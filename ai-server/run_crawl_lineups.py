"""
경기별 선발 라인업 + 교체 정보 크롤러.
matchInfo.do API에서 lineups/substitutions 데이터를 수집해
match_lineups_{season}.json 에 저장한다.

사용법:
    python run_crawl_lineups.py                  # 2025 전체
    python run_crawl_lineups.py --season 2024
    python run_crawl_lineups.py --limit 10       # 최근 10경기만
    python run_crawl_lineups.py --game-id 5      # 특정 경기 하나
    python run_crawl_lineups.py --force          # 이미 수집된 것도 재크롤
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


def load_game_list(season: int) -> list[dict]:
    """k1_team_results.json에서 완료된 경기 목록 로드."""
    path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    if not path.exists():
        logger.error(f"경기 데이터 없음: {path}")
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    # 중복 제거 + 해당 시즌 완료 경기
    seen, unique = set(), []
    for r in records:
        gid = r.get("game_id")
        if gid and gid not in seen and r.get("season") == season and r.get("finished"):
            seen.add(gid)
            unique.append(r)
    unique.sort(key=lambda r: (r.get("date", ""), r.get("game_id", 0)))
    return unique


def load_existing(out_path: Path) -> dict:
    """이미 수집된 라인업 데이터 로드."""
    if not out_path.exists():
        return {}
    data = json.loads(out_path.read_text(encoding="utf-8"))
    return {item["game_id"]: item for item in data.get("lineups_by_game", [])}


def save_lineups(lineups_by_game: dict, season: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season": season,
        "league": "K1",
        "total_games": len(lineups_by_game),
        "lineups_by_game": list(lineups_by_game.values()),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"저장 완료: {out_path} ({len(lineups_by_game)}경기)")


def main():
    parser = argparse.ArgumentParser(description="K리그 라인업 크롤러")
    parser.add_argument("--season",  type=int,   default=2025)
    parser.add_argument("--limit",   type=int,   default=0,   help="최대 경기 수 (0=전체)")
    parser.add_argument("--game-id", type=int,   default=0,   help="특정 game_id만")
    parser.add_argument("--delay",   type=float, default=2.0, help="경기 간 딜레이(초)")
    parser.add_argument("--force",   action="store_true",     help="기존 수집 데이터도 재크롤")
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
               colorize=True)

    out_path = ROOT / "data" / "processed" / "matches" / f"match_lineups_{args.season}.json"

    from crawlers.sources.kleague_crawler import KleagueCrawler
    raw_cache = ROOT / "data" / "raw" / "kleague_lineups"
    raw_cache.mkdir(parents=True, exist_ok=True)
    crawler = KleagueCrawler(raw_cache_dir=raw_cache)

    if not crawler.is_available():
        logger.error("kleague.com 접근 불가")
        sys.exit(1)

    # 대상 경기 결정
    if args.game_id:
        target_games = [{"game_id": args.game_id, "season": args.season,
                         "date": "?", "home_team": "?", "away_team": "?", "round": 0}]
    else:
        all_games = load_game_list(args.season)
        target_games = all_games[:args.limit] if args.limit else all_games
        logger.info(f"크롤링 대상: {len(target_games)}경기 ({args.season}시즌)")

    existing = {} if args.force else load_existing(out_path)
    logger.info(f"기존 수집: {len(existing)}경기")

    for i, game in enumerate(target_games, 1):
        gid = game["game_id"]

        if gid in existing:
            logger.debug(f"스킵: game_id={gid}")
            continue

        logger.info(
            f"[{i}/{len(target_games)}] game_id={gid}  "
            f"{game.get('date')} {game.get('home_team')} vs {game.get('away_team')}"
        )

        year = game.get("season", args.season)
        raw = crawler.crawl_match_events(
            gid,
            year=year,
            meet_seq=1,
            home_team=game.get("home_team", ""),
            away_team=game.get("away_team", ""),
        )

        record = {
            "game_id":       gid,
            "season":        year,
            "round":         game.get("round"),
            "date":          game.get("date", ""),
            "home_team":     game.get("home_team", ""),
            "away_team":     game.get("away_team", ""),
            "home_score":    game.get("home_score"),
            "away_score":    game.get("away_score"),
            "lineups":       raw.get("lineups", {}),
            "substitutions": raw.get("substitutions", []),
        }
        existing[gid] = record

        lineup_count = (
            len(record["lineups"].get("home", {}).get("starters", []))
            + len(record["lineups"].get("away", {}).get("starters", []))
        )
        sub_count = len(record["substitutions"])
        logger.info(f"  └─ 선수 {lineup_count}명 라인업, 교체 {sub_count}건")

        if i % 10 == 0:
            save_lineups(existing, args.season, out_path)

        time.sleep(args.delay)

    save_lineups(existing, args.season, out_path)
    logger.info("라인업 크롤링 완료")

    # 자동으로 출전시간 계산
    from process_player_minutes import process_season
    process_season(args.season)

    # 자동으로 선수별 클린시트 계산
    from process_player_cleansheets import process_season as process_cs_season
    process_cs_season(args.season)


if __name__ == "__main__":
    main()
