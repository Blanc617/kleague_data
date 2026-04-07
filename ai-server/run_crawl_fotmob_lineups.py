"""
FotMob에서 K리그1 경기 라인업을 수집해 match_lineups_{season}.json 에 병합 저장합니다.

흐름:
  1. FotMob /api/leagues 로 시즌 경기 목록 + FotMob match ID 수집
  2. k1_team_results.json 와 날짜+팀명으로 매핑 (kleague game_id 연결)
  3. /api/matchDetails 로 경기별 라인업 수집
  4. match_lineups_{season}.json 에 라인업 필드 업데이트

사용법:
    python run_crawl_fotmob_lineups.py                  # 2025 전체
    python run_crawl_fotmob_lineups.py --season 2024
    python run_crawl_fotmob_lineups.py --limit 10       # 최근 10경기
    python run_crawl_fotmob_lineups.py --force          # 이미 수집된 것도 재크롤
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


def load_kleague_games(season: int) -> list[dict]:
    """k1_team_results.json 에서 완료된 경기 목록 로드."""
    path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    if not path.exists():
        logger.error(f"경기 결과 파일 없음: {path}")
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    seen, unique = set(), []
    for r in records:
        gid = r.get("game_id")
        if gid and gid not in seen and r.get("season") == season and r.get("finished"):
            seen.add(gid)
            unique.append(r)
    return unique


def load_existing_lineups(out_path: Path) -> dict[int, dict]:
    """기존 match_lineups 파일 로드. key=game_id."""
    if not out_path.exists():
        return {}
    data = json.loads(out_path.read_text(encoding="utf-8"))
    return {item["game_id"]: item for item in data.get("lineups_by_game", [])}


def save_lineups(lineups_by_game: dict[int, dict], season: int, out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season": season,
        "league": "K1",
        "total_games": len(lineups_by_game),
        "lineups_by_game": list(lineups_by_game.values()),
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"저장 완료: {out_path} ({len(lineups_by_game)}경기)")


def match_fotmob_to_kleague(
    fotmob_matches: list[dict],
    kleague_games: list[dict],
) -> dict[int, int]:
    """
    FotMob 경기 ↔ kleague game_id 매핑.
    날짜(YYYY.MM.DD)와 팀명(부분 일치)으로 연결.
    반환: {fotmob_id: game_id}
    """
    mapping: dict[int, int] = {}

    for fm in fotmob_matches:
        fm_date = fm["date"]   # YYYY.MM.DD
        fm_home = fm["home"]
        fm_away = fm["away"]

        for kl in kleague_games:
            kl_date = kl.get("date", "")
            # 날짜 앞 10자리 비교 (YYYY.MM.DD)
            if kl_date[:10] != fm_date[:10]:
                continue
            kl_home = kl.get("home_team", "")
            kl_away = kl.get("away_team", "")

            # 팀명 유사도: FotMob short_name과 kleague 팀명이 겹치면 매핑
            def similar(a: str, b: str) -> bool:
                a, b = a.strip(), b.strip()
                return a == b or a in b or b in a

            if similar(fm_home, kl_home) and similar(fm_away, kl_away):
                mapping[fm["fotmob_id"]] = kl["game_id"]
                break

    return mapping


def main():
    parser = argparse.ArgumentParser(description="FotMob K리그 라인업 크롤러")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--limit",  type=int, default=0, help="최대 경기 수 (0=전체)")
    parser.add_argument("--delay",  type=float, default=1.5, help="경기 간 딜레이(초)")
    parser.add_argument("--force",  action="store_true", help="기존 라인업도 재수집")
    args = parser.parse_args()

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    out_path  = ROOT / "data" / "processed" / "matches" / f"match_lineups_{args.season}.json"
    raw_cache = ROOT / "data" / "raw" / "fotmob"
    raw_cache.mkdir(parents=True, exist_ok=True)

    from crawlers.sources.fotmob_crawler import FotmobCrawler
    crawler = FotmobCrawler(raw_cache_dir=raw_cache)

    if not crawler.is_available():
        logger.error("FotMob 접근 불가 — 네트워크 확인")
        sys.exit(1)

    # ── 1. FotMob 시즌 경기 목록 ─────────────────────
    logger.info(f"FotMob에서 {args.season}시즌 경기 목록 수집 중...")
    fotmob_matches = crawler.fetch_season_matches(args.season)
    finished = [m for m in fotmob_matches if m["finished"]]
    logger.info(f"완료된 경기: {len(finished)}/{len(fotmob_matches)}")

    if not finished:
        logger.warning("수집된 경기 없음")
        sys.exit(0)

    # ── 2. kleague game_id 매핑 ───────────────────────
    kleague_games = load_kleague_games(args.season)
    logger.info(f"kleague 완료 경기: {len(kleague_games)}")

    mapping = match_fotmob_to_kleague(finished, kleague_games)
    logger.info(f"매핑 성공: {len(mapping)}/{len(finished)}경기")

    # 매핑된 경기만 대상
    targets = [m for m in finished if m["fotmob_id"] in mapping]
    if args.limit:
        targets = targets[:args.limit]

    # ── 3. 기존 라인업 로드 ───────────────────────────
    existing = load_existing_lineups(out_path)
    logger.info(f"기존 라인업 보유: {len(existing)}경기")

    # kleague_games를 game_id로 빠르게 조회
    kl_by_id = {g["game_id"]: g for g in kleague_games}

    updated = 0
    for i, fm in enumerate(targets, 1):
        fotmob_id = fm["fotmob_id"]
        game_id   = mapping[fotmob_id]
        kl        = kl_by_id[game_id]

        # 이미 라인업 있으면 스킵 (--force 제외)
        # 단, bench가 비어있으면 재수집 (데이터 결함 보완)
        if not args.force and game_id in existing:
            existing_lu = existing[game_id].get("lineups", {})
            home_bench = existing_lu.get("home", {}).get("bench", [])
            away_bench = existing_lu.get("away", {}).get("bench", [])
            has_starters = (
                existing_lu.get("home", {}).get("starters")
                or existing_lu.get("away", {}).get("starters")
            )
            if has_starters and home_bench and away_bench:
                logger.debug(f"스킵 (라인업+벤치 보유): game_id={game_id}")
                continue
            if has_starters:
                logger.info(f"벤치 없음 → 재수집: game_id={game_id}")

        logger.info(
            f"[{i}/{len(targets)}] game_id={game_id} fotmob_id={fotmob_id}  "
            f"{kl.get('date')} {kl.get('home_team')} vs {kl.get('away_team')}"
        )

        result = crawler.fetch_match_lineup(fotmob_id)

        # 기존 레코드 업데이트 또는 신규 생성
        if game_id in existing:
            existing[game_id]["lineups"]       = result["lineups"]
            existing[game_id]["substitutions"] = result["substitutions"] or existing[game_id].get("substitutions", [])
            # score/round를 k1_team_results 기준으로 동기화
            if kl.get("home_score") is not None:
                existing[game_id]["home_score"] = kl["home_score"]
            if kl.get("away_score") is not None:
                existing[game_id]["away_score"] = kl["away_score"]
            if kl.get("round"):
                existing[game_id]["round"] = kl["round"]
        else:
            existing[game_id] = {
                "game_id":       game_id,
                "season":        kl.get("season", args.season),
                "round":         kl.get("round"),
                "date":          kl.get("date", ""),
                "home_team":     kl.get("home_team", ""),
                "away_team":     kl.get("away_team", ""),
                "home_score":    kl.get("home_score"),
                "away_score":    kl.get("away_score"),
                "lineups":       result["lineups"],
                "substitutions": result["substitutions"],
                "fotmob_id":     fotmob_id,
            }

        starter_count = (
            len(result["lineups"].get("home", {}).get("starters", []))
            + len(result["lineups"].get("away", {}).get("starters", []))
        )
        sub_count = len(result["substitutions"])
        logger.info(f"  └─ 선수 {starter_count}명 선발, 교체 {sub_count}건")
        updated += 1

        if i % 10 == 0:
            save_lineups(existing, args.season, out_path)

        time.sleep(args.delay)

    save_lineups(existing, args.season, out_path)
    logger.info(f"라인업 업데이트: {updated}경기")

    # ── 4. 출전시간 + 클린시트 재계산 ────────────────
    if updated > 0:
        from process_player_minutes import process_season
        process_season(args.season)

        from process_player_cleansheets import process_season as process_cs
        process_cs(args.season)
        logger.info("출전시간 + 클린시트 재계산 완료")


if __name__ == "__main__":
    main()
