"""
K리그1 2010~2019 레거시 시즌 데이터 수집 스크립트.

실행:
    python run_crawl_legacy.py                         # 2010~2019 전체
    python run_crawl_legacy.py --seasons 2015 2016     # 특정 연도만
    python run_crawl_legacy.py --skip-events           # 팀 결과만 (이벤트 제외)
    python run_crawl_legacy.py --seasons 2019 --delay 1.5

소요 시간 예상:
    팀 결과 (12요청/시즌): ~15초/시즌
    이벤트  (~240경기/시즌 × 1.2초): ~5분/시즌 → 10시즌 전체 ~50분

2010~2019 K리그1 팀 구성 변화:
  2010~2012: 15~16팀 (전북, 울산, 서울, 포항, 수원삼성, 성남, 전남, 부산,
                       경남, 인천, 대전, 광주, 강원, 제주, 대구, 상주)
  2013:     K리그 클래식으로 명칭 변경, 14팀
  2014~2019: 12~14팀 (팀별 승강제로 매년 구성 변동)

과거 팀명 → 현재 단축명 정규화 테이블:
  "울산 현대"      → 울산
  "전북 현대"      → 전북
  "수원 삼성"      → 수원삼성
  "성남 일화"      → 성남
  "상주 상무"      → 상주
  "서울 이랜드"    → 서울이랜드
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

# ── 과거 팀명 정규화 ────────────────────────────────────────────────────────
# kleague.com API가 반환하는 과거 팀명 → 통일된 단축명
LEGACY_TEAM_NAME_MAP: dict[str, str] = {
    "울산 현대": "울산",
    "울산현대": "울산",
    "전북 현대": "전북",
    "전북현대": "전북",
    "수원 삼성": "수원삼성",
    "수원삼성": "수원삼성",
    "수원 삼성 블루윙즈": "수원삼성",
    "성남 일화": "성남",
    "성남일화": "성남",
    "성남 천마": "성남",
    "FC 서울": "서울",
    "서울 이랜드 FC": "서울이랜드",
    "포항 스틸러스": "포항",
    "인천 유나이티드": "인천",
    "인천유나이티드": "인천",
    "전남 드래곤즈": "전남",
    "전남드래곤즈": "전남",
    "경남 FC": "경남",
    "대전 시티즌": "대전",
    "대전시티즌": "대전",
    "대전 코레일": "대전",
    "제주 유나이티드": "제주",
    "제주유나이티드": "제주",
    "광주 FC": "광주",
    "강원 FC": "강원",
    "대구 FC": "대구",
    "부산 아이파크": "부산",
    "부산아이파크": "부산",
    "상주 상무": "상주",
    "상주상무": "상주",
    "상주 상무 피닉스": "상주",
    "안양 LG 치타스": "서울",   # 서울 전신
    "부천 SK": "제주",           # 제주 전신
    "대우 로얄즈": "부산",       # 부산 전신
    "수원 FC": "수원FC",
    "수원FC": "수원FC",
    "대전 하나 시티즌": "대전",
    "광양 전남 드래곤즈": "전남",
    "김천 상무": "김천",
    "김천상무": "김천",
    "성남 FC": "성남",
}


def normalize_team_name(name: str) -> str:
    """과거 팀명을 현재 통일된 단축명으로 변환합니다."""
    if not name:
        return name
    # 정확히 일치하는 경우
    if name in LEGACY_TEAM_NAME_MAP:
        return LEGACY_TEAM_NAME_MAP[name]
    # 부분 일치 시도
    for legacy, canonical in LEGACY_TEAM_NAME_MAP.items():
        if legacy in name:
            return canonical
    return name


def load_existing_results() -> dict:
    """(season, game_id) 복합키로 기존 데이터 로드."""
    if not RESULTS_PATH.exists():
        return {}
    records = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    return {(r["season"], r["game_id"]): r for r in records if r.get("game_id") and r.get("season")}


def save_results(by_key: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = sorted(by_key.values(), key=lambda r: (r.get("season", 0), r.get("date", "")))
    RESULTS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"k1_team_results 저장: {len(records)}경기")


def crawl_season_results(session, season: int, existing: dict) -> int:
    """
    월별 스케줄 API로 해당 시즌 K1 전체 경기 수집.
    2010~2019는 leagueId가 달랐을 수 있으므로 복수 leagueId 시도.
    """
    url = "https://www.kleague.com/getScheduleList.do"
    added = 0

    # 2013 이전: K리그 단일 리그 (leagueId=1 or 다를 수 있음)
    # 2013 이후: K리그 클래식 = leagueId=1, K리그 챌린지 = leagueId=2
    league_ids = ["1"]

    for league_id in league_ids:
        for month in range(1, 13):
            payload = {"leagueId": league_id, "year": str(season), "month": f"{month:02d}"}
            try:
                r = session.post(url, json=payload, timeout=20)
                data = r.json()

                if isinstance(data, dict) and data.get("resultCode") != "200":
                    continue

                items = data.get("data", {}).get("scheduleList", []) if isinstance(data, dict) else []

                for item in items:
                    if item.get("endYn") != "Y":
                        continue

                    gid = item.get("gameId")
                    key = (season, gid)
                    if not gid or key in existing:
                        continue

                    home_raw = item.get("homeTeamName", "")
                    away_raw = item.get("awayTeamName", "")

                    existing[key] = {
                        "game_id": gid,
                        "season": season,
                        "round": item.get("roundId", ""),
                        "date": item.get("gameDate", ""),
                        "time": item.get("gameTime", ""),
                        "competition": item.get("meetName", ""),
                        "home_team": normalize_team_name(home_raw),
                        "home_team_raw": home_raw,
                        "home_team_id": item.get("homeTeam", ""),
                        "away_team": normalize_team_name(away_raw),
                        "away_team_raw": away_raw,
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
                    finished = sum(1 for i in items if i.get("endYn") == "Y")
                    if finished > 0:
                        logger.info(f"  {season}/{month:02d}: {finished}경기")

            except Exception as e:
                logger.warning(f"  {season}/{month:02d} 실패: {e}")

            time.sleep(random.uniform(0.8, 1.5))

    return added


def crawl_season_events(session, season: int, delay: float = 1.2) -> None:
    """특정 시즌 경기 이벤트 수집 → match_events_{season}.json + player_stats_{season}.json."""
    out_path = MATCHES_DIR / f"match_events_{season}.json"

    existing_events: dict = {}
    if out_path.exists():
        data = json.loads(out_path.read_text(encoding="utf-8"))
        existing_events = {item["game_id"]: item for item in data.get("events_by_game", [])}
        logger.info(f"  기존 이벤트 {len(existing_events)}경기 이어받기")

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

    if not new_games:
        logger.info(f"  [{season}] 모든 경기 이미 수집됨")
        return

    # JSESSIONID 갱신
    try:
        session.get("https://www.kleague.com/", timeout=10)
    except Exception:
        pass

    match_event_url = "https://www.kleague.com/api/ddf/match/matchInfo.do"
    no_data_count = 0

    for i, game in enumerate(new_games, 1):
        gid = game["game_id"]
        logger.info(
            f"  [{i}/{len(new_games)}] game_id={gid} {game.get('date')} "
            f"{game.get('home_team')} vs {game.get('away_team')}"
        )

        events_data = {"game_id": gid, "events": []}
        try:
            r = session.post(
                match_event_url,
                data={"year": str(season), "meetSeq": "1", "gameId": str(gid)},
                headers={"X-Requested-With": "XMLHttpRequest"},
                timeout=20,
            )
            raw = r.json()
            events_data = _parse_match_events(
                raw, gid,
                game.get("home_team", ""),
                game.get("away_team", ""),
            )
        except Exception as e:
            logger.warning(f"    이벤트 수집 실패: {e}")

        events_data["date"]       = game.get("date", "")
        events_data["home_team"]  = game.get("home_team", "")
        events_data["away_team"]  = game.get("away_team", "")
        events_data["home_score"] = game.get("home_score")
        events_data["away_score"] = game.get("away_score")
        existing_events[gid] = events_data

        event_count = len(events_data.get("events", []))
        logger.info(f"    └─ 이벤트 {event_count}개")
        if event_count == 0:
            no_data_count += 1

        # 중간 저장 (20경기마다)
        if i % 20 == 0:
            _save_events(existing_events, out_path, season)

        time.sleep(delay + random.uniform(0, 0.5))

    _save_events(existing_events, out_path, season)
    _save_player_stats(existing_events, season)

    if no_data_count > len(new_games) * 0.5:
        logger.warning(
            f"  [{season}] 이벤트 없는 경기 {no_data_count}/{len(new_games)}건 — "
            f"kleague.com이 {season}년 이벤트 데이터를 미제공할 수 있습니다."
        )


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

    for item in (
        (inner.get("firstHalf") or []) +
        (inner.get("secondHalf") or []) +
        (inner.get("EfirstHalf") or []) +
        (inner.get("EsecondHalf") or [])
    ):
        raw_name = (item.get("eventName") or "").strip()
        player   = (item.get("playerName") or "").strip()
        team     = normalize_team_name((item.get("teamName") or "").strip())
        half_type = int(item.get("halfType") or 1)
        time_min  = int(item.get("timeMin") or 0)
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
        "source": "kleague_crawled",
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
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/122.0.0.0 Safari/537.36"
        ),
        "Referer": "https://www.kleague.com/",
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "ko-KR,ko;q=0.9",
    })
    return s


def main():
    parser = argparse.ArgumentParser(
        description="K리그1 2010~2019 레거시 데이터 수집",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--seasons", type=int, nargs="+",
        default=list(range(2010, 2020)),
        help="수집할 시즌 (기본: 2010~2019)",
    )
    parser.add_argument("--skip-events", action="store_true", help="이벤트 크롤링 건너뜀")
    parser.add_argument("--delay", type=float, default=1.2, help="이벤트 경기 간 딜레이(초)")
    parser.add_argument("--results-only", action="store_true", help="팀 결과만 (--skip-events 별칭)")
    args = parser.parse_args()

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    session = _make_session()

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

    # ── Step 1: 팀 경기 결과 수집 ──────────────────────────────────────
    logger.info("\n[Step 1] K1 경기 결과 수집")
    existing = load_existing_results()
    logger.info(f"기존 경기 수: {len(existing)}")

    total_added = 0
    for season in args.seasons:
        logger.info(f"\n  ── {season} 시즌 ──")
        added = crawl_season_results(session, season, existing)
        total_added += added
        logger.info(f"  {season} 신규 추가: {added}경기")
        save_results(existing)  # 시즌마다 중간 저장

    logger.info(f"\n팀 결과 수집 완료: {total_added}경기 추가 (전체 {len(existing)}경기)")

    if args.skip_events or args.results_only:
        logger.info("이벤트 크롤링 건너뜀")
        _print_summary(args.seasons)
        return

    # ── Step 2: 경기 이벤트 수집 ───────────────────────────────────────
    logger.info("\n[Step 2] 경기 이벤트 수집")
    for season in args.seasons:
        logger.info(f"\n  ── {season} 시즌 이벤트 ──")
        crawl_season_events(session, season, delay=args.delay)

    _print_summary(args.seasons)


def _print_summary(seasons: list[int]) -> None:
    logger.info("\n=== 수집 완료 ===")
    for season in seasons:
        events_path = MATCHES_DIR / f"match_events_{season}.json"
        stats_path  = PLAYERS_DIR / f"player_stats_{season}.json"
        e_ok = events_path.exists()
        s_ok = stats_path.exists()
        if e_ok:
            data = json.loads(events_path.read_text(encoding="utf-8"))
            games = len(data.get("events_by_game", []))
            goals = sum(
                sum(1 for ev in g.get("events", []) if ev.get("type") == "goal")
                for g in data.get("events_by_game", [])
            )
            logger.info(f"  {season}: {games}경기, {goals}골 이벤트")
        else:
            logger.info(f"  {season}: match_events 없음")
        if not s_ok:
            logger.info(f"  {season}: player_stats 없음")


if __name__ == "__main__":
    main()
