"""
/api/stats/{team}  — 팀 시즌 통계 엔드포인트
"""

import json
from pathlib import Path

from fastapi import APIRouter, HTTPException

router = APIRouter()

AI_SERVER   = Path(__file__).parent.parent.parent / "ai-server"
K1_PATH     = AI_SERVER / "data" / "processed" / "teams" / "k1_team_results.json"
MATCHES_DIR = AI_SERVER / "data" / "processed" / "matches"


MINIMUM_SEASON_GAMES = 100  # k1_results 데이터가 이보다 적으면 match_events로 대체

def _load_unique_records(season_from: int, season_to: int) -> list[dict]:
    seen: set  = set()
    unique: list[dict] = []

    # 1) k1_team_results.json 에서 로드
    covered_seasons: set[int] = set()
    season_game_count: dict[int, int] = {}
    if K1_PATH.exists():
        records = json.loads(K1_PATH.read_text(encoding="utf-8"))
        for r in records:
            s = r.get("season", 0)
            if season_from <= s <= season_to:
                key = (s, r.get("game_id"))
                if key not in seen:
                    seen.add(key)
                    unique.append(r)
                    covered_seasons.add(s)
                    season_game_count[s] = season_game_count.get(s, 0) + 1

    # k1_results 데이터가 불완전한 시즌은 match_events로 대체
    incomplete = {s for s in covered_seasons if season_game_count.get(s, 0) < MINIMUM_SEASON_GAMES}
    if incomplete:
        covered_seasons -= incomplete
        unique = [r for r in unique if r.get("season") not in incomplete]
        seen   = {(r.get("season"), r.get("game_id")) for r in unique}

    # 2) k1_team_results에 없는(또는 불완전한) 시즌은 match_events 에서 보완
    for year in range(season_from, season_to + 1):
        if year in covered_seasons:
            continue
        ev_path = MATCHES_DIR / f"match_events_{year}.json"
        if not ev_path.exists():
            continue
        data = json.loads(ev_path.read_text(encoding="utf-8"))
        if data.get("source") == "generated":
            continue
        for g in data.get("events_by_game", []):
            gid = g.get("game_id")
            hs  = g.get("home_score")
            as_ = g.get("away_score")
            if gid is None or hs is None or as_ is None:
                continue
            key = (year, gid)
            if key not in seen:
                seen.add(key)
                unique.append({
                    "game_id":    gid,
                    "season":     year,
                    "round":      g.get("round"),
                    "date":       g.get("date", ""),
                    "home_team":  g.get("home_team", ""),
                    "away_team":  g.get("away_team", ""),
                    "home_score": hs,
                    "away_score": as_,
                    "finished":   True,
                })

    return unique


@router.get("/stats/teams")
def get_stats_teams(season: int = 2025, season_to: int = None):
    """시즌에 실제 참가한 팀 목록 반환 (경기 데이터 기반)."""
    s_from = season
    s_to   = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    records = _load_unique_records(s_from, s_to)
    records = _filter_league_only(records)

    teams: set[str] = set()
    for r in records:
        if r.get("home_team"):
            teams.add(r["home_team"])
        if r.get("away_team"):
            teams.add(r["away_team"])

    return {"season": s_from, "season_to": s_to, "teams": sorted(teams)}


@router.get("/stats/{team}")
def get_team_stats(team: str, season: int = 2025, season_to: int = None):
    """팀 시즌 통계 반환. season_to 지정 시 범위 집계."""
    s_from = season
    s_to   = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    records = _filter_league_only(_load_unique_records(s_from, s_to))
    records = [r for r in records if r.get("finished", True)]

    home_games = [r for r in records if team in r.get("home_team", "")]
    away_games = [r for r in records if team in r.get("away_team", "")]
    all_games  = home_games + away_games

    range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"
    if not all_games:
        raise HTTPException(status_code=404, detail=f"'{team}' 경기 없음 (시즌: {range_label})")

    def calc(games, is_home: bool):
        win  = sum(1 for r in games if (r["home_score"] > r["away_score"]) == is_home)
        draw = sum(1 for r in games if r["home_score"] == r["away_score"])
        lose = len(games) - win - draw
        gf   = sum(r["home_score"] if is_home else r["away_score"] for r in games)
        ga   = sum(r["away_score"] if is_home else r["home_score"] for r in games)
        return {"games": len(games), "win": win, "draw": draw, "lose": lose, "gf": gf, "ga": ga}

    h = calc(home_games, True)
    a = calc(away_games, False)
    total_w  = h["win"]  + a["win"]
    total_d  = h["draw"] + a["draw"]
    total_l  = h["lose"] + a["lose"]
    total_g  = len(all_games)
    total_gf = h["gf"] + a["gf"]
    total_ga = h["ga"] + a["ga"]
    total_pts = total_w * 3 + total_d

    recent = sorted(all_games, key=lambda r: r.get("date", ""), reverse=True)[:5]
    recent_results = []
    for r in recent:
        is_home = team in r.get("home_team", "")
        gf = r["home_score"] if is_home else r["away_score"]
        ga = r["away_score"] if is_home else r["home_score"]
        recent_results.append({
            "date": r["date"],
            "season": r.get("season"),
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "home_score": r["home_score"],
            "away_score": r["away_score"],
            "result": "W" if gf > ga else ("D" if gf == ga else "L"),
            "venue": "홈" if is_home else "원정",
            "stadium": r.get("venue", ""),
        })

    # 홈 관중 집계 (attendance > 0인 홈경기만)
    home_att_games = [r for r in home_games if r.get("attendance") and r["attendance"] > 0]
    if home_att_games:
        home_att_vals = [r["attendance"] for r in home_att_games]
        best_att_game = max(home_att_games, key=lambda r: r["attendance"])
        home_attendance = {
            "total":   sum(home_att_vals),
            "avg":     round(sum(home_att_vals) / len(home_att_vals)),
            "max":     max(home_att_vals),
            "min":     min(home_att_vals),
            "games":   len(home_att_games),
            "best_game": {
                "date":       best_att_game["date"],
                "opponent":   best_att_game["away_team"],
                "attendance": best_att_game["attendance"],
                "score":      f"{best_att_game['home_score']}-{best_att_game['away_score']}",
            },
        }
    else:
        home_attendance = None

    return {
        "team":         team,
        "season":       s_from,
        "season_to":    s_to,
        "season_label": range_label,
        "total": {
            "games": total_g, "win": total_w, "draw": total_d, "lose": total_l,
            "win_rate": round(total_w / total_g * 100, 1) if total_g else 0,
            "gf": total_gf, "ga": total_ga,
            "gd": total_gf - total_ga,
            "points": total_pts,
        },
        "home": h,
        "away": a,
        "recent": recent_results,
        "home_attendance": home_attendance,
    }


@router.get("/attendance")
def get_attendance(season: int = 2025, season_to: int = None, team: str = None):
    """시즌 관중 통계. team 지정 시 해당 팀 홈경기 상세 반환."""
    s_from = season
    s_to   = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    records = _filter_league_only(_load_unique_records(s_from, s_to))
    att_records = [r for r in records if r.get("attendance") and r["attendance"] > 0]
    if not att_records:
        raise HTTPException(status_code=404, detail=f"관중 데이터 없음 (시즌: {s_from}~{s_to})")

    range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"

    # 팀별 홈 관중 집계
    team_home: dict[str, dict] = {}
    for r in att_records:
        ht = r["home_team"]
        if ht not in team_home:
            team_home[ht] = {"team": ht, "games": 0, "total": 0, "max": 0, "min": 999_999, "games_list": []}
        t = team_home[ht]
        t["games"] += 1
        t["total"] += r["attendance"]
        t["max"] = max(t["max"], r["attendance"])
        t["min"] = min(t["min"], r["attendance"])
        t["games_list"].append(r)

    team_rows = []
    for ht, t in team_home.items():
        best = max(t["games_list"], key=lambda r: r["attendance"])
        team_rows.append({
            "team":   ht,
            "games":  t["games"],
            "total":  t["total"],
            "avg":    round(t["total"] / t["games"]) if t["games"] else 0,
            "max":    t["max"],
            "min":    t["min"],
            "best_game": {
                "date":       best["date"],
                "opponent":   best["away_team"],
                "attendance": best["attendance"],
                "score":      f"{best['home_score']}-{best['away_score']}",
                "venue":      best.get("venue", ""),
            },
        })
    team_rows.sort(key=lambda r: -r["avg"])
    for i, row in enumerate(team_rows, 1):
        row["rank"] = i

    # 특정 팀 홈경기 전체 목록 (team 파라미터)
    team_games = None
    if team:
        matched = sorted(
            [r for r in att_records if team in r.get("home_team", "")],
            key=lambda r: r.get("date", ""),
        )
        team_games = [
            {
                "date":       r["date"],
                "round":      r.get("round"),
                "opponent":   r["away_team"],
                "attendance": r["attendance"],
                "score":      f"{r['home_score']}-{r['away_score']}",
                "venue":      r.get("venue", ""),
                "season":     r.get("season"),
            }
            for r in matched
        ]

    # 시즌 전체 최다 관중 TOP 10
    top_games = sorted(att_records, key=lambda r: -r["attendance"])[:10]
    top_games_list = [
        {
            "date":       r["date"],
            "round":      r.get("round"),
            "home_team":  r["home_team"],
            "away_team":  r["away_team"],
            "attendance": r["attendance"],
            "score":      f"{r['home_score']}-{r['away_score']}",
            "venue":      r.get("venue", ""),
            "season":     r.get("season"),
        }
        for r in top_games
    ]

    total_att = sum(r["attendance"] for r in att_records)
    return {
        "season":       s_from,
        "season_to":    s_to,
        "season_label": range_label,
        "summary": {
            "total_games":      len(att_records),
            "total_attendance": total_att,
            "avg_per_game":     round(total_att / len(att_records)) if att_records else 0,
            "max_game":         top_games_list[0] if top_games_list else None,
        },
        "by_team":    team_rows,
        "top_games":  top_games_list,
        "team_games": team_games,
    }


MINUTES_DIR = AI_SERVER / "data" / "processed" / "players"


@router.get("/stats/{team}/form")
def get_team_form(team: str, season: int = 2025, limit: int = 20):
    """팀 최근 N경기 폼 데이터 (히트맵용)."""
    records = _load_unique_records(season, season)
    records = _filter_league_only(records)

    team_games = [
        r for r in records
        if team in r.get("home_team", "") or team in r.get("away_team", "")
    ]
    if not team_games:
        raise HTTPException(status_code=404, detail=f"'{team}' 경기 없음 ({season}시즌)")

    team_games.sort(key=lambda r: r.get("date", ""), reverse=True)
    standings = {row["team"]: row["rank"] for row in calculate_standings(records)}

    result = []
    for r in team_games[:limit]:
        is_home = team in r.get("home_team", "")
        gf = r["home_score"] if is_home else r["away_score"]
        ga = r["away_score"] if is_home else r["home_score"]
        opponent = r["away_team"] if is_home else r["home_team"]
        result.append({
            "date": r.get("date", ""),
            "round": r.get("round"),
            "is_home": is_home,
            "opponent": opponent,
            "opponent_rank": standings.get(opponent),
            "gf": gf,
            "ga": ga,
            "result": "W" if gf > ga else ("D" if gf == ga else "L"),
        })

    wins  = sum(1 for g in result if g["result"] == "W")
    draws = sum(1 for g in result if g["result"] == "D")
    losses = sum(1 for g in result if g["result"] == "L")
    return {
        "team": team, "season": season, "total": len(result),
        "summary": {"W": wins, "D": draws, "L": losses},
        "games": result,
    }


@router.get("/stats/{team}/goal-distribution")
def get_goal_distribution(team: str, season: int = 2025):
    """팀 득점/실점 15분 구간별 분포."""
    ev_path = MATCHES_DIR / f"match_events_{season}.json"
    if not ev_path.exists():
        raise HTTPException(status_code=404, detail=f"{season}시즌 이벤트 데이터 없음")

    data = json.loads(ev_path.read_text(encoding="utf-8"))
    if data.get("source") == "generated":
        raise HTTPException(status_code=404, detail=f"{season}시즌 실제 이벤트 데이터 없음")

    INTERVALS = [
        ("1-15",  1,  15), ("16-30", 16, 30), ("31-45", 31, 45),
        ("46-60", 46, 60), ("61-75", 61, 75), ("76-90", 76, 90),
        ("90+",   91, 9999),
    ]
    counts = {lb: {"scored": 0, "conceded": 0, "scored_home": 0, "scored_away": 0}
              for lb, _, _ in INTERVALS}

    for game in data.get("events_by_game", []):
        home = game.get("home_team", "")
        away = game.get("away_team", "")
        is_home = team in home
        is_away = team in away
        if not is_home and not is_away:
            continue
        for ev in game.get("events", []):
            if ev.get("type") != "goal":
                continue
            minute = ev.get("minute", 0)
            ev_team = ev.get("team", "")
            for lb, lo, hi in INTERVALS:
                if lo <= minute <= hi:
                    if team in ev_team:
                        counts[lb]["scored"] += 1
                        counts[lb]["scored_home" if is_home else "scored_away"] += 1
                    else:
                        counts[lb]["conceded"] += 1
                    break

    intervals = [
        {"label": lb, **counts[lb]}
        for lb, _, _ in INTERVALS
    ]
    return {
        "team": team, "season": season,
        "total_scored":   sum(i["scored"]   for i in intervals),
        "total_conceded": sum(i["conceded"] for i in intervals),
        "intervals": intervals,
    }


@router.get("/standings/timeline")
def get_standings_timeline(season: int = 2025):
    """라운드별 누적 순위 변동 타임라인."""
    records = _load_unique_records(season, season)
    if not records:
        raise HTTPException(status_code=404, detail=f"{season}시즌 데이터 없음")

    records = _filter_league_only(records)
    records_r = [r for r in records if r.get("round")]
    if not records_r:
        raise HTTPException(status_code=404, detail=f"{season}시즌 라운드 데이터 없음")

    max_round = max(r["round"] for r in records_r)

    all_teams: set[str] = set()
    for r in records:
        if r.get("home_team"): all_teams.add(r["home_team"])
        if r.get("away_team"): all_teams.add(r["away_team"])
    all_teams_sorted = sorted(all_teams)
    num_teams = len(all_teams_sorted)

    cum = {t: {"win": 0, "draw": 0, "gf": 0, "ga": 0} for t in all_teams_sorted}
    round_rank_maps: list[dict] = []

    for rnd in range(1, max_round + 1):
        for r in records_r:
            if r["round"] != rnd:
                continue
            hs, as_ = r.get("home_score", 0), r.get("away_score", 0)
            for t, is_home in [(r.get("home_team", ""), True), (r.get("away_team", ""), False)]:
                if t not in cum:
                    continue
                gf = hs if is_home else as_
                ga = as_ if is_home else hs
                cum[t]["gf"] += gf
                cum[t]["ga"] += ga
                if gf > ga: cum[t]["win"] += 1
                elif gf == ga: cum[t]["draw"] += 1

        rows = sorted(
            all_teams_sorted,
            key=lambda t: (
                -(cum[t]["win"] * 3 + cum[t]["draw"]),
                -cum[t]["gf"],
                -(cum[t]["gf"] - cum[t]["ga"]),
            )
        )
        round_rank_maps.append({t: i + 1 for i, t in enumerate(rows)})

    return {
        "season": season,
        "max_round": max_round,
        "rounds": list(range(1, max_round + 1)),
        "num_teams": num_teams,
        "teams": [
            {"team": t, "ranks": [round_rank_maps[i].get(t, num_teams) for i in range(max_round)]}
            for t in all_teams_sorted
        ],
    }


def _load_player_minutes(season: int) -> dict:
    """player_minutes_{season}.json 로드. 없으면 빈 dict 반환."""
    p = MINUTES_DIR / f"player_minutes_{season}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text(encoding="utf-8"))


@router.get("/player-minutes/{player}")
def get_player_minutes(player: str, season: int = 2025, team: str = None):
    """
    선수의 경기별 출전시간 반환.
    player: 선수 이름 (부분 일치)
    team:   팀명 필터 (선택)
    """
    data = _load_player_minutes(season)
    if not data:
        raise HTTPException(status_code=404, detail=f"{season}시즌 출전시간 데이터 없음")

    matched = [
        p for p in data.get("players", [])
        if player in p.get("player_name", "")
        and (not team or team in p.get("team", ""))
    ]
    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"'{player}' 선수 데이터 없음 (시즌: {season})"
        )

    # 이름이 정확히 일치하는 경우 우선
    exact = [p for p in matched if p["player_name"] == player]
    result = exact[0] if exact else matched[0]

    return {
        "season":        season,
        "player_name":   result["player_name"],
        "team":          result["team"],
        "total_minutes": result["total_minutes"],
        "appearances":   result["appearances"],
        "starter_count": result.get("starter_count", 0),
        "avg_minutes":   round(result["total_minutes"] / result["appearances"], 1) if result["appearances"] else 0,
        "games": sorted(result.get("games", []), key=lambda g: (g.get("date", ""), g.get("game_id", 0))),
    }


@router.get("/team-minutes/{team}")
def get_team_minutes(team: str, season: int = 2025):
    """팀 전체 선수 출전시간 요약 반환."""
    data = _load_player_minutes(season)
    if not data:
        raise HTTPException(status_code=404, detail=f"{season}시즌 출전시간 데이터 없음")

    players = [
        p for p in data.get("players", [])
        if team in p.get("team", "")
    ]
    if not players:
        raise HTTPException(status_code=404, detail=f"'{team}' 팀 데이터 없음 (시즌: {season})")

    summary = [
        {
            "player_name":   p["player_name"],
            "total_minutes": p["total_minutes"],
            "appearances":   p["appearances"],
            "starter_count": p.get("starter_count", 0),
            "avg_minutes":   round(p["total_minutes"] / p["appearances"], 1) if p["appearances"] else 0,
        }
        for p in sorted(players, key=lambda p: -p["total_minutes"])
    ]
    return {
        "season":  season,
        "team":    team,
        "players": summary,
    }


def calculate_standings(records: list[dict]) -> list[dict]:
    """경기 기록 리스트 → 순위표 계산 (승점·골득실·득점 순 정렬)."""
    teams: dict[str, dict] = {}
    for r in records:
        hs = r.get("home_score")
        as_ = r.get("away_score")
        if hs is None or as_ is None:
            continue
        for team, is_home in [(r["home_team"], True), (r["away_team"], False)]:
            if not team:
                continue
            if team not in teams:
                teams[team] = {"team": team, "games": 0, "win": 0, "draw": 0, "lose": 0, "gf": 0, "ga": 0}
            t = teams[team]
            t["games"] += 1
            gf = hs if is_home else as_
            ga = as_ if is_home else hs
            t["gf"] += gf
            t["ga"] += ga
            if gf > ga:
                t["win"] += 1
            elif gf == ga:
                t["draw"] += 1
            else:
                t["lose"] += 1

    rows = list(teams.values())
    for row in rows:
        row["gd"]     = row["gf"] - row["ga"]
        row["points"] = row["win"] * 3 + row["draw"]

    # K리그 순위 결정: 승점 → 다득점 → 득실차 순
    rows.sort(key=lambda r: (-r["points"], -r["gf"], -r["gd"]))
    for i, row in enumerate(rows, 1):
        row["rank"] = i
    return rows


def _filter_league_only(records: list[dict]) -> list[dict]:
    """플레이오프·컵 기록을 제외하고 리그 정규 시즌 경기만 반환."""
    result = []
    for r in records:
        comp = r.get("competition") or ""
        # 'PO'(플레이오프), '파이널', '컵' 포함된 competition 제외
        if any(kw in comp for kw in ("PO", "파이널", "컵", "Cup", "playoff")):
            continue
        result.append(r)
    return result if result else records  # 필터 결과가 비면 원본 반환


@router.get("/standings")
def get_standings(season: int = 2025, round_to: int = None):
    """시즌 순위표 반환. round_to 지정 시 해당 라운드까지의 누적 순위.
    파이널 라운드(라운드 34~38)가 있는 시즌은 K리그1 파이널 라운드 규칙 적용:
    - 정규 시즌(라운드 1~33) 순위로 A조(1~6위) / B조(7~12위) 구분
    - 파이널 라운드 포함 누적 승점으로 조 내 순위 결정
    - A조 팀은 항상 1~6위, B조 팀은 항상 7~12위
    """
    FINAL_ROUND_START = 34      # 라운드 정보 있는 시즌의 파이널 라운드 시작
    REGULAR_SEASON_GAMES = 198  # 12팀 × 33라운드 기본값
    FULL_SEASON_GAMES = 228     # 12팀 기본 전체 경기수

    # 라운드 정보 없는 시즌별 파이널 라운드 설정 (total, regular, group_size)
    SEASON_CONFIG = {
        2013: (266, 182, 7),  # 14팀: 정규 182경기 + 파이널 84경기, 7+7 분리
        # 12팀 시즌(2014, 2022, 2023 등)은 기본값(228, 198, 6) 사용
    }

    records = _load_unique_records(season, season)
    if not records:
        raise HTTPException(status_code=404, detail=f"{season}시즌 데이터 없음")

    # 강등PO·컵 등 비리그 경기 제외 (파이널 라운드는 유지)
    records = _filter_league_only(records)

    has_round_info = any(r.get("round") for r in records)
    max_round = max((r.get("round") or 0) for r in records)

    # round_to 지정 시: 단순 누적 순위 (그룹 구분 없이)
    if round_to is not None:
        filtered = [r for r in records if (r.get("round") or 0) <= round_to]
        if not filtered:
            raise HTTPException(status_code=404, detail=f"{season}시즌 {round_to}라운드 데이터 없음")
        rows = calculate_standings(filtered)
        return {
            "season": season, "round_to": round_to, "max_round": max_round,
            "label": f"{season} 시즌 {round_to}라운드까지",
            "has_final_round": False,
            "standings": rows,
        }

    # 파이널 라운드 존재 여부 및 정규 시즌 경기 결정
    cfg = SEASON_CONFIG.get(season)
    full_games    = cfg[0] if cfg else FULL_SEASON_GAMES
    regular_games = cfg[1] if cfg else REGULAR_SEASON_GAMES
    group_size    = cfg[2] if cfg else 6

    if has_round_info:
        # 라운드 정보 있는 시즌 (2015~2021, 2024~2025 등)
        has_final_round = max_round >= FINAL_ROUND_START
        regular = [r for r in records if (r.get("round") or 0) < FINAL_ROUND_START]
    else:
        # 라운드 정보 없는 시즌 (2013, 2014, 2022, 2023 등): game_id로 구분
        has_final_round = len(records) == full_games
        records_by_id = sorted(records, key=lambda r: r.get("game_id", 0))
        regular = records_by_id[:regular_games] if has_final_round else records

    if has_final_round:
        regular_standings = calculate_standings(regular)

        group_a_teams = {row["team"] for row in regular_standings[:group_size]}
        group_b_teams = {row["team"] for row in regular_standings[group_size:]}

        # 정규+파이널 전체 누적 승점 계산
        total_standings = calculate_standings(records)

        # 조별 분리 및 재정렬
        group_a = sorted(
            [r for r in total_standings if r["team"] in group_a_teams],
            key=lambda r: (-r["points"], -r["gf"], -r["gd"])
        )
        group_b = sorted(
            [r for r in total_standings if r["team"] in group_b_teams],
            key=lambda r: (-r["points"], -r["gf"], -r["gd"])
        )
        others = [r for r in total_standings
                  if r["team"] not in group_a_teams and r["team"] not in group_b_teams]

        # 순위 재부여: A조 1~6위, B조 7~12위
        for i, row in enumerate(group_a, 1):
            row["rank"] = i
            row["group"] = "A"
        for i, row in enumerate(group_b, len(group_a) + 1):
            row["rank"] = i
            row["group"] = "B"
        for i, row in enumerate(others, len(group_a) + len(group_b) + 1):
            row["rank"] = i
            row["group"] = None

        rows = group_a + group_b + others
    else:
        rows = calculate_standings(records)
        for row in rows:
            row["group"] = None

    return {
        "season":          season,
        "round_to":        round_to,
        "max_round":       max_round,
        "label":           f"{season} 시즌 전체",
        "has_final_round": has_final_round,
        "standings":       rows,
    }
