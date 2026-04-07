"""
match_lineups_{season}.json + k1_team_results.json 에서
선수(골키퍼)별 클린시트 수를 계산해 player_cleansheets_{season}.json 에 저장한다.

클린시트 귀속 규칙:
  - 해당 팀이 무실점(상대 득점 0)인 경기
  - 그 경기 라인업에서 포지션이 GK인 선발 선수에게 귀속
  - 라인업 없는 경기는 스킵 (데이터 공백으로 처리)

사용법:
    python process_player_cleansheets.py              # 2025
    python process_player_cleansheets.py --season 2024
    python process_player_cleansheets.py --all        # 2010~현재
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

# GK 포지션 식별 문자열 (kleague.com API 반환값 기준)
GK_POSITIONS = {"gk", "골키퍼", "goalkeeper", "g", "keeper"}


def _is_gk(position: str) -> bool:
    return (position or "").strip().lower() in GK_POSITIONS


def process_season(season: int) -> Path:
    """시즌의 라인업 + 경기결과 파일을 읽어 선수별 클린시트 파일 생성."""
    from loguru import logger

    lineup_path  = ROOT / "data" / "processed" / "matches"  / f"match_lineups_{season}.json"
    results_path = ROOT / "data" / "processed" / "teams"    / "k1_team_results.json"
    out_path     = ROOT / "data" / "processed" / "players"  / f"player_cleansheets_{season}.json"

    # ── 경기 결과 로드 ─────────────────────────────────
    if not results_path.exists():
        logger.warning(f"경기 결과 파일 없음: {results_path}")
        return out_path

    all_records: list[dict] = json.loads(results_path.read_text(encoding="utf-8"))
    # 해당 시즌 완료 경기만
    season_records = {
        r["game_id"]: r
        for r in all_records
        if r.get("season") == season and r.get("game_id") and r.get("finished")
    }

    # ── 라인업 로드 ────────────────────────────────────
    if not lineup_path.exists():
        logger.warning(f"라인업 파일 없음: {lineup_path}")
        _write_empty(out_path, season, 0, len(season_records))
        return out_path

    lineup_data = json.loads(lineup_path.read_text(encoding="utf-8"))
    lineup_by_game: dict[int, dict] = {
        g["game_id"]: g
        for g in lineup_data.get("lineups_by_game", [])
        if g.get("game_id")
    }

    total_games   = len(season_records)
    games_with_lineup = sum(1 for g in lineup_by_game.values() if g.get("lineups"))

    # ── 선수별 집계 ────────────────────────────────────
    # key: (team, player_name)  value: {cs, games, cs_home, cs_away, cs_game_list}
    player_cs: dict[tuple, dict] = {}

    def ensure(team: str, player: str) -> dict:
        key = (team, player)
        if key not in player_cs:
            player_cs[key] = {
                "player_name": player,
                "team":        team,
                "clean_sheets": 0,
                "cs_home":      0,
                "cs_away":      0,
                "games_played": 0,
                "cs_games":     [],
            }
        return player_cs[key]

    for gid, rec in season_records.items():
        ht  = rec["home_team"]
        at  = rec["away_team"]
        hs  = rec.get("home_score", 0) or 0
        aws = rec.get("away_score", 0) or 0

        lu = lineup_by_game.get(gid, {})
        lineups = lu.get("lineups", {})
        if not lineups:
            continue

        for side, team_name, ga in (("home", ht, aws), ("away", at, hs)):
            side_data = lineups.get(side, {})
            starters  = side_data.get("starters", [])

            # GK 찾기
            gks = [p for p in starters if _is_gk(p.get("position", ""))]

            # 모든 선발 선수에게 "출전 경기" 카운트
            for p in starters:
                entry = ensure(team_name, p["player"])
                entry["games_played"] += 1

            # 클린시트 귀속
            if ga == 0 and gks:
                date  = rec.get("date", "")
                round_no = rec.get("round", "")
                for gk in gks:
                    entry = ensure(team_name, gk["player"])
                    entry["clean_sheets"] += 1
                    if side == "home":
                        entry["cs_home"] += 1
                    else:
                        entry["cs_away"] += 1
                    entry["cs_games"].append({
                        "game_id":  gid,
                        "date":     date,
                        "round":    round_no,
                        "home":     ht,
                        "away":     at,
                        "score":    f"{hs}-{aws}",
                        "location": "홈" if side == "home" else "원정",
                    })

    # GK가 있는 선수만 추출 & 정렬
    gk_list = [v for v in player_cs.values() if v["clean_sheets"] > 0]
    gk_list.sort(key=lambda x: (-x["clean_sheets"], -x["cs_home"]))
    for i, row in enumerate(gk_list, 1):
        row["rank"] = i
        if row["games_played"]:
            row["cs_rate"] = round(row["clean_sheets"] / row["games_played"] * 100, 1)
        else:
            row["cs_rate"] = 0.0

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season":            season,
        "league":            "K1",
        "total_games":       total_games,
        "games_with_lineup": games_with_lineup,
        "total_gks":         len(gk_list),
        "players":           gk_list,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(
        f"클린시트 저장 완료: {out_path} "
        f"(GK {len(gk_list)}명, 라인업 {games_with_lineup}/{total_games}경기)"
    )
    return out_path


def _write_empty(out_path: Path, season: int, games_with_lineup: int, total_games: int) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps({
            "season":            season,
            "league":            "K1",
            "total_games":       total_games,
            "games_with_lineup": games_with_lineup,
            "total_gks":         0,
            "players":           [],
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description="선수(골키퍼)별 클린시트 집계")
    parser.add_argument("--season", type=int, default=2025)
    parser.add_argument("--all",    action="store_true", help="2010~현재 전체 시즌")
    args = parser.parse_args()

    from loguru import logger
    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    seasons = range(2010, 2027) if args.all else [args.season]
    for s in seasons:
        out = process_season(s)
        logger.info(f"완료: {out}")


if __name__ == "__main__":
    main()
