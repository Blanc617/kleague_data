"""
FotMob matchDetails에서 득점 유형(필드골/코너킥/프리킥/페널티킥)을 추출해
match_events_{season}.json 의 골 이벤트에 goal_type 필드를 추가합니다.

매핑 방식: FotMob 경기 ↔ match_events 경기를 날짜 + 팀명으로 직접 연결.
k1_team_results.json 불필요 → 모든 시즌(2010~2026) 처리 가능.

이미 run_crawl_fotmob_lineups.py 로 수집된 캐시 파일이 있으면 추가 API 호출 없음.

사용법:
    python run_crawl_fotmob_goal_types.py                  # 2025 기본
    python run_crawl_fotmob_goal_types.py --season 2022
    python run_crawl_fotmob_goal_types.py --all-seasons    # 2010~2026 전체
    python run_crawl_fotmob_goal_types.py --all-seasons --stats
    python run_crawl_fotmob_goal_types.py --force          # 이미 처리된 것도 재처리
"""

import argparse
import json
import sys
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")


# ── 유틸 ──────────────────────────────────────────────────────────────


def _similar(a: str, b: str) -> bool:
    """팀명 유사도 비교 (부분 일치)."""
    a, b = a.strip().lower(), b.strip().lower()
    return bool(a and b and (a == b or a in b or b in a))


def load_match_events(season: int) -> tuple[dict | None, Path]:
    """match_events_{season}.json 로드. 파일 없으면 None 반환."""
    path = ROOT / "data" / "processed" / "matches" / f"match_events_{season}.json"
    if not path.exists():
        return None, path
    return json.loads(path.read_text(encoding="utf-8")), path


def save_match_events(data: dict, path: Path) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"저장 완료: {path}")


def map_fotmob_to_events(
    fotmob_matches: list[dict],
    events_games: list[dict],
) -> dict[int, dict]:
    """
    FotMob 경기 목록 ↔ match_events 게임을 날짜 + 팀명으로 직접 매핑.
    반환: {fotmob_id: game_dict}
    """
    mapping: dict[int, dict] = {}

    for fm in fotmob_matches:
        fm_date = fm["date"][:10]  # YYYY.MM.DD
        for game in events_games:
            # 날짜 비교
            game_date = str(game.get("date", ""))[:10]
            if game_date != fm_date:
                continue
            # 팀명 비교
            if _similar(fm["home"], game.get("home_team", "")) and \
               _similar(fm["away"], game.get("away_team", "")):
                mapping[fm["fotmob_id"]] = game
                break

    return mapping


def enrich_game_events(game: dict, fotmob_goals: list[dict], force: bool) -> int:
    """
    game["events"] 의 goal 이벤트에 goal_type 필드를 추가.
    FotMob 골 → match_events 골을 분(minute) + 팀명으로 매핑.
    반환: 업데이트된 골 수
    """
    updated = 0
    events = game.get("events", [])

    # FotMob 골을 (minute, team) 인덱스로 (±1분 허용)
    fm_index: dict[tuple, str] = {}
    for fg in fotmob_goals:
        for delta in range(-1, 2):
            key = (fg["minute"] + delta, fg["team"])
            if key not in fm_index:
                fm_index[key] = fg["goal_type"]

    for ev in events:
        if ev.get("type") not in ("goal", "own_goal"):
            continue
        if not force and "goal_type" in ev:
            continue

        key = (ev.get("minute", 0), ev.get("team", ""))
        goal_type = fm_index.get(key)

        if goal_type:
            ev["goal_type"] = goal_type
        elif ev.get("type") == "own_goal":
            ev["goal_type"] = "own_goal"
        else:
            ev["goal_type"] = "open_play"  # 매핑 실패 시 기본값

        updated += 1

    return updated


def print_stats(data: dict, season: int) -> None:
    """득점 유형 통계 출력."""
    counts: dict[str, int] = defaultdict(int)
    total = 0

    for game in data.get("events_by_game", []):
        for ev in game.get("events", []):
            if ev.get("type") in ("goal", "own_goal"):
                counts[ev.get("goal_type", "unknown")] += 1
                total += 1

    if not total:
        return

    order  = ["open_play", "corner", "free_kick", "penalty", "own_goal", "unknown"]
    labels = {
        "open_play": "필드골   ",
        "corner":    "코너킥   ",
        "free_kick": "프리킥   ",
        "penalty":   "페널티킥 ",
        "own_goal":  "자책골   ",
        "unknown":   "미확인   ",
    }
    print(f"\n── {season}시즌 득점 유형 통계 ──────────────")
    for key in order:
        cnt = counts.get(key, 0)
        if not cnt:
            continue
        pct = cnt / total * 100
        bar = "█" * int(pct / 2)
        print(f"  {labels.get(key, key)}: {cnt:4d}골 ({pct:5.1f}%)  {bar}")
    print(f"  {'합계':8s}: {total:4d}골\n")


# ── 시즌 단위 처리 ────────────────────────────────────────────────────


def run_season(season: int, crawler, raw_cache: Path, args) -> dict:
    """단일 시즌 처리. 반환: {"updated": int, "cache_hits": int, "api_calls": int}"""
    logger.info(f"━━━ {season}시즌 시작 ━━━")

    # 1. match_events 로드
    events_data, events_path = load_match_events(season)
    if events_data is None:
        logger.warning(f"match_events_{season}.json 없음 — 스킵")
        return {"updated": 0, "cache_hits": 0, "api_calls": 0}

    events_games = events_data.get("events_by_game", [])
    # 골이 하나도 없는 시즌은 스킵 (2010~2012 등 더미 데이터)
    total_goals = sum(
        1 for g in events_games
        for e in g.get("events", [])
        if e.get("type") in ("goal", "own_goal")
    )
    if total_goals == 0:
        logger.warning(f"{season}시즌 골 데이터 없음 — 스킵")
        return {"updated": 0, "cache_hits": 0, "api_calls": 0}

    logger.info(f"match_events 보유: {len(events_games)}경기, {total_goals}골")

    # 2. FotMob 시즌 경기 목록
    fotmob_matches = crawler.fetch_season_matches(season)
    finished = [m for m in fotmob_matches if m["finished"]]
    logger.info(f"FotMob 완료 경기: {len(finished)}/{len(fotmob_matches)}")

    if not finished:
        logger.warning(f"{season}시즌 FotMob 데이터 없음 — 스킵")
        return {"updated": 0, "cache_hits": 0, "api_calls": 0}

    # 3. FotMob ↔ match_events 직접 매핑 (날짜 + 팀명)
    mapping = map_fotmob_to_events(finished, events_games)
    logger.info(f"매핑 성공: {len(mapping)}/{len(finished)}경기")

    if not mapping:
        logger.warning(f"{season}시즌 매핑 실패 — 스킵")
        return {"updated": 0, "cache_hits": 0, "api_calls": 0}

    targets = [m for m in finished if m["fotmob_id"] in mapping]
    if args.limit:
        targets = targets[-args.limit:]

    # 4. 득점 유형 수집 + 보강
    total_updated = 0
    cache_hits = 0
    api_calls = 0

    for i, fm in enumerate(targets, 1):
        fotmob_id = fm["fotmob_id"]
        game      = mapping[fotmob_id]

        # 이미 모든 골에 goal_type 있으면 스킵
        if not args.force:
            goal_events = [
                e for e in game.get("events", [])
                if e.get("type") in ("goal", "own_goal")
            ]
            if goal_events and all("goal_type" in e for e in goal_events):
                logger.debug(f"스킵 (이미 처리됨): {game.get('date')} {game.get('home_team')} vs {game.get('away_team')}")
                continue

        cache_path = raw_cache / f"fotmob_match_{fotmob_id}.json"
        is_cached = cache_path.exists()
        if is_cached:
            cache_hits += 1
        else:
            api_calls += 1
            time.sleep(args.delay)

        logger.info(
            f"  [{i}/{len(targets)}] {game.get('date')} "
            f"{game.get('home_team')} vs {game.get('away_team')}  "
            f"{'[캐시]' if is_cached else '[API]'}"
        )

        fotmob_goals = crawler.fetch_match_goal_types(fotmob_id)
        updated = enrich_game_events(game, fotmob_goals, args.force)

        goal_types = [
            e.get("goal_type") for e in game.get("events", [])
            if e.get("type") in ("goal", "own_goal")
        ]
        logger.info(f"    └─ FotMob {len(fotmob_goals)}골 매핑 | {goal_types}")

        total_updated += updated

        if i % 10 == 0:
            save_match_events(events_data, events_path)

    # 5. 저장
    save_match_events(events_data, events_path)
    logger.info(
        f"{season}시즌 완료 — 업데이트 {total_updated}골 | "
        f"캐시 {cache_hits}건 / API {api_calls}건"
    )

    if args.stats:
        print_stats(events_data, season)

    return {"updated": total_updated, "cache_hits": cache_hits, "api_calls": api_calls}


# ── 메인 ──────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="FotMob 득점 유형 수집 → match_events 보강")

    season_group = parser.add_mutually_exclusive_group()
    season_group.add_argument("--season",      type=int, help="단일 시즌 (예: 2025)")
    season_group.add_argument("--all-seasons", action="store_true", help="2010~2026 전체 시즌")

    parser.add_argument("--limit",  type=int,   default=0,   help="시즌당 최대 경기 수 (0=전체)")
    parser.add_argument("--delay",  type=float, default=1.5, help="캐시 미스 시 API 딜레이(초)")
    parser.add_argument("--force",  action="store_true",     help="이미 goal_type 있는 이벤트도 재처리")
    parser.add_argument("--stats",  action="store_true",     help="시즌 완료 후 득점 유형 통계 출력")
    args = parser.parse_args()

    if args.all_seasons:
        seasons = list(range(2010, 2027))
    elif args.season:
        seasons = [args.season]
    else:
        seasons = [2025]

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    raw_cache = ROOT / "data" / "raw" / "fotmob"
    raw_cache.mkdir(parents=True, exist_ok=True)

    from crawlers.sources.fotmob_crawler import FotmobCrawler
    crawler = FotmobCrawler(raw_cache_dir=raw_cache)

    grand_total = {"updated": 0, "cache_hits": 0, "api_calls": 0}

    for season in seasons:
        result = run_season(season, crawler, raw_cache, args)
        for k in grand_total:
            grand_total[k] += result[k]

    if len(seasons) > 1:
        logger.info(
            f"\n전체 완료 ({seasons[0]}~{seasons[-1]}) — "
            f"업데이트 {grand_total['updated']}골 | "
            f"캐시 {grand_total['cache_hits']}건 / API {grand_total['api_calls']}건"
        )


if __name__ == "__main__":
    main()
