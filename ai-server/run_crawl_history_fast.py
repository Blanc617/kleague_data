"""
K리그 과거 시즌 데이터 빠른 수집 스크립트.

월별로 전체 경기를 한 번에 수집 (팀별 순회 대신 12요청/시즌).

실행:
    python run_crawl_history_fast.py                     # 2022~2024 전체
    python run_crawl_history_fast.py --seasons 2024      # 특정 연도만
    python run_crawl_history_fast.py --skip-events       # 팀 결과만

소요 시간 예상:
    팀 결과: 12요청 × 1초 = ~12초/시즌
    이벤트: 220경기 × 0.8초 = ~3분/시즌
"""

import argparse
import json
import sys
import time
import random
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

RESULTS_PATH = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
MATCHES_DIR  = ROOT / "data" / "processed" / "matches"
PLAYERS_DIR  = ROOT / "data" / "processed" / "players"


def load_existing_results() -> dict:
    """game_id는 시즌마다 1부터 재사용되므로 (season, game_id) 복합키 사용."""
    if not RESULTS_PATH.exists():
        return {}
    records = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    return {(r["season"], r["game_id"]): r for r in records if r.get("game_id") and r.get("season")}


def save_results(by_key: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = sorted(by_key.values(), key=lambda r: (r.get("season", 0), r.get("date", "")))
    RESULTS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"k1_team_results 저장: {len(records)}경기")


def crawl_season_results_fast(session, season: int, existing: dict) -> int:
    """월별 전체 경기를 한 번에 수집 → 12요청/시즌.
    existing 키: (season, game_id) 복합키."""
    url = "https://www.kleague.com/getScheduleList.do"
    added = 0

    for month in range(1, 13):
        payload = {"leagueId": "1", "year": str(season), "month": f"{month:02d}"}
        try:
            r = session.post(url, json=payload, timeout=15)
            data = r.json()
            items = data.get("data", {}).get("scheduleList", []) if isinstance(data, dict) else []

            for item in items:
                if item.get("endYn") != "Y":
                    continue  # 완료된 경기만

                gid = item.get("gameId")
                key = (season, gid)
                if not gid or key in existing:
                    continue

                existing[key] = {
                    "game_id": gid,
                    "season": season,
                    "round": item.get("roundId", ""),
                    "date": item.get("gameDate", ""),
                    "time": item.get("gameTime", ""),
                    "competition": item.get("meetName", ""),
                    "home_team": item.get("homeTeamName", ""),
                    "home_team_id": item.get("homeTeam", ""),
                    "away_team": item.get("awayTeamName", ""),
                    "away_team_id": item.get("awayTeam", ""),
                    "home_score": item.get("homeGoal"),
                    "away_score": item.get("awayGoal"),
                    "venue": item.get("fieldNameFull", item.get("fieldName", "")),
                    "attendance": item.get("audienceQty"),
                    "finished": True,
                    "broadcast": item.get("broadcastName", ""),
                    "source": "kleague",
                }
                added += 1

            if items:
                finished_cnt = sum(1 for i in items if i.get("endYn") == "Y")
                logger.info(f"  {season}/{month:02d}: {finished_cnt}경기 완료")

        except Exception as e:
            logger.warning(f"  {season}/{month:02d} 실패: {e}")

        time.sleep(random.uniform(0.5, 1.0))

    return added


def crawl_season_events(session, season: int, delay: float = 0.8) -> None:
    """특정 시즌 경기 이벤트 수집."""
    out_path = MATCHES_DIR / f"match_events_{season}.json"

    existing_events: dict = {}
    if out_path.exists():
        data = json.loads(out_path.read_text(encoding="utf-8"))
        existing_events = {item["game_id"]: item for item in data.get("events_by_game", [])}

    if not RESULTS_PATH.exists():
        logger.error("k1_team_results.json 없음")
        return

    records = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    seen, target_games = set(), []
    for r in records:
        gid = r.get("game_id")
        if gid and gid not in seen and r.get("season") == season and r.get("finished"):
            seen.add(gid)
            target_games.append(r)
    target_games.sort(key=lambda r: (r.get("date", ""), r.get("game_id", 0)))

    new_games = [g for g in target_games if g["game_id"] not in existing_events]
    logger.info(f"[{season}] 이벤트 수집 대상: {len(new_games)}/{len(target_games)}경기")

    # 이벤트 API는 JSESSIONID 필요 → kleague 메인 페이지 먼저 방문
    try:
        session.get("https://www.kleague.com/", timeout=10)
    except Exception:
        pass

    match_event_url = "https://www.kleague.com/api/ddf/match/matchInfo.do"

    for i, game in enumerate(new_games, 1):
        gid = game["game_id"]
        logger.info(f"  [{i}/{len(new_games)}] game_id={gid} {game.get('date')} "
                    f"{game.get('home_team')} vs {game.get('away_team')}")

        try:
            r = session.post(
                match_event_url,
                data={"year": str(season), "meetSeq": "1", "gameId": str(gid)},
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=15,
            )
            data = r.json()
            events_data = _parse_match_events(data, gid, game.get("home_team", ""), game.get("away_team", ""))
        except Exception as e:
            logger.warning(f"    이벤트 수집 실패: {e}")
            events_data = {"game_id": gid, "events": []}

        events_data["date"]       = game.get("date", "")
        events_data["home_team"]  = game.get("home_team", "")
        events_data["away_team"]  = game.get("away_team", "")
        events_data["home_score"] = game.get("home_score")
        events_data["away_score"] = game.get("away_score")
        existing_events[gid] = events_data
        logger.info(f"    └─ 이벤트 {len(events_data.get('events', []))}개")

        if i % 20 == 0:
            _save_events(existing_events, out_path, season)

        time.sleep(delay)

    _save_events(existing_events, out_path, season)
    _save_player_stats(existing_events, season)


def _parse_match_events(data: dict, game_id: int, home_team: str, away_team: str) -> dict:
    if not isinstance(data, dict) or data.get("resultCode") != "200":
        return {"game_id": game_id, "events": []}
    inner = data.get("data", {})
    if not inner:
        return {"game_id": game_id, "events": []}

    events = []

    for side, team_name in (("homeScorer", home_team), ("awayScorer", away_team)):
        for scorer in inner.get(side, []) or []:
            name = (scorer.get("name") or "").strip()
            if not name:
                continue
            minute = int(scorer.get("time") or 0)
            event_type = "own_goal" if scorer.get("isOwnGoal") else "goal"
            events.append({"minute": minute, "type": event_type, "player": name, "team": team_name})

    ASSIST_NAMES     = {"도움", "assist"}
    YELLOW_NAMES     = {"경고", "yellow card"}
    RED_NAMES        = {"퇴장", "직접 퇴장", "red card"}
    YELLOW_RED_NAMES = {"경고 퇴장", "경고퇴장", "두 번째 경고"}
    HALF_OFFSET = {1: 0, 2: 45, 3: 90, 4: 105}

    assist_map: dict[int, str] = {}
    card_events = []

    for item in ((inner.get("firstHalf") or []) + (inner.get("secondHalf") or []) +
                 (inner.get("EfirstHalf") or []) + (inner.get("EsecondHalf") or [])):
        raw_name = (item.get("eventName") or "").strip()
        player = (item.get("playerName") or "").strip()
        team = (item.get("teamName") or "").strip()
        half_type = int(item.get("halfType") or 1)
        time_min = int(item.get("timeMin") or 0)
        game_minute = HALF_OFFSET.get(half_type, 0) + time_min

        if raw_name in ASSIST_NAMES and player:
            assist_map[game_minute] = player
        elif raw_name in YELLOW_NAMES and player:
            card_events.append({"minute": game_minute, "type": "yellow_card", "team": team, "player": player})
        elif raw_name in RED_NAMES and player:
            card_events.append({"minute": game_minute, "type": "red_card", "team": team, "player": player})
        elif raw_name in YELLOW_RED_NAMES and player:
            card_events.append({"minute": game_minute, "type": "yellow_red", "team": team, "player": player})

    for e in events:
        if e["type"] == "goal":
            assist = assist_map.get(e["minute"])
            if assist:
                e["assist"] = assist

    events.extend(card_events)
    events.sort(key=lambda e: e["minute"])
    return {"game_id": game_id, "events": events}


def _save_events(events_by_game: dict, out_path: Path, season: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season": season,
        "league": "K1",
        "total_games": len(events_by_game),
        "events_by_game": list(events_by_game.values()),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"  저장: {out_path.name} ({len(events_by_game)}경기)")


def _save_player_stats(events_by_game: dict, season: int) -> None:
    from generate_match_events import aggregate_player_stats

    player_stats = aggregate_player_stats(list(events_by_game.values()))
    stats_path = PLAYERS_DIR / f"player_stats_{season}.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season": season,
        "league": "K1",
        "source": "kleague_crawled",
        "total_players": len(player_stats),
        "players": player_stats,
    }
    stats_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"  player_stats_{season}.json 저장: {len(player_stats)}명")


def _make_session():
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Referer": "https://www.kleague.com/",
        "Accept": "application/json, text/plain, */*",
    })
    return s


def main():
    parser = argparse.ArgumentParser(description="K리그 과거 시즌 데이터 빠른 수집")
    parser.add_argument("--seasons", type=int, nargs="+", default=[2022, 2023, 2024],
                        help="수집할 시즌 목록 (기본: 2022~2024)")
    parser.add_argument("--skip-events", action="store_true", help="이벤트 크롤링 건너뜀")
    parser.add_argument("--delay", type=float, default=0.8, help="이벤트 경기 간 딜레이(초)")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
               colorize=True)

    session = _make_session()

    # 연결 확인
    try:
        r = session.get("https://www.kleague.com/", timeout=10)
        if r.status_code != 200:
            logger.error(f"kleague.com 접근 불가 (HTTP {r.status_code})")
            sys.exit(1)
        logger.info("kleague.com 연결 확인됨")
    except Exception as e:
        logger.error(f"kleague.com 접근 불가: {e}")
        sys.exit(1)

    logger.info(f"수집 시즌: {args.seasons}")

    # ── Step 1: 팀 경기 결과 수집 ──────────────────────
    logger.info("\n[Step 1] 팀 경기 결과 수집 (월별 일괄)")
    existing_results = load_existing_results()
    logger.info(f"기존 경기 수: {len(existing_results)}")

    total_added = 0
    for season in args.seasons:
        logger.info(f"\n  ── {season}시즌 ──")
        added = crawl_season_results_fast(session, season, existing_results)
        total_added += added
        logger.info(f"  {season}시즌 신규 추가: {added}경기")
        save_results(existing_results)

    logger.info(f"\n팀 결과 수집 완료: {total_added}경기 추가 (전체 {len(existing_results)}경기)")

    if args.skip_events:
        logger.info("--skip-events: 이벤트 크롤링 건너뜀")
        return

    # ── Step 2: 경기 이벤트 수집 ──────────────────────
    logger.info("\n[Step 2] 경기 이벤트 수집")
    for season in args.seasons:
        logger.info(f"\n  ── {season}시즌 이벤트 ──")
        crawl_season_events(session, season, delay=args.delay)

    logger.info("\n전체 과거 데이터 수집 완료!")
    for season in args.seasons:
        events_path = MATCHES_DIR / f"match_events_{season}.json"
        stats_path  = PLAYERS_DIR / f"player_stats_{season}.json"
        logger.info(f"  match_events_{season}.json: {'OK' if events_path.exists() else '없음'}")
        logger.info(f"  player_stats_{season}.json: {'OK' if stats_path.exists() else '없음'}")


if __name__ == "__main__":
    main()
