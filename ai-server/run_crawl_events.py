"""
경기별 득점/도움/경고/퇴장 이벤트 크롤러.

사용법:
    python run_crawl_events.py                  # 2025 전체 경기 크롤링
    python run_crawl_events.py --season 2023    # 특정 시즌
    python run_crawl_events.py --limit 10       # 최근 10경기만
    python run_crawl_events.py --game-id 5      # 특정 경기 하나
    python run_crawl_events.py --dry-run        # API 연결 테스트만
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

# OUT_PATH은 main()에서 --season 값에 따라 설정됨
OUT_PATH: Path = ROOT / "data" / "processed" / "matches" / "match_events_2025.json"


def load_game_ids(season: int = 2025) -> list[dict]:
    """k1_team_results.json에서 완료된 경기 목록 로드."""
    path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    if not path.exists():
        logger.error(f"경기 데이터 없음: {path}")
        return []

    records = json.loads(path.read_text(encoding="utf-8"))

    seen, unique = set(), []
    for r in records:
        gid = r.get("game_id")
        if gid and gid not in seen and r.get("season") == season and r.get("finished"):
            seen.add(gid)
            unique.append(r)

    unique.sort(key=lambda r: (r.get("date", ""), r.get("game_id", 0)))
    return unique


def load_existing_events() -> dict:
    """이미 수집된 이벤트 로드 (재시작 시 중복 방지).
    생성된 가짜 데이터(source=generated)는 무시하고 새로 크롤링합니다."""
    if not OUT_PATH.exists():
        return {}
    data = json.loads(OUT_PATH.read_text(encoding="utf-8"))
    if data.get("source") == "generated":
        logger.info("기존 파일이 생성된 가짜 데이터입니다. 처음부터 크롤링합니다.")
        return {}
    return {item["game_id"]: item for item in data.get("events_by_game", [])}


def save_events(events_by_game: dict, meta: dict) -> None:
    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season": meta.get("season", 2025),
        "league": "K1",
        "source": "kleague_crawled",
        "total_games": len(events_by_game),
        "events_by_game": list(events_by_game.values()),
    }
    OUT_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"저장 완료: {OUT_PATH} ({len(events_by_game)}경기)")


def save_player_stats(events_by_game: dict, season: int) -> None:
    """이벤트 데이터에서 선수별 시즌 통계 집계 후 저장."""
    from generate_match_events import aggregate_player_stats

    player_stats = aggregate_player_stats(list(events_by_game.values()))
    stats_path = ROOT / "data" / "processed" / "players" / f"player_stats_{season}.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_payload = {
        "season": season,
        "league": "K1",
        "source": "kleague_crawled",
        "total_players": len(player_stats),
        "players": player_stats,
    }
    stats_path.write_text(json.dumps(stats_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"player_stats 저장: {stats_path} ({len(player_stats)}명)")


def main():
    global OUT_PATH

    parser = argparse.ArgumentParser(description="K리그 경기 이벤트 크롤러")
    parser.add_argument("--season",  type=int, default=2025)
    parser.add_argument("--limit",   type=int, default=0,  help="최대 크롤링 경기 수 (0=전체)")
    parser.add_argument("--game-id", type=int, default=0,  help="특정 경기 game_id만 크롤링")
    parser.add_argument("--delay",   type=float, default=1.5, help="경기 간 딜레이(초)")
    parser.add_argument("--dry-run", action="store_true", help="API 연결만 테스트")
    args = parser.parse_args()

    # 시즌별 출력 파일
    OUT_PATH = ROOT / "data" / "processed" / "matches" / f"match_events_{args.season}.json"

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

    if args.dry_run:
        logger.info("kleague.com 접근 가능. --dry-run 종료")
        return

    # 크롤링할 경기 목록 결정
    if args.game_id:
        target_games = [{"game_id": args.game_id, "date": "?", "home_team": "?", "away_team": "?"}]
    else:
        all_games = load_game_ids(args.season)
        target_games = all_games[:args.limit] if args.limit else all_games
        logger.info(f"크롤링 대상: {len(target_games)}경기 ({args.season}시즌)")

    # 기존 데이터 로드 (이어받기)
    existing = load_existing_events()
    logger.info(f"기존 수집 데이터: {len(existing)}경기")

    import time
    for i, game in enumerate(target_games, 1):
        gid = game["game_id"]

        if gid in existing:
            logger.debug(f"스킵 (이미 수집): game_id={gid}")
            continue

        logger.info(f"[{i}/{len(target_games)}] game_id={gid}  {game.get('date')} {game.get('home_team')} vs {game.get('away_team')}")

        year = game.get("season", args.season)
        result = crawler.crawl_match_events(
            gid,
            year=year,
            meet_seq=1,
            home_team=game.get("home_team", ""),
            away_team=game.get("away_team", ""),
        )
        result["date"]      = game.get("date", "")
        result["home_team"] = game.get("home_team", "")
        result["away_team"] = game.get("away_team", "")
        result["home_score"] = game.get("home_score")
        result["away_score"] = game.get("away_score")

        existing[gid] = result

        event_count = len(result.get("events", []))
        logger.info(f"  └─ 이벤트 {event_count}개 수집")

        # 10경기마다 중간 저장
        if i % 10 == 0:
            save_events(existing, {"season": args.season})

        time.sleep(args.delay)

    save_events(existing, {"season": args.season})
    save_player_stats(existing, args.season)
    logger.info("전체 크롤링 완료")


if __name__ == "__main__":
    main()
