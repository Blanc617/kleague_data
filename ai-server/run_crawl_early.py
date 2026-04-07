"""
K리그1 2010~2012 초기 시즌 데이터 수집 스크립트.

데이터 소스: 영문 위키피디아 (kleague.com API가 해당 연도 미지원)
수집 항목:
  - 팀 경기 결과 (홈/어웨이 크로스테이블 파싱)
  - 득점 순위 (Top Scorers 테이블)
  ※ 골 이벤트(분 단위) 데이터 없음 → match_events는 스코어만 저장

실행:
    python run_crawl_early.py                    # 2010~2012 전체
    python run_crawl_early.py --seasons 2010     # 특정 연도만

위키피디아 페이지:
    2010: https://en.wikipedia.org/wiki/2010_K_League
    2011: https://en.wikipedia.org/wiki/2011_K_League
    2012: https://en.wikipedia.org/wiki/2012_K_League
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Optional

from loguru import logger

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

RESULTS_PATH = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
MATCHES_DIR  = ROOT / "data" / "processed" / "matches"
PLAYERS_DIR  = ROOT / "data" / "processed" / "players"

# ── 위키피디아 페이지 URL 맵 ────────────────────────────────────────────────
WIKI_URLS: dict[int, str] = {
    2010: "https://en.wikipedia.org/wiki/2010_K_League",
    2011: "https://en.wikipedia.org/wiki/2011_K_League",
    2012: "https://en.wikipedia.org/wiki/2012_K_League",
}

# ── 팀명 영→한 변환 맵 ────────────────────────────────────────────────────
EN_TO_KO: dict[str, str] = {
    "FC Seoul": "서울",
    "Jeonbuk Hyundai Motors": "전북",
    "Jeonbuk Hyundai Motors FC": "전북",
    "Ulsan Hyundai": "울산",
    "Ulsan HD FC": "울산",
    "Pohang Steelers": "포항",
    "Incheon United": "인천",
    "Incheon United FC": "인천",
    "Jeju United": "제주",
    "Jeju United FC": "제주",
    "Jeonnam Dragons": "전남",
    "Suwon Samsung Bluewings": "수원삼성",
    "Busan IPark": "부산",
    "Gyeongnam FC": "경남",
    "Daejeon Citizen": "대전",
    "Daejeon Hana Citizen": "대전",
    "Gwangju FC": "광주",
    "Gangwon FC": "강원",
    "Daegu FC": "대구",
    "Seongnam Ilhwa Chunma": "성남",
    "Seongnam FC": "성남",
    "Sangju Sangmu Phoenix": "상주",
    "Sangju Sangmu": "상주",
    "Gyeongnam": "경남",
    "Gwangju Sangmu": "광주",   # 상무가 광주로 이전하기 전
    "Chunnam Dragons": "전남",
    "Chonnam Dragons": "전남",
    "Suwon FC": "수원FC",
    "Daejeon": "대전",
}

# ── 팀 약어 (크로스테이블 헤더) → 팀명 매핑 ────────────────────────────
# 위키피디아 결과 크로스테이블 헤더는 3~4글자 약어를 사용
ABBR_MAP: dict[str, str] = {
    # 위키피디아 실제 약어 (크로스테이블 열 헤더)
    "SEO": "서울",
    "JHM": "전북",
    "USH": "울산",
    "PHS": "포항",
    "ICU": "인천",
    "JJU": "제주",
    "JND": "전남",
    "SSB": "수원삼성",
    "BIP": "부산",
    "GNM": "경남",
    "DJC": "대전",
    "GWJ": "광주",
    "GWN": "강원",
    "DGU": "대구",
    "SIC": "성남",
    "SSP": "상주", "SJS": "상주", "SSM": "상주",
    # 기타 대체 약어
    "FCS": "서울",
    "JBK": "전북", "JBM": "전북",
    "ULH": "울산",
    "ICH": "인천", "INU": "인천",
    "JEJ": "제주",
    "SWS": "수원삼성",
    "GYM": "경남",
    "GNG": "강원",
    "SNG": "성남",
    "DJN": "전남",
}


def abbr_to_ko(abbr: str, header_map: dict[str, str]) -> str:
    """약어를 한국어 팀명으로 변환합니다."""
    return header_map.get(abbr, ABBR_MAP.get(abbr, abbr))


def en_to_ko(name: str) -> str:
    """영어 팀명을 한국어로 변환합니다."""
    # 정확 일치
    if name in EN_TO_KO:
        return EN_TO_KO[name]
    # 부분 일치
    for en, ko in EN_TO_KO.items():
        if en in name:
            return ko
    return name


def load_existing_results() -> dict:
    if not RESULTS_PATH.exists():
        return {}
    records = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
    return {(r["season"], r.get("game_id", r.get("date","") + r.get("home_team",""))): r
            for r in records if r.get("season")}


def save_results(by_key: dict) -> None:
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    records = sorted(by_key.values(), key=lambda r: (r.get("season", 0), r.get("date", "")))
    RESULTS_PATH.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"k1_team_results 저장: {len(records)}경기")


def crawl_season(session, season: int, existing: dict) -> tuple[list[dict], list[dict]]:
    """
    위키피디아에서 시즌 데이터 크롤링.
    Returns: (match_results, player_stats)
    """
    from bs4 import BeautifulSoup

    url = WIKI_URLS.get(season)
    if not url:
        logger.warning(f"[Wikipedia] {season} URL 없음")
        return [], []

    try:
        r = session.get(url, timeout=20)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"[Wikipedia] {season} 수집 실패: {e}")
        return [], []

    soup = BeautifulSoup(r.text, "html.parser")
    tables = soup.find_all("table", class_="wikitable")
    logger.info(f"[{season}] wikitable {len(tables)}개 발견")

    match_results = _parse_results_table(tables, season)
    player_stats  = _parse_scorers_table(tables, season)

    logger.info(f"[{season}] 경기 결과 {len(match_results)}건, 선수 통계 {len(player_stats)}명 파싱")
    return match_results, player_stats


def _parse_results_table(tables, season: int) -> list[dict]:
    """
    홈/어웨이 크로스테이블 파싱.
    헤더 행: Home\Away | BIP | JND | ...
    데이터 행: BIP | — | 5–3 | 0–2 | ...
    """
    from bs4 import BeautifulSoup, Tag

    results = []
    game_id_counter = 1

    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        # "Home \ Away" 또는 "Home \\ Away" 패턴으로 크로스테이블 감지
        if not any("Home" in h and ("Away" in h or "\\" in h) for h in headers[:3]):
            continue

        rows = table.find_all("tr")
        if len(rows) < 4:
            continue

        # 열 헤더 (away팀 순서) 추출
        header_row = rows[0]
        col_headers = [th.get_text(strip=True) for th in header_row.find_all(["th", "td"])]
        # 첫 번째 열은 "Home\Away" 레이블 → 제거
        away_teams_raw = col_headers[1:]

        # 약어→팀명 매핑 구축 (이 테이블 전용)
        header_map: dict[str, str] = {}

        # 행 순회
        for row in rows[1:]:
            cells = row.find_all(["th", "td"])
            if not cells:
                continue

            home_raw = cells[0].get_text(strip=True)
            home_ko  = en_to_ko(home_raw) if len(home_raw) > 4 else abbr_to_ko(home_raw, header_map)

            if not home_ko or home_ko == home_raw:
                continue  # 팀명 변환 실패 → 스킵

            for j, cell in enumerate(cells[1:], 0):
                if j >= len(away_teams_raw):
                    break
                away_raw = away_teams_raw[j]
                away_ko  = en_to_ko(away_raw) if len(away_raw) > 4 else abbr_to_ko(away_raw, header_map)

                score_text = cell.get_text(strip=True)
                if score_text in ("—", "-", "", "–") or home_ko == away_ko:
                    continue

                hs, as_ = _parse_score(score_text)
                if hs is None:
                    continue

                results.append({
                    "game_id": game_id_counter,
                    "season": season,
                    "round": 0,
                    "date": f"{season}.00.00",  # 위키에는 날짜 없음
                    "competition": f"K리그 {season}",
                    "home_team": home_ko,
                    "away_team": away_ko,
                    "home_score": hs,
                    "away_score": as_,
                    "venue": "",
                    "finished": True,
                    "source": "wikipedia",
                })
                game_id_counter += 1

        if results:
            break  # 첫 번째 크로스테이블 파싱 완료

    return results


def _parse_scorers_table(tables, season: int) -> list[dict]:
    """Top Scorers 테이블 파싱."""
    for table in tables:
        headers = [th.get_text(strip=True) for th in table.find_all("th")]
        if "Goals" not in headers and "goals" not in " ".join(headers).lower():
            continue

        rows = table.find_all("tr")
        stats = []
        for row in rows[1:]:
            cells = [td.get_text(strip=True) for td in row.find_all(["th", "td"])]
            if len(cells) < 3:
                continue
            try:
                # 형식: Rank | Player | Club | Goals
                rank   = cells[0]
                player = cells[1]
                club   = cells[2]
                goals  = int(cells[3]) if len(cells) > 3 and cells[3].isdigit() else 0
                if not player or not goals:
                    continue
                stats.append({
                    "team": en_to_ko(club),
                    "player_name": player,
                    "appearances": 0,   # 위키에 없음
                    "goals": goals,
                    "assists": 0,
                    "own_goals": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                })
            except Exception:
                continue

        if stats:
            return stats

    return []


def _parse_score(text: str) -> tuple[Optional[int], Optional[int]]:
    """'2-1', '2–1', '2:1' 형태 파싱. 실패 시 (None, None)."""
    text = text.strip().split("\n")[0].split("(")[0].strip()
    for sep in ("–", "-", ":"):
        if sep in text:
            parts = text.split(sep)
            if len(parts) == 2:
                try:
                    return int(parts[0].strip()), int(parts[1].strip())
                except ValueError:
                    pass
    return None, None


def process_season(session, season: int, existing_results: dict) -> None:
    """시즌 데이터 수집 → 저장."""
    logger.info(f"\n  ── {season} 시즌 ──")

    match_results, player_stats = crawl_season(session, season, existing_results)

    if not match_results:
        logger.warning(f"  [{season}] 경기 결과 없음")
        return

    # k1_team_results에 병합
    added = 0
    for r in match_results:
        key = (season, r["game_id"])
        if key not in existing_results:
            existing_results[key] = r
            added += 1
    logger.info(f"  [{season}] 팀 결과 {added}건 추가")
    save_results(existing_results)

    # match_events_{season}.json 저장 (이벤트 없이 스코어만)
    events_by_game = []
    for r in match_results:
        events_by_game.append({
            "game_id": r["game_id"],
            "date":       r["date"],
            "home_team":  r["home_team"],
            "away_team":  r["away_team"],
            "home_score": r["home_score"],
            "away_score": r["away_score"],
            "events": [],   # 위키피디아에 분 단위 이벤트 없음
        })

    out_path = MATCHES_DIR / f"match_events_{season}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({
        "season": season,
        "league": "K1",
        "source": "wikipedia",
        "note": "골 이벤트(분 단위) 없음 — 위키피디아 소스 한계",
        "total_games": len(events_by_game),
        "events_by_game": events_by_game,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"  match_events_{season}.json 저장: {len(events_by_game)}경기")

    # player_stats_{season}.json 저장
    if player_stats:
        stats_path = PLAYERS_DIR / f"player_stats_{season}.json"
        stats_path.parent.mkdir(parents=True, exist_ok=True)
        stats_path.write_text(json.dumps({
            "season": season,
            "league": "K1",
            "source": "wikipedia",
            "note": "출장수·도움·카드 없음 — 위키피디아 상위 득점자만 포함",
            "total_players": len(player_stats),
            "players": player_stats,
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info(f"  player_stats_{season}.json 저장: {len(player_stats)}명")
    else:
        logger.warning(f"  [{season}] 선수 통계 없음")


def _make_session():
    import requests
    s = requests.Session()
    s.headers.update({
        "User-Agent": "Mozilla/5.0 (compatible; KLeagueResearch/1.0)",
        "Accept-Language": "ko,en;q=0.9",
    })
    return s


def main():
    parser = argparse.ArgumentParser(
        description="K리그 2010~2012 위키피디아 데이터 수집",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--seasons", type=int, nargs="+",
        default=[2010, 2011, 2012],
        help="수집할 시즌 (기본: 2010~2012)",
    )
    args = parser.parse_args()

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    session = _make_session()
    existing = load_existing_results()
    logger.info(f"기존 경기 수: {len(existing)}")
    logger.info(f"수집 시즌: {args.seasons}")

    for season in args.seasons:
        if season not in WIKI_URLS:
            logger.warning(f"  {season}: 지원 범위 외 (2010~2012만 가능)")
            continue
        process_season(session, season, existing)
        time.sleep(1)  # Wikipedia 요청 간격

    logger.info("\n=== 완료 ===")
    for season in args.seasons:
        e = MATCHES_DIR / f"match_events_{season}.json"
        p = PLAYERS_DIR / f"player_stats_{season}.json"
        if e.exists():
            data = json.loads(e.read_text(encoding="utf-8"))
            logger.info(f"  {season}: {data['total_games']}경기 (이벤트 없음)")
        if p.exists():
            data = json.loads(p.read_text(encoding="utf-8"))
            logger.info(f"  {season}: 선수 {data['total_players']}명")


if __name__ == "__main__":
    main()
