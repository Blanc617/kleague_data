"""
MatchDataEngine 조회 결과 → 자연어 컨텍스트 문자열 변환.

LLM에 주입할 정확한 컨텍스트를 만듭니다.
이 모듈은 데이터를 가공하지 않으며, 표현 방식만 변환합니다.
"""

from typing import Optional
from data_engine.match_data_engine import GameResult, GoalEvent, PlayerStat


def format_early_goal_results(
    results: list[dict],
    team: str,
    max_minute: int,
    half: str,
) -> str:
    """get_games_with_early_goal 결과를 컨텍스트 문자열로 변환."""
    if not results:
        return (
            f"[데이터 조회 결과]\n"
            f"{team}이(가) {half} {max_minute}분 이전에 득점한 경기: 0건\n"
            f"(데이터 범위: 2022~2025 K리그1)\n"
            f"조건에 해당하는 경기가 없습니다."
        )

    lines = [
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"{team}이(가) {half} {max_minute}분 이전에 득점한 경기: 총 {len(results)}건",
        f"(데이터 범위: 2022~2025 K리그1)",
        "",
    ]
    for item in results:
        game: GameResult = item["game"]
        goals: list[GoalEvent] = item["goals"]
        goal_strs = ", ".join(
            f"{g.minute}분 {g.player}" + (f"(도움: {g.assist})" if g.assist else "")
            for g in sorted(goals, key=lambda g: g.minute)
        )
        lines.append(
            f"• {game.date}  {game.home_team} {game.home_score}-{game.away_score} {game.away_team}"
            f"  [{goal_strs}]"
        )
    return "\n".join(lines)


def format_team_results(
    results: list[GameResult],
    team: str,
    season: Optional[int],
) -> str:
    """팀 경기 결과 목록을 컨텍스트 문자열로 변환."""
    season_str = f"{season} 시즌" if season else "전체"
    if not results:
        return f"[데이터 조회 결과]\n{team} {season_str} 경기: 0건"

    wins = sum(1 for r in results if r.result_for(team) == "승")
    draws = sum(1 for r in results if r.result_for(team) == "무")
    losses = sum(1 for r in results if r.result_for(team) == "패")

    lines = [
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"{team} {season_str}: 총 {len(results)}경기  {wins}승 {draws}무 {losses}패",
        "",
    ]
    for r in results:
        gf, ga = r.score_for(team)
        res = r.result_for(team)
        venue = "홈" if team in r.home_team else "원정"
        lines.append(
            f"• {r.date}  {r.home_team} {r.home_score}-{r.away_score} {r.away_team}"
            f"  ({venue}, {res})"
        )
    return "\n".join(lines)


def format_head_to_head(
    results: list[GameResult],
    team1: str,
    team2: str,
    season: Optional[int],
) -> str:
    """맞대결 기록을 컨텍스트 문자열로 변환."""
    season_str = f"{season} 시즌" if season else "전체"
    if not results:
        return f"[데이터 조회 결과]\n{team1} vs {team2} {season_str} 맞대결: 0건"

    t1_wins = sum(1 for r in results if r.result_for(team1) == "승")
    draws   = sum(1 for r in results if r.result_for(team1) == "무")
    t2_wins = sum(1 for r in results if r.result_for(team1) == "패")

    lines = [
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"{team1} vs {team2} {season_str}: 총 {len(results)}경기",
        f"{team1} {t1_wins}승 {draws}무 {t2_wins}패 ({team2} 기준)",
        "",
    ]
    for r in results:
        res1 = r.result_for(team1)
        lines.append(
            f"• {r.date}  {r.home_team} {r.home_score}-{r.away_score} {r.away_team}  ({res1})"
        )
    return "\n".join(lines)


def format_top_scorers(
    stats: list[PlayerStat],
    season: Optional[int],
) -> str:
    """득점 순위를 컨텍스트 문자열로 변환."""
    season_str = f"{season} 시즌" if season else "전체"
    if not stats:
        return f"[데이터 조회 결과]\n{season_str} 득점 순위: 데이터 없음"

    lines = [
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"{season_str} K리그1 득점 순위 (상위 {len(stats)}명):",
        "",
    ]
    for i, s in enumerate(stats, 1):
        lines.append(
            f"{i:2}. {s.player_name} ({s.team})  {s.goals}골 {s.assists}도움"
        )
    return "\n".join(lines)
