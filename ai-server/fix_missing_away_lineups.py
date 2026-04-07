"""
원정 라인업이 누락된 경기들을 meetSeq=1 단일 요청으로 재보완.

kleague.com match.do?meetSeq=1 페이지의 첫 4개 테이블:
  tables[0] = 홈 선발 11명
  tables[1] = 홈 벤치
  tables[2] = 원정 선발 11명
  tables[3] = 원정 벤치

사용법:
    python fix_missing_away_lineups.py               # 2013~2022
    python fix_missing_away_lineups.py --season 2022
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from loguru import logger

ROOT = Path(__file__).parent
POSITIONS = {"GK", "DF", "MF", "FW"}
BASE_URL = "https://www.kleague.com/match.do"


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "Referer": "https://www.kleague.com/",
    })
    return s


def _parse_player_table(table, team_name: str) -> list[dict]:
    """table → 선수 목록 파싱."""
    players = []
    for row in table.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) < 3:
            continue
        pos = tds[1].get_text(strip=True).upper()
        if pos not in POSITIONS:
            continue
        jersey = tds[0].get_text(strip=True)
        name_raw = tds[2].get_text(strip=True)
        name = re.split(r"[（\(\[]", name_raw)[0].replace("(c)", "").replace("(C)", "").strip()
        if name:
            players.append({"player": name, "team": team_name, "position": pos, "jersey": jersey})
    return players


def fetch_both_lineups(
    session: requests.Session,
    game_id: int,
    year: int,
    home_team: str,
    away_team: str,
    delay: float = 2.0,
) -> dict:
    """
    meetSeq=1 단일 요청으로 홈+원정 선발/벤치 파싱.
    tables[0]=홈선발, tables[1]=홈벤치, tables[2]=원정선발, tables[3]=원정벤치
    """
    time.sleep(delay)
    try:
        resp = session.get(
            BASE_URL,
            params={"year": str(year), "leagueId": "1", "gameId": str(game_id), "meetSeq": "1"},
            timeout=15,
        )
        resp.raise_for_status()
    except Exception as e:
        logger.warning(f"요청 실패 game_id={game_id}: {e}")
        return {}

    soup = BeautifulSoup(resp.content, "html.parser")
    tables = soup.find_all("table")

    # 선수 포함 테이블만 추출 (순서 유지)
    player_tables = []
    for t in tables:
        players = _parse_player_table(t, "")
        if players:
            player_tables.append(t)
        if len(player_tables) == 4:
            break

    if len(player_tables) < 3:
        logger.warning(f"테이블 부족 game_id={game_id}: {len(player_tables)}개")
        return {}

    home_starters = _parse_player_table(player_tables[0], home_team)
    home_bench    = _parse_player_table(player_tables[1], home_team) if len(player_tables) > 1 else []
    away_starters = _parse_player_table(player_tables[2], away_team)
    away_bench    = _parse_player_table(player_tables[3], away_team) if len(player_tables) > 3 else []

    return {
        "home": {"starters": home_starters, "bench": home_bench},
        "away": {"starters": away_starters, "bench": away_bench},
    }


def fix_season(session: requests.Session, season: int, delay: float) -> int:
    """원정 선발이 누락된 경기 보완. 업데이트 수 반환."""
    out_path = ROOT / "data" / "processed" / "matches" / f"match_lineups_{season}.json"
    if not out_path.exists():
        logger.warning(f"[{season}] 파일 없음")
        return 0

    data = json.loads(out_path.read_text(encoding="utf-8"))
    games = data.get("lineups_by_game", [])

    targets = [
        g for g in games
        if len(g.get("lineups", {}).get("home", {}).get("starters", [])) >= 11
        and len(g.get("lineups", {}).get("away", {}).get("starters", [])) < 11
    ]
    logger.info(f"[{season}] 원정 누락 경기: {len(targets)}개")
    if not targets:
        return 0

    updated = 0
    for i, game in enumerate(targets, 1):
        gid = game["game_id"]
        logger.info(
            f"[{season}] [{i}/{len(targets)}] game_id={gid} "
            f"{game.get('date')} {game.get('home_team')} vs {game.get('away_team')}"
        )

        lineups = fetch_both_lineups(
            session, gid, season,
            home_team=game.get("home_team", ""),
            away_team=game.get("away_team", ""),
            delay=delay,
        )
        if not lineups:
            continue

        away_count = len(lineups.get("away", {}).get("starters", []))
        home_count = len(lineups.get("home", {}).get("starters", []))
        logger.info(f"  └─ 홈 {home_count}명 / 원정 {away_count}명")

        if away_count >= 11:
            game["lineups"] = lineups
            updated += 1

        if i % 10 == 0:
            _save(data, out_path, season)

    _save(data, out_path, season)
    logger.info(f"[{season}] 완료: {updated}/{len(targets)} 업데이트")

    if updated > 0:
        from process_player_minutes import process_season
        process_season(season)
        from process_player_cleansheets import process_season as process_cs
        process_cs(season)
        logger.info(f"[{season}] 출전시간 + 클린시트 재계산 완료")

    return updated


def _save(data: dict, out_path: Path, season: int) -> None:
    out_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"저장: {out_path}")


def main():
    parser = argparse.ArgumentParser(description="원정 라인업 누락 경기 보완")
    parser.add_argument("--season",  type=int, default=None)
    parser.add_argument("--seasons", type=int, nargs="+")
    parser.add_argument("--delay",   type=float, default=2.0)
    args = parser.parse_args()

    logger.remove()
    logger.add(sys.stderr,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
               colorize=True)

    if args.seasons:
        seasons = args.seasons
    elif args.season:
        seasons = [args.season]
    else:
        seasons = list(range(2013, 2023))

    session = make_session()
    total_updated = 0
    for s in seasons:
        total_updated += fix_season(session, s, args.delay)

    logger.info(f"전체 완료: {total_updated}경기 업데이트")


if __name__ == "__main__":
    main()
