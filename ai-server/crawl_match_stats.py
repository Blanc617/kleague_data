"""
K리그 공식 API에서 경기별 통계 수집 스크립트.

수집 항목 (경기당):
  - possession (점유율 %)
  - attempts (총 슈팅)
  - onTarget (유효슈팅)
  - corners (코너킥)
  - fouls (파울)
  - freeKicks (프리킥)
  - yellowCards / redCards / doubleYellowCards
  - offsides (오프사이드)

출처: https://www.kleague.com/api/ddf/match/matchRecord.do
      POST 파라미터: year, meetSeq, gameId

입력: data/processed/matches/match_events_{year}.json (game_id 목록)
출력: data/processed/matches/match_stats_{year}.json

사용법:
  python crawl_match_stats.py              # 전 시즌
  python crawl_match_stats.py --year 2026  # 특정 시즌
  python crawl_match_stats.py --dry-run    # 2026년 처음 10경기만 테스트
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from loguru import logger

sys.stderr.reconfigure(encoding="utf-8")
logger.remove()
logger.add(sys.stderr, format="<green>{time:HH:mm:ss}</green> | {level} | {message}")

BASE_DIR    = Path(__file__).parent
MATCHES_DIR = BASE_DIR / "data" / "processed" / "matches"
STATS_API   = "https://www.kleague.com/api/ddf/match/matchRecord.do"
DELAY       = 1.2   # 요청 간 딜레이 (초)

HEADERS = {
    "User-Agent":     "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer":        "https://www.kleague.com/",
    "Accept":         "application/json, text/javascript, */*; q=0.01",
    "X-Requested-With": "XMLHttpRequest",
}


# ── 세션 관리 ─────────────────────────────────────────────────────────

def make_session() -> requests.Session:
    """JSESSIONID 쿠키가 있는 세션 생성."""
    sess = requests.Session()
    sess.headers.update(HEADERS)
    sess.get("https://www.kleague.com/", timeout=12)
    return sess


# ── API 호출 ──────────────────────────────────────────────────────────

def fetch_stats(sess: requests.Session, game_id: int, year: int,
                meet_seq: int = 1, retries: int = 2) -> dict | None:
    """
    경기 통계 반환. 실패 시 None.
    반환 형식:
      {"home": {...}, "away": {...}}
    """
    payload = {"year": str(year), "meetSeq": str(meet_seq), "gameId": str(game_id)}

    for attempt in range(retries + 1):
        try:
            r = sess.post(STATS_API, data=payload, timeout=12)
            if r.status_code == 429:
                logger.warning(f"429 rate limit — game_id={game_id}, 30초 대기")
                time.sleep(30)
                continue
            if not r.ok:
                return None
            data = r.json()
            if data.get("resultCode") != "200":
                return None
            inner = data.get("data", {})
            if not inner or not inner.get("home"):
                return None
            return inner
        except Exception as e:
            logger.debug(f"fetch_stats 실패 (attempt {attempt+1}): game_id={game_id} | {e}")
            if attempt < retries:
                time.sleep(3)
    return None


# ── 시즌 처리 ─────────────────────────────────────────────────────────

def process_season(year: int, sess: requests.Session, dry_run: bool = False) -> int:
    """
    한 시즌의 모든 경기 통계 수집 → match_stats_{year}.json 저장/업데이트.
    이미 수집된 game_id는 건너뜀.
    반환: 새로 수집한 경기 수
    """
    events_path = MATCHES_DIR / f"match_events_{year}.json"
    if not events_path.exists():
        logger.warning(f"{year}: match_events 없음 — 스킵")
        return 0

    events_data = json.loads(events_path.read_text(encoding="utf-8"))
    games = events_data.get("events_by_game", [])
    if not games:
        logger.info(f"{year}: 경기 없음")
        return 0

    # 기존 통계 로드
    stats_path = MATCHES_DIR / f"match_stats_{year}.json"
    existing: dict[int, dict] = {}
    if stats_path.exists():
        saved = json.loads(stats_path.read_text(encoding="utf-8"))
        for item in saved.get("stats", []):
            existing[item["game_id"]] = item

    targets = [g for g in games if g.get("game_id") and g["game_id"] not in existing]

    logger.info(f"{year}: 전체 {len(games)}경기 중 미수집 {len(targets)}경기")

    if dry_run:
        targets = targets[:10]
        logger.info(f"[DRY-RUN] 처음 {len(targets)}경기만 처리")

    added = 0
    for i, game in enumerate(targets, 1):
        gid = game["game_id"]
        stats = fetch_stats(sess, gid, year)

        if stats:
            existing[gid] = {
                "game_id":    gid,
                "home_team":  game.get("home_team", ""),
                "away_team":  game.get("away_team", ""),
                "date":       game.get("date", ""),
                "home":       stats["home"],
                "away":       stats["away"],
            }
            added += 1
            if i % 20 == 0 or i == len(targets):
                logger.info(f"  {year}: {i}/{len(targets)} 처리 | 수집 {added}경기")
        else:
            logger.debug(f"  {year} game_id={gid}: 통계 없음")

        time.sleep(DELAY)

    # 저장
    if not dry_run and added > 0:
        out = {
            "season":       year,
            "source":       "kleague_official",
            "crawled_at":   datetime.now().strftime("%Y-%m-%d %H:%M"),
            "total_games":  len(existing),
            "stats":        sorted(existing.values(), key=lambda x: x["game_id"]),
        }
        stats_path.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.success(f"{year}: {len(existing)}경기 통계 저장 → {stats_path.name}")
    elif dry_run:
        logger.info(f"[DRY-RUN] 샘플 (처음 3경기):")
        for item in list(existing.values())[:3]:
            h, a = item["home"], item["away"]
            name = f'{item["home_team"]} vs {item["away_team"]}'
            sys.stdout.buffer.write(
                f"  {name}: 점유율 {h['possession']}% vs {a['possession']}% | "
                f"슈팅 {h['attempts']} vs {a['attempts']} | "
                f"코너 {h['corners']} vs {a['corners']}\n"
                .encode("utf-8")
            )

    return added


# ── 메인 ──────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year",     type=int, default=None, help="특정 시즌만 수집")
    parser.add_argument("--dry-run",  action="store_true",    help="2026년 처음 10경기만 테스트")
    parser.add_argument("--from-year",type=int, default=2010, help="시작 시즌 (기본 2010)")
    parser.add_argument("--to-year",  type=int, default=2026, help="종료 시즌 (기본 2026)")
    args = parser.parse_args()

    sess = make_session()
    logger.info(f"세션 생성 완료 (JSESSIONID: {sess.cookies.get('JSESSIONID','없음')[:8]}...)")

    if args.dry_run:
        process_season(2026, sess, dry_run=True)
        return

    if args.year:
        seasons = [args.year]
    else:
        seasons = list(range(args.from_year, args.to_year + 1))

    total_added = 0
    for year in seasons:
        added = process_season(year, sess)
        total_added += added

    logger.info(f"전체 완료 — 새로 수집: {total_added}경기")


if __name__ == "__main__":
    main()
