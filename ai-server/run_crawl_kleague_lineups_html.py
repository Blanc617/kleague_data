"""
kleague.com match.do HTML 페이지에서 선발 라인업을 수집합니다.
matchInfo.do API와 달리 HTML 페이지에는 GK/DF/MF/FW 포지션 + 선수명이 있습니다.

파싱 규칙:
  - match.do?year=Y&leagueId=1&gameId=G&meetSeq=1
  - .match-lineup-player 가 2개 (home, away)
  - 각 내부의 첫 번째 <table>의 <tbody> rows → 선발 선수 (11명)
  - td[0]=등번호, td[1]=포지션(GK/DF/MF/FW), td[2]=이름(생년)...

사용법:
    python run_crawl_kleague_lineups_html.py                  # 2025
    python run_crawl_kleague_lineups_html.py --season 2024
    python run_crawl_kleague_lineups_html.py --limit 10
    python run_crawl_kleague_lineups_html.py --force
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")

BASE_URL = "https://www.kleague.com/match.do"
POSITIONS = {"GK", "DF", "MF", "FW"}


def _parse_minute(raw: str) -> int:
    """'90+1' → 90, '81' → 81"""
    if not raw:
        return 0
    return int(re.split(r"[+\-]", raw.strip())[0])


def _parse_substitutions_from_html(html: str, starter_ids: set[str], player_id_to_name: dict[str, str], team_name: str) -> list[dict]:
    """
    raw HTML에서 교체 이벤트 파싱.
    starter_ids에 있는 선수(선발)의 changeM만 처리해 중복 방지.
    changeM_PLAYERID → 교체 아웃 시간
    changeP_PLAYERID → 교체 투입 선수명
    """
    subs = []
    for player_id in starter_ids:
        m_minute = re.search(rf'changeM_{player_id}">([^<]*)</p>', html)
        m_partner = re.search(rf'changeP_{player_id}">([^<]*)</p>', html)
        if not m_minute:
            continue
        minute_raw = m_minute.group(1).strip()
        if not minute_raw:
            continue
        player_on_raw = m_partner.group(1).strip() if m_partner else ""
        subs.append({
            "minute":     _parse_minute(minute_raw),
            "team":       team_name,
            "player_off": player_id_to_name.get(player_id, ""),
            "player_on":  player_on_raw,
        })
    return subs


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


def fetch_match_lineup(
    session: requests.Session,
    game_id: int,
    year: int,
    home_team: str = "",
    away_team: str = "",
) -> tuple[dict, list[dict]]:
    """
    kleague.com match.do HTML 파싱 → 홈/어웨이 선발 라인업 + 교체 이벤트 반환.

    meetSeq=1 → 홈팀 라인업 페이지
    meetSeq=2 → 원정팀 라인업 페이지 (별도 요청 필요)

    반환: (
        {"home": {"starters": [...], "bench": []}, "away": {...}},
        [{"minute": int, "team": str, "player_off": str, "player_on": str}, ...]
    )
    """
    url = BASE_URL
    lineups = {}
    substitutions = []

    for meet_seq, side, team_name in (
        ("1", "home", home_team),
        ("2", "away", away_team),
    ):
        params = {"year": str(year), "leagueId": "1", "gameId": str(game_id), "meetSeq": meet_seq}
        try:
            resp = session.get(url, params=params, timeout=15)
            resp.raise_for_status()
        except Exception as e:
            logger.warning(f"[HTML] 페이지 요청 실패: game_id={game_id} meetSeq={meet_seq} | {e}")
            continue

        soup = BeautifulSoup(resp.content, "html.parser")
        mlps = soup.select(".match-lineup-player")
        if not mlps:
            logger.warning(f"[HTML] 라인업 섹션 없음: game_id={game_id} meetSeq={meet_seq}")
            continue

        starters = _parse_starters(mlps[0], team_name)
        bench = _parse_bench(mlps[0], team_name)
        if starters:
            lineups[side] = {"starters": starters, "bench": bench}

        # 교체 데이터 파싱: mlps[0]의 선발 선수 ID만 대상으로 처리
        player_id_to_name: dict[str, str] = {}
        starter_ids: set[str] = set()
        starter_table_rows = mlps[0].find_all("table")[0].find_all("tr") if mlps[0].find_all("table") else []
        for tr in starter_table_rows:
            onclick = tr.get("onclick", "")
            m = re.search(r"playerDetailPop\('[^']*',\s*'(\d+)'\)", onclick)
            if not m:
                continue
            pid = m.group(1)
            starter_ids.add(pid)
            tds = tr.find_all("td")
            if len(tds) >= 3:
                name_raw = tds[2].get_text(strip=True)
                name = re.split(r"[（\(\[]", name_raw)[0].replace("(c)", "").replace("(C)", "").strip()
                if name:
                    player_id_to_name[pid] = name

        html = resp.text
        subs = _parse_substitutions_from_html(html, starter_ids, player_id_to_name, team_name)
        substitutions.extend(subs)

    substitutions.sort(key=lambda s: s["minute"])
    return lineups, substitutions



def _parse_player_rows(rows, team_name: str) -> list[dict]:
    """table rows → 선수 목록 파싱."""
    players = []
    for row in rows:
        tds = row.find_all("td")
        if len(tds) < 3:
            continue
        pos = tds[1].get_text(strip=True).upper()
        if pos not in POSITIONS:
            continue

        jersey = tds[0].get_text(strip=True)
        name_raw = tds[2].get_text(strip=True)
        # 괄호 및 통계 제거: '이광연(99)출전:13/평점:1.00' → '이광연'
        name = re.split(r"[（\(\[]", name_raw)[0].strip()
        # 주장 표시 제거
        name = name.replace("(c)", "").replace("(C)", "").strip()

        if name:
            players.append({
                "player":   name,
                "team":     team_name,
                "position": pos,
                "jersey":   jersey,
            })
    return players


def _parse_starters(mlp, team_name: str) -> list[dict]:
    """
    match-lineup-player 요소에서 선발 선수 파싱.
    첫 번째 table의 첫 번째 tbody = 선발 11명.
    """
    tables = mlp.find_all("table")
    if not tables:
        return []

    rows = tables[0].find_all("tr")
    return _parse_player_rows(rows, team_name)


def _parse_bench(mlp, team_name: str) -> list[dict]:
    """
    match-lineup-player 요소에서 벤치 선수 파싱.
    두 번째 table = 벤치/후보 선수.
    """
    tables = mlp.find_all("table")
    if len(tables) < 2:
        return []

    rows = tables[1].find_all("tr")
    return _parse_player_rows(rows, team_name)


def load_kleague_games(season: int) -> list[dict]:
    """
    완료된 경기 목록 로드.
    k1_team_results.json + match_events_{season}.json 를 합산해 game_id 누락 방지.
    (2013·2014처럼 k1_team_results에 일부 경기만 있는 시즌을 위해 항상 보완)
    """
    seen: set[int] = set()
    unique: list[dict] = []

    # 1) k1_team_results.json (round/finished 정보 우선)
    results_path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    if results_path.exists():
        records = json.loads(results_path.read_text(encoding="utf-8"))
        for r in records:
            gid = r.get("game_id")
            if gid and gid not in seen and r.get("season") == season and r.get("finished"):
                seen.add(gid)
                unique.append(r)

    # 2) match_events_{season}.json 로 보완 (generated 데이터 제외)
    events_path = ROOT / "data" / "processed" / "matches" / f"match_events_{season}.json"
    if events_path.exists():
        data = json.loads(events_path.read_text(encoding="utf-8"))
        if data.get("source") != "generated" and data.get("source") != "wikipedia":
            for g in data.get("events_by_game", []):
                gid = g.get("game_id")
                if gid and gid not in seen:
                    seen.add(gid)
                    unique.append({
                        "game_id":    gid,
                        "season":     season,
                        "round":      g.get("round", 0),
                        "date":       g.get("date", ""),
                        "home_team":  g.get("home_team", ""),
                        "away_team":  g.get("away_team", ""),
                        "home_score": g.get("home_score"),
                        "away_score": g.get("away_score"),
                        "finished":   True,
                    })

    unique.sort(key=lambda r: (r.get("date", ""), r.get("game_id", 0)))
    return unique


def load_existing(out_path: Path) -> dict[int, dict]:
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
    logger.info(f"저장: {out_path} ({len(lineups_by_game)}경기)")


def crawl_season(
    session,
    season: int,
    force: bool = False,
    limit: int = 0,
    delay: float = 2.0,
) -> None:
    """단일 시즌 라인업 크롤링."""
    out_path = ROOT / "data" / "processed" / "matches" / f"match_lineups_{season}.json"

    games = load_kleague_games(season)
    if not games:
        logger.warning(f"[{season}] 경기 데이터 없음 — 스킵")
        return

    if limit:
        games = games[:limit]

    existing = {} if force else load_existing(out_path)
    logger.info(f"[{season}] 대상 {len(games)}경기 / 기존 보유 {len(existing)}경기")

    updated = 0
    for i, game in enumerate(games, 1):
        gid = game["game_id"]
        if not force and gid in existing:
            existing_lu = existing[gid].get("lineups", {})
            home_bench = existing_lu.get("home", {}).get("bench", [])
            away_bench = existing_lu.get("away", {}).get("bench", [])
            has_starters = (
                existing_lu.get("home", {}).get("starters")
                or existing_lu.get("away", {}).get("starters")
            )
            if has_starters and home_bench and away_bench:
                logger.debug(f"[{season}] 스킵: game_id={gid}")
                continue
            if has_starters:
                logger.info(f"[{season}] 벤치 없음 → 재수집: game_id={gid}")

        logger.info(
            f"[{season}] [{i}/{len(games)}] game_id={gid}  "
            f"{game.get('date')} {game.get('home_team')} vs {game.get('away_team')}"
        )

        lineups, substitutions = fetch_match_lineup(
            session, gid,
            game.get("season", season),
            home_team=game.get("home_team", ""),
            away_team=game.get("away_team", ""),
        )

        home_count = len(lineups.get("home", {}).get("starters", []))
        away_count = len(lineups.get("away", {}).get("starters", []))
        logger.info(f"  └─ 홈 {home_count}명 / 어웨이 {away_count}명 선발 / 교체 {len(substitutions)}건")

        if gid in existing:
            existing[gid]["lineups"] = lineups
            existing[gid]["substitutions"] = substitutions
            # score/round를 k1_team_results 기준으로 동기화
            if game.get("home_score") is not None:
                existing[gid]["home_score"] = game["home_score"]
            if game.get("away_score") is not None:
                existing[gid]["away_score"] = game["away_score"]
            if game.get("round"):
                existing[gid]["round"] = game["round"]
        else:
            existing[gid] = {
                "game_id":       gid,
                "season":        game.get("season", season),
                "round":         game.get("round"),
                "date":          game.get("date", ""),
                "home_team":     game.get("home_team", ""),
                "away_team":     game.get("away_team", ""),
                "home_score":    game.get("home_score"),
                "away_score":    game.get("away_score"),
                "lineups":       lineups,
                "substitutions": substitutions,
            }
        updated += 1

        if i % 10 == 0:
            save_lineups(existing, season, out_path)

        time.sleep(delay)

    save_lineups(existing, season, out_path)
    logger.info(f"[{season}] 완료: {updated}경기 업데이트")

    if updated > 0:
        from process_player_minutes import process_season
        process_season(season)
        from process_player_cleansheets import process_season as process_cs
        process_cs(season)
        logger.info(f"[{season}] 출전시간 + 클린시트 재계산 완료")


def main():
    parser = argparse.ArgumentParser(description="K리그 HTML 라인업 크롤러")
    parser.add_argument("--season",  type=int,   default=None,  help="단일 시즌 (기본: 2025)")
    parser.add_argument("--seasons", type=int,   nargs="+",     help="여러 시즌 (예: --seasons 2024 2025 2026)")
    parser.add_argument("--limit",   type=int,   default=0,     help="시즌당 최대 경기 수 (0=전체)")
    parser.add_argument("--delay",   type=float, default=2.0,   help="요청 간 딜레이(초)")
    parser.add_argument("--force",   action="store_true",       help="기존 라인업도 재수집")
    args = parser.parse_args()

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    if args.seasons:
        seasons = args.seasons
    elif args.season:
        seasons = [args.season]
    else:
        seasons = [2025]

    session = make_session()
    logger.info(f"크롤링 시즌: {seasons}")

    for season in seasons:
        crawl_season(session, season, force=args.force, limit=args.limit, delay=args.delay)

    logger.info("전체 완료")


if __name__ == "__main__":
    main()
