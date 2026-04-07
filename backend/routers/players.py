"""
/api/players  — 선수 기록 검색 엔드포인트
"""

import json
import os
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

AI_SERVER = Path(__file__).parent.parent.parent / "ai-server"
PLAYER_STATS_PATH = AI_SERVER / "data" / "processed" / "players" / "player_stats_2025.json"


def _load_players(season: int = 2025, season_to: int | None = None) -> list[dict]:
    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    players: list[dict] = []
    for y in range(s_from, s_to + 1):
        path = AI_SERVER / "data" / "processed" / "players" / f"player_stats_{y}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for p in data.get("players", []):
            players.append({**p, "_season": y})
    return players


@router.get("/players")
def search_players(
    team: str = "",
    position: str = "",
    min_goals: int = 0,
    min_assists: int = 0,
    sort_by: str = "goals",
    season: int = 2025,
    season_to: int | None = None,
):
    """선수 기록 검색. 팀, 포지션, 최소 득점/도움 필터링 지원."""
    players = _load_players(season, season_to)
    range_label = str(season) if season_to is None or season_to == season else f"{season}~{season_to}"
    if not players:
        raise HTTPException(status_code=404, detail=f"{range_label} 시즌 선수 데이터 없음")

    if team:
        players = [p for p in players if team in p.get("team", "")]
    if position:
        players = [p for p in players if position.upper() == p.get("position", "").upper()]
    if min_goals > 0:
        players = [p for p in players if p.get("goals", 0) >= min_goals]
    if min_assists > 0:
        players = [p for p in players if p.get("assists", 0) >= min_assists]

    sort_key = sort_by if sort_by in ("goals", "assists", "appearances", "minutes_played") else "goals"
    players.sort(key=lambda p: p.get(sort_key, 0), reverse=True)

    return {
        "season": season,
        "count": len(players),
        "players": players,
    }


@router.get("/players/top")
def get_top_scorers(season: int = 2025, season_to: int | None = None, limit: int = 10):
    """득점 순위 Top N."""
    players = _load_players(season, season_to)
    range_label = str(season) if season_to is None or season_to == season else f"{season}~{season_to}"
    if not players:
        raise HTTPException(status_code=404, detail=f"{range_label} 시즌 데이터 없음")
    players.sort(key=lambda p: (p.get("goals", 0), p.get("assists", 0)), reverse=True)
    return {
        "season": season,
        "season_to": season_to,
        "season_label": range_label,
        "type": "top_scorers",
        "players": players[:limit],
    }


PLAYERS_DIR = AI_SERVER / "data" / "processed" / "players"
PROFILES_PATH = PLAYERS_DIR / "player_profiles.json"


def _match_player(records: list[dict], name: str, name_field: str = "player_name") -> dict | None:
    """이름 정확·부분 매칭. 정확 일치 우선."""
    exact = [p for p in records if p.get(name_field, "") == name]
    if exact:
        return exact[0]
    partial = [p for p in records if name in p.get(name_field, "")]
    return partial[0] if partial else None


@router.get("/players/search")
def search_players_by_name(name: str, season_from: int = 2010, season_to: int = 2026):
    """이름 부분 일치로 선수 목록 반환 (자동완성용)."""
    found: dict[str, dict] = {}  # player_name -> {team, seasons}
    for year in range(season_from, season_to + 1):
        path = PLAYERS_DIR / f"player_stats_{year}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for p in data.get("players", []):
            pname = p.get("player_name", "")
            if name and name not in pname:
                continue
            if pname not in found:
                found[pname] = {"player_name": pname, "team": p.get("team", ""), "seasons": []}
            found[pname]["seasons"].append(year)
            found[pname]["team"] = p.get("team", "")  # 최신 팀으로 갱신
    results = sorted(found.values(), key=lambda x: -max(x["seasons"]) if x["seasons"] else 0)
    return {"count": len(results), "players": results[:30]}


@router.get("/players/{player_name}/career")
def get_player_career(player_name: str, season_from: int = 2010, season_to: int = 2026):
    """선수 시즌별 커리어 통계 반환."""
    career: list[dict] = []

    for year in range(season_from, season_to + 1):
        stats_path = PLAYERS_DIR / f"player_stats_{year}.json"
        minutes_path = PLAYERS_DIR / f"player_minutes_{year}.json"

        stats_rec: dict = {}
        if stats_path.exists():
            data = json.loads(stats_path.read_text(encoding="utf-8"))
            matched = _match_player(data.get("players", []), player_name)
            if matched:
                stats_rec = matched

        minutes_rec: dict = {}
        if minutes_path.exists():
            data = json.loads(minutes_path.read_text(encoding="utf-8"))
            matched = _match_player(data.get("players", []), player_name)
            if matched:
                minutes_rec = matched

        if not stats_rec and not minutes_rec:
            continue

        career.append({
            "season": year,
            "team": stats_rec.get("team") or minutes_rec.get("team", ""),
            "appearances": stats_rec.get("appearances") or minutes_rec.get("appearances", 0),
            "goals": stats_rec.get("goals", 0),
            "assists": stats_rec.get("assists", 0),
            "own_goals": stats_rec.get("own_goals", 0),
            "yellow_cards": stats_rec.get("yellow_cards", 0),
            "red_cards": stats_rec.get("red_cards", 0),
            "total_minutes": minutes_rec.get("total_minutes", 0),
            "starter_count": minutes_rec.get("starter_count", 0),
        })

    if not career:
        raise HTTPException(status_code=404, detail=f"'{player_name}' 선수 데이터 없음")

    totals = {
        "seasons": len(career),
        "appearances": sum(s["appearances"] for s in career),
        "goals": sum(s["goals"] for s in career),
        "assists": sum(s["assists"] for s in career),
        "yellow_cards": sum(s["yellow_cards"] for s in career),
        "red_cards": sum(s["red_cards"] for s in career),
        "total_minutes": sum(s["total_minutes"] for s in career),
    }

    # 프로필 매칭 (name_ko 또는 name_en)
    profile: dict | None = None
    if PROFILES_PATH.exists():
        profiles_data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        for p in profiles_data.get("players", []):
            if player_name in (p.get("name_ko") or "") or player_name in (p.get("name_en") or ""):
                profile = p
                break

    latest = career[-1]
    return {
        "player_name": player_name,
        "current_team": latest["team"],
        "profile": profile,
        "career": career,
        "totals": totals,
    }


def _build_career_data(player_name: str, season_from: int, season_to: int) -> dict:
    """커리어 데이터 빌드 (compare 엔드포인트용 공유 로직)."""
    career: list[dict] = []
    for year in range(season_from, season_to + 1):
        stats_path = PLAYERS_DIR / f"player_stats_{year}.json"
        minutes_path = PLAYERS_DIR / f"player_minutes_{year}.json"
        stats_rec: dict = {}
        if stats_path.exists():
            data = json.loads(stats_path.read_text(encoding="utf-8"))
            matched = _match_player(data.get("players", []), player_name)
            if matched:
                stats_rec = matched
        minutes_rec: dict = {}
        if minutes_path.exists():
            data = json.loads(minutes_path.read_text(encoding="utf-8"))
            matched = _match_player(data.get("players", []), player_name)
            if matched:
                minutes_rec = matched
        if not stats_rec and not minutes_rec:
            continue
        career.append({
            "season": year,
            "team": stats_rec.get("team") or minutes_rec.get("team", ""),
            "appearances": stats_rec.get("appearances") or minutes_rec.get("appearances", 0),
            "goals": stats_rec.get("goals", 0),
            "assists": stats_rec.get("assists", 0),
            "own_goals": stats_rec.get("own_goals", 0),
            "yellow_cards": stats_rec.get("yellow_cards", 0),
            "red_cards": stats_rec.get("red_cards", 0),
            "total_minutes": minutes_rec.get("total_minutes", 0),
            "starter_count": minutes_rec.get("starter_count", 0),
        })

    if not career:
        raise HTTPException(status_code=404, detail=f"'{player_name}' 선수 데이터 없음")

    totals = {
        "seasons": len(career),
        "appearances": sum(s["appearances"] for s in career),
        "goals": sum(s["goals"] for s in career),
        "assists": sum(s["assists"] for s in career),
        "yellow_cards": sum(s["yellow_cards"] for s in career),
        "red_cards": sum(s["red_cards"] for s in career),
        "total_minutes": sum(s["total_minutes"] for s in career),
    }

    profile: dict | None = None
    if PROFILES_PATH.exists():
        profiles_data = json.loads(PROFILES_PATH.read_text(encoding="utf-8"))
        for p in profiles_data.get("players", []):
            if player_name in (p.get("name_ko") or "") or player_name in (p.get("name_en") or ""):
                profile = p
                break

    latest = career[-1]
    return {
        "player_name": player_name,
        "current_team": latest["team"],
        "profile": profile,
        "career": career,
        "totals": totals,
    }


def _generate_compare_summary(p1: dict, p2: dict) -> str:
    """GPT-4o-mini로 두 선수 비교 요약 생성. API 키 없으면 빈 문자열 반환."""
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        return ""
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)

        def career_summary(p: dict) -> str:
            t = p["totals"]
            seasons = ", ".join(
                f"{s['season']}시즌({s['team']}) {s['goals']}골 {s['assists']}도움 {s['appearances']}경기"
                for s in p["career"]
            )
            return (
                f"이름: {p['player_name']}, 현소속: {p['current_team']}, "
                f"통산 {t['seasons']}시즌 {t['appearances']}경기 {t['goals']}골 {t['assists']}도움 "
                f"경고 {t['yellow_cards']}회 퇴장 {t['red_cards']}회. "
                f"시즌별: {seasons}"
            )

        prompt = (
            "당신은 K리그 전문 해설위원입니다. 아래 두 선수의 K리그 커리어 통계를 보고 "
            "해설 방송에서 바로 쓸 수 있는 간결한 비교 분석문을 한국어로 작성하세요. "
            "어느 선수가 어떤 면에서 우위에 있는지, 각자의 강점은 무엇인지 짧게 정리하세요. "
            "2~3문장으로 작성하고 수치를 근거로 활용하세요.\n\n"
            f"[선수 A] {career_summary(p1)}\n\n"
            f"[선수 B] {career_summary(p2)}"
        )

        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=300,
            temperature=0.7,
        )
        return resp.choices[0].message.content or ""
    except Exception:
        return ""


@router.get("/players/compare")
def compare_players(
    player1: str,
    player2: str,
    season_from: int = 2010,
    season_to: int = 2026,
):
    """두 선수 커리어 비교 + AI 요약."""
    p1 = _build_career_data(player1, season_from, season_to)
    p2 = _build_career_data(player2, season_from, season_to)
    summary = _generate_compare_summary(p1, p2)
    return {"player1": p1, "player2": p2, "summary": summary}
