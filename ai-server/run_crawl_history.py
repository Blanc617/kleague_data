"""
K리그 과거 시즌 데이터 수집 스크립트 (2020~2024).

실행:
    python run_crawl_history.py                        # 2020~2024 전체
    python run_crawl_history.py --seasons 2023 2024    # 특정 연도만
    python run_crawl_history.py --skip-events          # 팀 결과만 (이벤트 크롤링 제외)

순서:
  1. 각 시즌 K1 팀 경기 결과 크롤링 → k1_team_results.json에 병합
  2. 각 시즌 경기 이벤트 크롤링 → match_events_{year}.json
  3. 각 시즌 선수 통계 집계 → player_stats_{year}.json
"""

import argparse
import json
import sys
import time
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
    """기존 k1_team_results.json 로드 → (season, game_id) 복합키 딕셔너리."""
    if not RESULTS_PATH.exists():
        return {}
    records = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    return {(r["season"], r["game_id"]): r for r in records if r.get("game_id") and r.get("season")}


def save_results(by_key: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = sorted(by_key.values(), key=lambda r: (r.get("season", 0), r.get("date", "")))
    RESULTS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"k1_team_results 저장: {len(records)}경기")


def crawl_season_results(crawler, season: int, existing: dict) -> int:
    """특정 시즌 K1 전 팀 경기 결과를 수집해 existing에 병합. 추가된 경기 수 반환."""
    from crawlers.config.teams import K1_TEAMS

    added = 0
    for team in K1_TEAMS:
        try:
            results = crawler.crawl_team_results(team.name_ko, season)
            for r in results:
                gid = r.get("game_id")
                key = (season, gid)
                if gid and key not in existing:
                    existing[key] = r
                    added += 1
            logger.info(f"  {team.name_ko} {season}: {len(results)}경기")
        except Exception as e:
            logger.warning(f"  {team.name_ko} {season} 실패: {e}")
        time.sleep(0.5)

    return added


def crawl_season_events(crawler, season: int, delay: float = 1.5) -> None:
    """특정 시즌 match_events_{season}.json 수집 + player_stats_{season}.json 집계."""
    out_path = MATCHES_DIR / f"match_events_{season}.json"

    # 기존 데이터 로드 (이어받기)
    existing_events: dict = {}
    if out_path.exists():
        data = json.loads(out_path.read_text(encoding="utf-8"))
        existing_events = {item["game_id"]: item for item in data.get("events_by_game", [])}

    # 해당 시즌 완료 경기 목록
    if not RESULTS_PATH.exists():
        logger.error("k1_team_results.json 없음. 팀 결과를 먼저 수집하세요.")
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

    for i, game in enumerate(new_games, 1):
        gid = game["game_id"]
        logger.info(f"  [{i}/{len(new_games)}] game_id={gid} {game.get('date')} "
                    f"{game.get('home_team')} vs {game.get('away_team')}")

        result = crawler.crawl_match_events(
            gid,
            year=season,
            meet_seq=1,
            home_team=game.get("home_team", ""),
            away_team=game.get("away_team", ""),
        )
        result["date"]       = game.get("date", "")
        result["home_team"]  = game.get("home_team", "")
        result["away_team"]  = game.get("away_team", "")
        result["home_score"] = game.get("home_score")
        result["away_score"] = game.get("away_score")
        existing_events[gid] = result

        logger.info(f"    └─ 이벤트 {len(result.get('events', []))}개")

        if i % 10 == 0:
            _save_events(existing_events, out_path, season)

        time.sleep(delay)

    _save_events(existing_events, out_path, season)
    _save_player_stats(existing_events, season)


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


def main():
    parser = argparse.ArgumentParser(description="K리그 과거 시즌 데이터 수집")
    parser.add_argument("--seasons", type=int, nargs="+", default=list(range(2020, 2025)),
                        help="수집할 시즌 목록 (기본: 2020~2024)")
    parser.add_argument("--skip-events", action="store_true", help="이벤트 크롤링 건너뜀")
    parser.add_argument("--delay", type=float, default=1.5, help="경기 간 딜레이(초)")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
               colorize=True)

    from crawlers.sources.kleague_crawler import KleagueCrawler

    raw_cache = ROOT / "data" / "raw" / "kleague_events"
    raw_cache.mkdir(parents=True, exist_ok=True)
    crawler = KleagueCrawler(raw_cache_dir=raw_cache)

    if not crawler.is_available():
        logger.error("kleague.com 접근 불가")
        sys.exit(1)

    logger.info(f"수집 시즌: {args.seasons}")

    # ── Step 1: 팀 경기 결과 수집 및 병합 ──────────────
    logger.info("\n[Step 1] 팀 경기 결과 수집")
    existing_results = load_existing_results()
    logger.info(f"기존 경기 수: {len(existing_results)}")

    total_added = 0
    for season in args.seasons:
        logger.info(f"\n  ── {season}시즌 ──")
        added = crawl_season_results(crawler, season, existing_results)
        total_added += added
        logger.info(f"  {season}시즌 신규 추가: {added}경기")
        save_results(existing_results)  # 시즌마다 중간 저장

    logger.info(f"\n팀 결과 수집 완료: 총 {total_added}경기 추가 (전체 {len(existing_results)}경기)")

    if args.skip_events:
        logger.info("--skip-events: 이벤트 크롤링 건너뜀")
        return

    # ── Step 2: 경기 이벤트 수집 ──────────────────────
    logger.info("\n[Step 2] 경기 이벤트 수집")
    for season in args.seasons:
        logger.info(f"\n  ── {season}시즌 이벤트 ──")
        crawl_season_events(crawler, season, delay=args.delay)

    logger.info("\n전체 과거 데이터 수집 완료!")
    logger.info(f"생성된 파일:")
    for season in args.seasons:
        events_path = MATCHES_DIR / f"match_events_{season}.json"
        stats_path  = PLAYERS_DIR / f"player_stats_{season}.json"
        logger.info(f"  {events_path.name}: {'OK' if events_path.exists() else '없음'}")
        logger.info(f"  {stats_path.name}: {'OK' if stats_path.exists() else '없음'}")


if __name__ == "__main__":
    main()
