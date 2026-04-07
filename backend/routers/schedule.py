"""
/api/schedule  — 경기 일정/결과 조회 엔드포인트 (2010~2026)
"""

import json
from pathlib import Path
from functools import lru_cache

from fastapi import APIRouter, HTTPException

router = APIRouter()

MATCHES_DIR = Path(__file__).parent.parent.parent / "ai-server" / "data" / "processed" / "matches"
TEAMS_DIR   = Path(__file__).parent.parent.parent / "ai-server" / "data" / "processed" / "teams"

# 홈팀 → 경기장 정적 매핑 (venue 데이터 없는 시즌용 폴백)
HOME_VENUE: dict[str, str] = {
    "전북": "전주월드컵경기장",
    "울산": "울산문수경기장",
    "포항": "포항스틸야드",
    "서울": "서울월드컵경기장",
    "수원FC": "수원종합경기장",
    "제주": "제주월드컵경기장",
    "인천": "인천축구전용경기장",
    "광주": "광주축구전용경기장",
    "대구": "DGB대구은행파크",
    "강원": "강릉종합경기장",
    "김천": "김천종합경기장",
    "대전": "대전월드컵경기장",
    "성남": "탄천종합운동장",
    "수원": "수원월드컵경기장",
    "전남": "광양전용구장",
    "부산": "부산아시아드경기장",
    "안양": "안양종합경기장",
}


def _load_season_stats(season: int) -> dict[int, dict]:
    """match_stats_{season}.json 로드 → {game_id: {home:{...}, away:{...}}}"""
    stats_path = MATCHES_DIR / f"match_stats_{season}.json"
    if not stats_path.exists():
        return {}
    data = json.loads(stats_path.read_text(encoding="utf-8"))
    return {item["game_id"]: item for item in data.get("stats", [])}


def _load_season(season: int) -> list[dict]:
    """경기 일정 데이터 로드.
    우선순위: k1_team_results.json (실제 크롤링) → match_events (이벤트 보강).
    match_events가 generated 데이터이면 이벤트는 제외.
    """
    # 1) k1_team_results.json에서 해당 시즌 경기 로드 (기본 일정/스코어)
    results_path = TEAMS_DIR / "k1_team_results.json"
    games_by_id: dict[int, dict] = {}

    if results_path.exists():
        records = json.loads(results_path.read_text(encoding="utf-8"))
        for r in records:
            if r.get("season") == season:
                gid = r.get("game_id")
                if gid:
                    finished = r.get("finished", True)
                    games_by_id[gid] = {
                        "game_id":    gid,
                        "season":     season,
                        "round":      r.get("round"),
                        "date":       r.get("date", ""),
                        "home_team":  r.get("home_team", ""),
                        "away_team":  r.get("away_team", ""),
                        "home_score": r.get("home_score") if finished else None,
                        "away_score": r.get("away_score") if finished else None,
                        "finished":   finished,
                        "venue":      r.get("venue", ""),
                        "events":     [],
                        "stats":      None,
                    }

    # 2) match_events에서 이벤트(골/도움 등) 보강 — generated 데이터는 제외
    events_path = MATCHES_DIR / f"match_events_{season}.json"
    if events_path.exists():
        raw = json.loads(events_path.read_text(encoding="utf-8"))
        if raw.get("source") != "generated":
            for g in raw.get("events_by_game", []):
                gid = g.get("game_id")
                if gid and gid in games_by_id:
                    games_by_id[gid]["events"] = g.get("events", [])
                elif gid and gid not in games_by_id:
                    # k1_team_results에 없는 경기라면 events에서 추가
                    g["season"] = season
                    g.setdefault("stats", None)
                    games_by_id[gid] = g

    # 3) match_stats에서 경기 통계(점유율·슈팅·코너킥 등) 보강
    season_stats = _load_season_stats(season)
    for gid, item in season_stats.items():
        if gid in games_by_id:
            games_by_id[gid]["stats"] = {
                "home": item["home"],
                "away": item["away"],
            }

    return list(games_by_id.values())


def _normalize_date(date_str: str) -> str:
    """'2025.02.15' → '2025-02-15', 미상('2010.00.00') 그대로 반환"""
    if not date_str:
        return date_str
    return date_str.replace(".", "-")


@router.get("/schedule")
def get_schedule(
    season: int = 2025,
    season_to: int | None = None,
    team: str | None = None,
    page: int = 1,
    per_page: int = 30,
):
    """시즌별 경기 일정/결과 목록 반환.

    - season: 시작 시즌 (2010~2026)
    - season_to: 종료 시즌 (지정 시 범위 조회)
    - team: 팀명 필터 (부분 일치)
    - page/per_page: 페이지네이션
    """
    s_from = max(2010, min(2026, season))
    s_to = max(s_from, min(2026, season_to)) if season_to is not None else s_from

    # 시즌 전체 경기 로드 (팀 목록 추출용)
    season_games: list[dict] = []
    for yr in range(s_from, s_to + 1):
        season_games.extend(_load_season(yr))

    # 팀 목록 (필터 적용 전, 시즌 전체)
    all_teams = sorted({
        t
        for g in season_games
        for t in (g.get("home_team", ""), g.get("away_team", ""))
        if t
    })

    # 팀 필터 적용
    filtered = season_games
    if team:
        filtered = [
            g for g in season_games
            if team in g.get("home_team", "") or team in g.get("away_team", "")
        ]

    # 날짜 오름차순 정렬 (날짜 미상은 맨 뒤)
    def sort_key(g: dict):
        d = g.get("date", "")
        if not d or "00" in d:
            return "9999-99-99"
        return _normalize_date(d)

    filtered.sort(key=sort_key)

    total = len(filtered)
    total_pages = max(1, (total + per_page - 1) // per_page)
    page = max(1, min(page, total_pages))
    start = (page - 1) * per_page
    games = filtered[start: start + per_page]

    result = []
    for g in games:
        date_raw = g.get("date", "")
        date_norm = _normalize_date(date_raw)
        is_unknown_date = "00" in date_raw

        # 이벤트 요약: 골만
        goals = [e for e in g.get("events", []) if e.get("type") in ("goal", "own_goal")]

        home = g.get("home_team", "")
        venue = g.get("venue") or HOME_VENUE.get(home, "")

        result.append({
            "season":     g.get("season"),
            "game_id":    g.get("game_id"),
            "date":       date_norm if not is_unknown_date else None,
            "home_team":  home,
            "away_team":  g.get("away_team"),
            "home_score": g.get("home_score"),
            "away_score": g.get("away_score"),
            "finished":   g.get("finished", True),
            "goals":      goals,
            "round":      g.get("round"),
            "venue":      venue,
            "stats":      g.get("stats"),
        })

    return {
        "season": s_from,
        "season_to": s_to,
        "season_label": str(s_from) if s_from == s_to else f"{s_from}~{s_to}",
        "total": total,
        "page": page,
        "total_pages": total_pages,
        "per_page": per_page,
        "all_teams": all_teams,
        "games": result,
    }


@router.get("/schedule/{season}/{game_id}")
def get_match_detail(season: int, game_id: int):
    """특정 경기 상세 정보 반환 (전체 이벤트 포함)."""
    games = _load_season(season)
    game = next((g for g in games if g.get("game_id") == game_id), None)
    if not game:
        raise HTTPException(status_code=404, detail="경기를 찾을 수 없습니다.")

    date_raw = game.get("date", "")
    return {
        "season":     season,
        "game_id":    game_id,
        "round":      game.get("round"),
        "date":       _normalize_date(date_raw) if date_raw and "00" not in date_raw else None,
        "home_team":  game.get("home_team"),
        "away_team":  game.get("away_team"),
        "home_score": game.get("home_score"),
        "away_score": game.get("away_score"),
        "events":     game.get("events", []),
        "stats":      game.get("stats"),    # 점유율·슈팅·코너킥 등
        "venue":      game.get("venue") or HOME_VENUE.get(game.get("home_team", ""), ""),
    }


@router.get("/schedule/teams")
def get_schedule_teams(season: int = 2025, season_to: int | None = None):
    """해당 시즌에 등장하는 팀 목록 반환"""
    s_from = max(2010, min(2026, season))
    s_to = max(s_from, min(2026, season_to)) if season_to is not None else s_from

    teams: set[str] = set()
    for yr in range(s_from, s_to + 1):
        for g in _load_season(yr):
            if g.get("home_team"):
                teams.add(g["home_team"])
            if g.get("away_team"):
                teams.add(g["away_team"])

    return {"teams": sorted(teams)}
