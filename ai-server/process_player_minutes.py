"""
match_lineups_{season}.json 에서 선수별 경기당 출전시간을 계산해
player_minutes_{season}.json 에 저장한다.

계산 규칙:
  - 선발 출전 + 교체 아웃 없음  → 90분
  - 선발 출전 + N분에 교체 아웃  → N분
  - 후보 + N분에 교체 인         → 90 - N분 (단, 연장전 고려 시 최대 120)
  - 라인업 데이터 없는 경기는 스킵

교체 데이터 소스 우선순위:
  1. match_lineups_{season}.json 의 substitutions (FotMob 크롤 시 포함)
  2. match_events_{season}.json 의 substitutions (kleague.com 크롤)

사용법:
    python process_player_minutes.py              # 2025
    python process_player_minutes.py --season 2024
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

MATCH_DURATION = 90  # 기본 경기 시간(분)


def calc_minutes_for_game(lineup: dict, substitutions: list[dict]) -> list[dict]:
    """
    한 경기의 라인업 + 교체 데이터 → 선수별 출전시간 리스트 반환.
    반환: [{"player": ..., "team": ..., "minutes": ..., "starter": bool, "subbed_off": int|None, "subbed_on": int|None}]
    """
    result = []

    # 팀별 처리
    for side in ("home", "away"):
        side_data = lineup.get(side, {})
        starters = side_data.get("starters", [])
        bench    = side_data.get("bench", [])

        # 팀명은 starters[0]["team"] 또는 bench[0]["team"] 에서 가져옴
        team_name = ""
        if starters:
            team_name = starters[0].get("team", "")
        elif bench:
            team_name = bench[0].get("team", "")

        # 해당 팀의 교체 이벤트 필터
        team_subs = [s for s in substitutions if s.get("team") == team_name] if team_name else []

        # player_off → 교체 아웃 시간
        sub_off_time: dict[str, int] = {}
        sub_on_time: dict[str, int] = {}
        for s in team_subs:
            off = s.get("player_off", "")
            on  = s.get("player_on", "")
            minute = s.get("minute", MATCH_DURATION)
            if off:
                sub_off_time[off] = minute
            if on:
                sub_on_time[on] = minute

        # 선발 선수
        for p in starters:
            name = p.get("player", "")
            if not name:
                continue
            off_min = sub_off_time.get(name)
            minutes = off_min if off_min is not None else MATCH_DURATION
            result.append({
                "player":     name,
                "team":       p.get("team", team_name),
                "minutes":    minutes,
                "starter":    True,
                "subbed_off": off_min,
                "subbed_on":  None,
            })

        # 교체 투입 선수
        for name, on_min in sub_on_time.items():
            if not name:
                continue
            minutes = max(0, MATCH_DURATION - on_min)
            result.append({
                "player":     name,
                "team":       team_name,
                "minutes":    minutes,
                "starter":    False,
                "subbed_off": None,
                "subbed_on":  on_min,
            })

    return result


def _load_events_subs(season: int) -> dict[int, list[dict]]:
    """
    match_events_{season}.json에서 game_id → 교체 이벤트 목록 반환.
    match_lineups의 substitutions가 비어있을 때 보완 소스로 사용.
    """
    events_path = ROOT / "data" / "processed" / "matches" / f"match_events_{season}.json"
    if not events_path.exists():
        return {}
    try:
        ev_data = json.loads(events_path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    result: dict[int, list[dict]] = {}
    for g in ev_data.get("events_by_game", []):
        gid = g.get("game_id")
        subs = g.get("substitutions", [])
        if gid is not None and subs:
            result[gid] = subs
    return result


def process_season(season: int) -> Path:
    """시즌의 라인업 파일을 읽어 선수별 출전시간 파일 생성."""
    from loguru import logger

    lineup_path = ROOT / "data" / "processed" / "matches" / f"match_lineups_{season}.json"
    out_path    = ROOT / "data" / "processed" / "players" / f"player_minutes_{season}.json"

    if not lineup_path.exists():
        logger.warning(f"라인업 파일 없음: {lineup_path}")
        return out_path

    data = json.loads(lineup_path.read_text(encoding="utf-8"))
    games = data.get("lineups_by_game", [])

    # match_events 교체 데이터 보완 소스 로드
    events_subs = _load_events_subs(season)
    補완_cnt = sum(
        1 for g in games
        if not g.get("substitutions") and g.get("game_id") in events_subs
    )
    if 補완_cnt:
        logger.info(f"match_events 교체 보완 대상: {補완_cnt}경기")

    # 선수별 집계: {(team, player): {..., "games": [...]}}
    player_map: dict[tuple, dict] = {}
    games_output: list[dict] = []

    for game in games:
        gid      = game.get("game_id")
        round_no = game.get("round")
        date     = game.get("date", "")
        home     = game.get("home_team", "")
        away     = game.get("away_team", "")
        hs       = game.get("home_score")
        as_      = game.get("away_score")
        lineup   = game.get("lineups", {})
        subs     = game.get("substitutions", [])

        # match_lineups에 교체 데이터 없으면 match_events 보완 소스 사용
        if not subs and gid in events_subs:
            subs = events_subs[gid]

        if not lineup:
            continue

        player_entries = calc_minutes_for_game(lineup, subs)

        game_record = {
            "game_id":    gid,
            "round":      round_no,
            "date":       date,
            "home_team":  home,
            "away_team":  away,
            "home_score": hs,
            "away_score": as_,
            "players":    player_entries,
        }
        games_output.append(game_record)

        for entry in player_entries:
            key = (entry["team"], entry["player"])
            if key not in player_map:
                player_map[key] = {
                    "player_name": entry["player"],
                    "team":        entry["team"],
                    "total_minutes": 0,
                    "appearances":   0,
                    "starter_count": 0,
                    "games": [],
                }
            pm = player_map[key]
            pm["total_minutes"] += entry["minutes"]
            pm["appearances"]   += 1
            if entry["starter"]:
                pm["starter_count"] += 1
            pm["games"].append({
                "game_id":    gid,
                "round":      round_no,
                "date":       date,
                "home_team":  home,
                "away_team":  away,
                "home_score": hs,
                "away_score": as_,
                "minutes":    entry["minutes"],
                "starter":    entry["starter"],
                "subbed_off": entry.get("subbed_off"),
                "subbed_on":  entry.get("subbed_on"),
            })

    # 정렬: 총 출전시간 내림차순
    players_list = sorted(player_map.values(), key=lambda p: -p["total_minutes"])

    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season":        season,
        "league":        "K1",
        "total_players": len(players_list),
        "players":       players_list,
        "games":         games_output,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info(f"출전시간 저장 완료: {out_path} ({len(players_list)}명, {len(games_output)}경기)")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="선수 출전시간 집계")
    parser.add_argument("--season", type=int, default=2025)
    args = parser.parse_args()

    from loguru import logger
    logger.remove()
    logger.add(sys.stderr,
               format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
               colorize=True)

    out = process_season(args.season)
    logger.info(f"완료: {out}")


if __name__ == "__main__":
    main()
