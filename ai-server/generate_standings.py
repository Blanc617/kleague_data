"""
match_events 데이터로 역대 시즌 최종 순위표 생성.

외부 API가 역대 데이터를 반환하지 않으므로 자체 집계.
k1_team_results.json(라운드/날짜 포함) + match_events(스코어 보완) 활용.

결과: data/processed/teams/standings.json
"""

import json
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
sys.stdout.reconfigure(encoding="utf-8")

RESULTS_PATH = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
MATCHES_DIR  = ROOT / "data" / "processed" / "matches"
OUT_PATH     = ROOT / "data" / "processed" / "teams" / "standings.json"


def compute_standings(games: list[dict], season: int) -> list[dict]:
    """경기 목록에서 최종 순위표 계산."""
    stats: dict[str, dict] = defaultdict(lambda: {
        "played": 0, "wins": 0, "draws": 0, "losses": 0,
        "goals_for": 0, "goals_against": 0,
    })

    for g in games:
        hs = g.get("home_score")
        as_ = g.get("away_score")
        home = g.get("home_team", "").strip()
        away = g.get("away_team", "").strip()

        if hs is None or as_ is None or not home or not away:
            continue
        try:
            hs, as_ = int(hs), int(as_)
        except (TypeError, ValueError):
            continue

        stats[home]["played"] += 1
        stats[home]["goals_for"] += hs
        stats[home]["goals_against"] += as_

        stats[away]["played"] += 1
        stats[away]["goals_for"] += as_
        stats[away]["goals_against"] += hs

        if hs > as_:
            stats[home]["wins"] += 1
            stats[away]["losses"] += 1
        elif hs < as_:
            stats[away]["wins"] += 1
            stats[home]["losses"] += 1
        else:
            stats[home]["draws"] += 1
            stats[away]["draws"] += 1

    rows = []
    for team, s in stats.items():
        points = s["wins"] * 3 + s["draws"]
        goal_diff = s["goals_for"] - s["goals_against"]
        rows.append({
            "season":         season,
            "league":         "K1",
            "team":           team,
            "played":         s["played"],
            "wins":           s["wins"],
            "draws":          s["draws"],
            "losses":         s["losses"],
            "goals_for":      s["goals_for"],
            "goals_against":  s["goals_against"],
            "goal_diff":      goal_diff,
            "points":         points,
        })

    rows.sort(key=lambda r: (-r["points"], -r["goal_diff"], -r["goals_for"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    return rows


def load_games_for_season(season: int) -> list[dict]:
    """해당 시즌 완료된 경기 목록 로드. k1_team_results 우선, 없으면 match_events 사용."""
    games: dict[int, dict] = {}

    # 1) k1_team_results에서 해당 시즌 경기 로드
    if RESULTS_PATH.exists():
        records = json.loads(RESULTS_PATH.read_text(encoding="utf-8"))
        for r in records:
            if r.get("season") == season:
                gid = r.get("game_id")
                hs, as_ = r.get("home_score"), r.get("away_score")
                if gid and hs is not None and as_ is not None:
                    games[gid] = r

    # 2) match_events 에서 스코어 보완 (k1_team_results에 없는 경기)
    ev_path = MATCHES_DIR / f"match_events_{season}.json"
    if ev_path.exists():
        data = json.loads(ev_path.read_text(encoding="utf-8"))
        for g in data.get("events_by_game", []):
            gid = g.get("game_id")
            hs = g.get("home_score")
            as_ = g.get("away_score")
            if gid and hs is not None and as_ is not None and gid not in games:
                games[gid] = g

    return list(games.values())


def main():
    all_standings = []

    for season in range(2013, 2027):
        games = load_games_for_season(season)
        if not games:
            print(f"{season}: 경기 데이터 없음 → 건너뜀")
            continue

        rows = compute_standings(games, season)
        if not rows:
            print(f"{season}: 순위 계산 실패 → 건너뜀")
            continue

        all_standings.extend(rows)
        top3 = ", ".join(f"{r['rank']}위 {r['team']}({r['points']}점)" for r in rows[:3])
        print(f"{season}: {len(rows)}팀 | {top3}")

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(
        json.dumps(all_standings, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"\n저장 완료: {OUT_PATH} ({len(all_standings)}건)")


if __name__ == "__main__":
    main()
