"""
/api/query  — SSE 스트리밍 자연어 질의 엔드포인트
/api/query/sync — 동기 질의 (테스트용)
"""

import asyncio
import json
import os
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

router = APIRouter()

AI_SERVER = Path(__file__).parent.parent.parent / "ai-server"

PLAYER_KEYWORDS = ["선수", "득점", "도움", "출장", "황색", "적색", "황카", "적카", "공격수", "미드필더", "수비수", "골키퍼", "득점왕", "어시스트", "몇 골", "이상 골", "이상 득점"]
MATCH_PRIORITY_KEYWORDS = ["경기", "맞대결", "전적", "결과", "이긴", "진", "무승부", "라운드", "홈", "원정"]
MINUTES_KEYWORDS = [
    "출전시간", "출전 시간", "몇 분", "몇분", "출전분", "출전 분",
    "라운드별 출전", "경기별 출전", "경기마다", "각 경기 출전",
    "선발 출전", "교체 출전", "교체로 출전", "출전 현황",
    "분 뛰었", "분 출전", "출장 시간", "출장시간",
    "출전경기", "출전 경기", "많이 출전", "출전 많", "출전 순위",
    "출전순위", "출장경기", "출장 경기", "많이 뛴", "가장 많이 뛴",
    "출전 횟수", "출전횟수", "가장 많이 출전",
    "몇 경기", "몇경기", "경기 출전", "경기 출장", "출전했", "출장했",
]
ATTENDANCE_KEYWORDS = [
    "관중", "관중수", "관중 수", "입장객", "관람객", "흥행", "매진",
    "많이 온", "많이 찾은", "최다 관중", "최고 관중", "평균 관중",
    "홈 관중", "관중 순위", "관중 현황",
]
STANDINGS_KEYWORDS = [
    "순위", "리그 테이블", "순위표", "리그순위", "리그 순위", "포인트 테이블", "몇 위", "몇위",
    "성적", "성적표", "시즌 성적", "팀 성적", "리그 성적", "승점", "몇 승", "몇승",
]
EVENT_KEYWORDS = [
    "누가 골", "누가 득점", "골 넣은", "어시스트한", "경고", "퇴장",
    "이벤트", "골 목록", "스코어러", "골 시간", "몇 분에", "몇분에",
    "득점자", "골 기록", "골을 넣", "골을 기록", "도움을 준",
    "황색 카드", "적색 카드", "카드를 받", "누가 어시스트",
    # 시간 조건 관련 (할루시네이션 방지: Python 필터링 후 LLM 전달)
    "분 이전", "분 이내", "분에 득점", "분에 골", "전반에 득점", "후반에 득점",
    "득점한 경기", "골을 넣은 경기", "선제골", "동점골", "역전골",
    "분 안에", "분 전에", "전반 내", "후반 내",
]
CLEANSHEET_KEYWORDS = [
    "클린시트", "무실점", "완봉", "클린 시트",
]
FIRSTGOAL_KEYWORDS = [
    "선제골 승률", "선제골 득점", "선제골 실점", "선제골 통계",
    "먼저 득점", "먼저 골", "먼저 실점", "선제 득점", "선제 실점",
    "선제골 시 승률", "선제골시 승률", "선제골 때", "선제골을 넣",
]
TIMEDIST_KEYWORDS = [
    "시간대별 득점", "시간대 득점", "득점 분포", "시간대별 골",
    "시간대 분포", "구간별 득점", "구간별 골", "몇 분대", "분대별",
    "전반 득점 비율", "후반 득점 비율", "득점 시간", "득점시간",
    "시간대별 실점", "시간대 실점", "실점 분포", "구간별 실점",
]
STREAK_KEYWORDS = [
    "연승", "연패", "연무", "연속 승", "연속 패", "연속 무",
    "스트릭", "streak", "무승", "무패",
    "연속 무득점", "연속 득점", "무득점 경기", "연속 클린시트",
    "연속 기록", "현재 기록", "최근 연속", "몇 연승", "몇 연패",
    "최장 연승", "최장 연패", "최다 연승", "최다 연패",
]
LINEUP_KEYWORDS = [
    "선발 명단", "선발명단", "라인업", "lineup",
    "선발 선수", "선수 명단", "선수명단",
    "출전 명단", "출전명단", "스타팅", "스타팅 11",
    "선발 11", "선발11", "몇 번 선수", "포메이션",
    "교체 명단", "벤치 명단", "벤치멤버",
]

def _is_firstgoal_query(question: str) -> bool:
    """선제골 승률/통계 질문 판별. 키워드 조합으로 유연하게 감지."""
    if any(kw in question for kw in FIRSTGOAL_KEYWORDS):
        return True
    # "선제골" + ("승률", "실점", "득점", "통계", "확률", "전적") 조합
    if "선제골" in question and any(kw in question for kw in ["승률", "실점", "득점", "통계", "확률", "전적", "승패"]):
        return True
    return False


def _is_timedist_query(question: str) -> bool:
    """시간대별 득점/실점 분포 질문 판별."""
    if any(kw in question for kw in TIMEDIST_KEYWORDS):
        return True
    # "시간대" + ("득점", "골", "실점") 조합
    if "시간대" in question and any(kw in question for kw in ["득점", "골", "실점"]):
        return True
    return False


def _build_timedist_context(question: str, season: int, season_to: int | None = None) -> str:
    """
    15분 단위 시간대별 득점(또는 실점) 분포를 Python에서 집계해 LLM에 전달.
    할루시네이션 방지: 모든 집계를 Python에서 직접 수행.
    """
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams

    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    # 실점 모드 체크
    is_conceded = any(kw in question for kw in ["실점", "먹힌 골", "먹은 골", "잃은 골"])

    # 이벤트 데이터 로드 (생성된 가짜 데이터 제외)
    all_games: list[dict] = []
    for y in range(s_from, s_to + 1):
        p = _events_path(y)
        if not p.exists():
            continue
        if _is_generated_data(p):
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        all_games.extend(data.get("events_by_game", []))

    if not all_games:
        return ""

    teams = _detect_teams(question)

    # 15분 구간 정의
    INTERVALS = [
        ("1~15분", 1, 15),
        ("16~30분", 16, 30),
        ("31~45분", 31, 45),
        ("46~60분", 46, 60),
        ("61~75분", 61, 75),
        ("76~90분", 76, 90),
        ("90+분(추가시간)", 91, 999),
    ]

    def _get_interval(minute: int) -> str:
        for label, lo, hi in INTERVALS:
            if lo <= minute <= hi:
                return label
        return "90+분(추가시간)"

    if teams:
        # 팀별 시간대 분포
        results = {}
        for team in teams:
            dist: dict[str, int] = {label: 0 for label, _, _ in INTERVALS}
            total = 0
            matched_games = [
                g for g in all_games
                if team in g.get("home_team", "") or team in g.get("away_team", "")
            ]
            num_games = len(matched_games)

            for g in matched_games:
                for e in g.get("events", []):
                    if e.get("type") not in ("goal", "own_goal"):
                        continue
                    evt_team = e.get("team", "")
                    if is_conceded:
                        # 실점: 상대 팀이 넣은 골
                        if team in evt_team:
                            continue
                    else:
                        # 득점: 해당 팀이 넣은 골
                        if team not in evt_team:
                            continue
                    interval = _get_interval(e.get("minute", 0))
                    dist[interval] += 1
                    total += 1

            results[team] = {"dist": dist, "total": total, "games": num_games}

        # 컨텍스트 문자열 구성
        label_type = "실점" if is_conceded else "득점"
        range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"
        lines = [f"[{range_label} 시즌 K리그1 시간대별 {label_type} 분포]\n"]

        for team, info in results.items():
            lines.append(f"■ {team} ({info['games']}경기, 총 {info['total']}{label_type})")
            lines.append(f"{'시간대':<16} {'골수':>4}  {'비율':>6}")
            lines.append("-" * 30)
            for label, _, _ in INTERVALS:
                cnt = info["dist"][label]
                pct = (cnt / info["total"] * 100) if info["total"] > 0 else 0
                lines.append(f"{label:<16} {cnt:>4}  {pct:>5.1f}%")
            lines.append("")

        return "\n".join(lines)

    else:
        # 전체 팀 시간대별 득점 분포
        # 팀별로 집계
        team_dist: dict[str, dict] = {}
        team_games: dict[str, int] = {}
        team_total: dict[str, int] = {}

        for g in all_games:
            ht = g.get("home_team", "")
            at = g.get("away_team", "")
            for t in [ht, at]:
                if t and t not in team_dist:
                    team_dist[t] = {label: 0 for label, _, _ in INTERVALS}
                    team_games[t] = 0
                    team_total[t] = 0
            if ht:
                team_games[ht] = team_games.get(ht, 0) + 1
            if at:
                team_games[at] = team_games.get(at, 0) + 1

            for e in g.get("events", []):
                if e.get("type") not in ("goal", "own_goal"):
                    continue
                evt_team = e.get("team", "")
                if not evt_team or evt_team not in team_dist:
                    continue
                interval = _get_interval(e.get("minute", 0))
                team_dist[evt_team][interval] += 1
                team_total[evt_team] = team_total.get(evt_team, 0) + 1

        range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"
        lines = [f"[{range_label} 시즌 K리그1 전체 팀 시간대별 득점 분포]\n"]

        # 총 득점 기준 정렬
        sorted_teams = sorted(team_total.keys(), key=lambda t: -team_total.get(t, 0))

        # 요약 테이블: 팀 | 총 득점 | 1~15분 | 16~30분 | ... | 90+분
        header = f"{'팀':<6}"
        for label, _, _ in INTERVALS:
            short = label.replace("분(추가시간)", "+")
            header += f" {short:>7}"
        header += f" {'합계':>5}"
        lines.append(header)
        lines.append("-" * 72)

        for t in sorted_teams:
            row = f"{t:<6}"
            for label, _, _ in INTERVALS:
                cnt = team_dist[t][label]
                total = team_total.get(t, 1)
                pct = cnt / total * 100 if total else 0
                row += f" {cnt:>3}({pct:.0f}%)"
            row += f" {team_total.get(t, 0):>5}"
            lines.append(row)

        lines.append("")
        # 전체 리그 시간대 합산
        league_dist = {label: 0 for label, _, _ in INTERVALS}
        league_total = 0
        for t in team_dist:
            for label, _, _ in INTERVALS:
                league_dist[label] += team_dist[t][label]
            league_total += team_total.get(t, 0)

        lines.append(f"\n■ 리그 전체 시간대별 득점 ({league_total}골)")
        for label, _, _ in INTERVALS:
            cnt = league_dist[label]
            pct = (cnt / league_total * 100) if league_total > 0 else 0
            lines.append(f"  {label:<16} {cnt:>4}골  {pct:>5.1f}%")

        return "\n".join(lines)


def _is_streak_query(question: str) -> bool:
    """연속 기록(스트릭) 질문 판별."""
    if any(kw in question for kw in STREAK_KEYWORDS):
        return True
    return False


def _build_streak_context(question: str, season: int, season_to: int | None = None) -> str:
    """
    팀별 연속 기록(연승/연패/무승/무득점/연속득점/연속클린시트 등)을 Python에서 집계.
    할루시네이션 방지: 모든 집계를 직접 수행.
    """
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams, _load_records

    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    # 이벤트 데이터 (득점 정보용, 생성된 가짜 데이터 제외)
    all_events: dict[str, dict] = {}  # "{season}_{game_id}" -> game events
    for y in range(s_from, s_to + 1):
        p = _events_path(y)
        if not p.exists():
            continue
        if _is_generated_data(p):
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for g in data.get("events_by_game", []):
            key = f"{y}_{g['game_id']}"
            all_events[key] = g

    # 경기 결과 로드
    records: list[dict] = []
    for y in range(s_from, s_to + 1):
        records.extend(_load_records(y))

    if not records:
        return ""

    teams = _detect_teams(question)

    # 홈/원정 필터 체크
    home_only = any(kw in question for kw in ["홈 연승", "홈 연패", "홈에서", "홈 경기"])
    away_only = any(kw in question for kw in ["원정 연승", "원정 연패", "원정에서", "원정 경기"])

    def _get_team_games(team: str) -> list[dict]:
        """팀의 경기를 날짜순으로 정렬해 반환 (홈/원정 필터 포함)."""
        games = []
        for r in records:
            ht, at = r.get("home_team", ""), r.get("away_team", "")
            if team not in ht and team not in at:
                continue
            if home_only and team not in ht:
                continue
            if away_only and team not in at:
                continue
            is_home = team in ht
            if is_home:
                gf, ga = r.get("home_score", 0), r.get("away_score", 0)
            else:
                gf, ga = r.get("away_score", 0), r.get("home_score", 0)
            if gf > ga:
                result = "W"
            elif gf < ga:
                result = "L"
            else:
                result = "D"

            # 득점 여부
            season_val = r.get("season", s_from)
            evt_key = f"{season_val}_{r.get('game_id')}"
            evt_game = all_events.get(evt_key)
            team_goals = 0
            team_conceded = 0
            if evt_game:
                for e in evt_game.get("events", []):
                    if e.get("type") in ("goal", "own_goal"):
                        if team in e.get("team", ""):
                            team_goals += 1
                        else:
                            team_conceded += 1
            else:
                team_goals = gf
                team_conceded = ga

            games.append({
                "date": r.get("date", ""),
                "round": r.get("round"),
                "home_team": ht,
                "away_team": at,
                "home_score": r.get("home_score", 0),
                "away_score": r.get("away_score", 0),
                "result": result,
                "gf": gf,
                "ga": ga,
                "team_goals": team_goals,
                "team_conceded": team_conceded,
                "is_home": is_home,
            })
        games.sort(key=lambda g: g["date"])
        return games

    def _calc_streaks(games: list[dict]) -> dict:
        """경기 리스트에서 각종 연속 기록 계산. 경기 정보 포함."""
        if not games:
            return {}

        def _longest_streak_with_games(seq: list[bool], games_list: list[dict]) -> tuple[int, list[dict]]:
            """연속 True의 최장 길이와 해당 경기 리스트."""
            best, cur = 0, 0
            best_games: list[dict] = []
            cur_games: list[dict] = []
            for i, v in enumerate(seq):
                if v:
                    cur += 1
                    cur_games.append(games_list[i])
                    if cur > best:
                        best = cur
                        best_games = list(cur_games)
                else:
                    cur = 0
                    cur_games = []
            return best, best_games

        def _current_streak_with_games(seq: list[bool], games_list: list[dict]) -> tuple[int, list[dict]]:
            """현재(가장 최근부터) 연속 True 개수와 해당 경기 리스트."""
            streak_games: list[dict] = []
            for i in range(len(seq) - 1, -1, -1):
                if seq[i]:
                    streak_games.append(games_list[i])
                else:
                    break
            streak_games.reverse()
            return len(streak_games), streak_games

        wins = [g["result"] == "W" for g in games]
        losses = [g["result"] == "L" for g in games]
        draws = [g["result"] == "D" for g in games]
        unbeaten = [g["result"] != "L" for g in games]
        winless = [g["result"] != "W" for g in games]
        scoring = [g["team_goals"] > 0 for g in games]
        scoreless = [g["team_goals"] == 0 for g in games]
        cleansheet = [g["team_conceded"] == 0 for g in games]

        best_win, best_win_g = _longest_streak_with_games(wins, games)
        best_loss, best_loss_g = _longest_streak_with_games(losses, games)
        best_draw, best_draw_g = _longest_streak_with_games(draws, games)
        best_unbeaten, best_unbeaten_g = _longest_streak_with_games(unbeaten, games)
        best_winless, best_winless_g = _longest_streak_with_games(winless, games)
        best_scoring, best_scoring_g = _longest_streak_with_games(scoring, games)
        best_scoreless, best_scoreless_g = _longest_streak_with_games(scoreless, games)
        best_cs, best_cs_g = _longest_streak_with_games(cleansheet, games)

        cur_win, cur_win_g = _current_streak_with_games(wins, games)
        cur_loss, cur_loss_g = _current_streak_with_games(losses, games)
        cur_draw, cur_draw_g = _current_streak_with_games(draws, games)
        cur_unbeaten, cur_unbeaten_g = _current_streak_with_games(unbeaten, games)
        cur_winless, cur_winless_g = _current_streak_with_games(winless, games)
        cur_scoring, cur_scoring_g = _current_streak_with_games(scoring, games)
        cur_scoreless, cur_scoreless_g = _current_streak_with_games(scoreless, games)
        cur_cs, cur_cs_g = _current_streak_with_games(cleansheet, games)

        total = len(games)
        w = sum(wins)
        d = sum(draws)
        l_ = sum(losses)

        return {
            "total": total, "w": w, "d": d, "l": l_,
            "best_win": best_win, "best_win_games": best_win_g,
            "cur_win": cur_win, "cur_win_games": cur_win_g,
            "best_loss": best_loss, "best_loss_games": best_loss_g,
            "cur_loss": cur_loss, "cur_loss_games": cur_loss_g,
            "best_draw": best_draw, "best_draw_games": best_draw_g,
            "cur_draw": cur_draw, "cur_draw_games": cur_draw_g,
            "best_unbeaten": best_unbeaten, "best_unbeaten_games": best_unbeaten_g,
            "cur_unbeaten": cur_unbeaten, "cur_unbeaten_games": cur_unbeaten_g,
            "best_winless": best_winless, "best_winless_games": best_winless_g,
            "cur_winless": cur_winless, "cur_winless_games": cur_winless_g,
            "best_scoring": best_scoring, "best_scoring_games": best_scoring_g,
            "cur_scoring": cur_scoring, "cur_scoring_games": cur_scoring_g,
            "best_scoreless": best_scoreless, "best_scoreless_games": best_scoreless_g,
            "cur_scoreless": cur_scoreless, "cur_scoreless_games": cur_scoreless_g,
            "best_cs": best_cs, "best_cs_games": best_cs_g,
            "cur_cs": cur_cs, "cur_cs_games": cur_cs_g,
            "last5": [g["result"] for g in games[-5:]],
        }

    def _fmt_game(g: dict) -> str:
        """경기 한 줄 포맷: R3 서울 2:1 울산 (H) 2025.03.01"""
        loc = "H" if g["is_home"] else "A"
        return f"R{g['round']} {g['home_team']} {g['home_score']}:{g['away_score']} {g['away_team']} ({loc}) {g['date']}"

    def _fmt_streak_block(label: str, cur: int, cur_games: list[dict], best: int, best_games: list[dict]) -> list[str]:
        """연속 기록 한 항목을 경기 목록과 함께 포맷."""
        block = []
        block.append(f"  ● {label}: 현재 {cur}경기 / 시즌최장 {best}경기")
        if best > 0 and best_games:
            block.append(f"    [시즌최장 {best}{label} 경기 목록]")
            for g in best_games:
                block.append(f"      {_fmt_game(g)}")
        if cur > 0 and cur_games and cur_games != best_games:
            block.append(f"    [현재 진행 중 {cur}{label} 경기 목록]")
            for g in cur_games:
                block.append(f"      {_fmt_game(g)}")
        return block

    range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"
    loc_label = "홈" if home_only else ("원정" if away_only else "전체")
    lines = [f"[{range_label} 시즌 K리그1 연속 기록 ({loc_label})]\n"]

    if teams:
        for team in teams:
            games = _get_team_games(team)
            if not games:
                lines.append(f"■ {team}: 해당 시즌 경기 데이터 없음\n")
                continue

            s = _calc_streaks(games)
            last5_str = " ".join(s["last5"])

            lines.append(f"■ {team} ({s['total']}경기 {s['w']}승 {s['d']}무 {s['l']}패)")
            lines.append(f"  최근 5경기 폼: {last5_str}")
            lines.append("")

            # 각 연속 기록 + 경기 목록
            lines.extend(_fmt_streak_block("연승", s["cur_win"], s["cur_win_games"], s["best_win"], s["best_win_games"]))
            lines.append("")
            lines.extend(_fmt_streak_block("연패", s["cur_loss"], s["cur_loss_games"], s["best_loss"], s["best_loss_games"]))
            lines.append("")
            lines.extend(_fmt_streak_block("연속 무승부", s["cur_draw"], s["cur_draw_games"], s["best_draw"], s["best_draw_games"]))
            lines.append("")
            lines.extend(_fmt_streak_block("무패 행진", s["cur_unbeaten"], s["cur_unbeaten_games"], s["best_unbeaten"], s["best_unbeaten_games"]))
            lines.append("")
            lines.extend(_fmt_streak_block("무승 행진", s["cur_winless"], s["cur_winless_games"], s["best_winless"], s["best_winless_games"]))
            lines.append("")
            lines.extend(_fmt_streak_block("연속 득점", s["cur_scoring"], s["cur_scoring_games"], s["best_scoring"], s["best_scoring_games"]))
            lines.append("")
            lines.extend(_fmt_streak_block("연속 무득점", s["cur_scoreless"], s["cur_scoreless_games"], s["best_scoreless"], s["best_scoreless_games"]))
            lines.append("")
            lines.extend(_fmt_streak_block("연속 클린시트", s["cur_cs"], s["cur_cs_games"], s["best_cs"], s["best_cs_games"]))
            lines.append("")

        return "\n".join(lines)

    else:
        # 전체 팀 비교 — 현재 연승/연패/무패 기록이 눈에 띄는 팀
        all_teams_set: set[str] = set()
        for r in records:
            ht = r.get("home_team", "")
            at = r.get("away_team", "")
            if ht:
                all_teams_set.add(ht)
            if at:
                all_teams_set.add(at)

        team_streaks: list[tuple[str, dict]] = []
        for t in sorted(all_teams_set):
            games = _get_team_games(t)
            if not games:
                continue
            s = _calc_streaks(games)
            team_streaks.append((t, s))

        def _fmt_team_streak(t: str, s: dict, key: str, label: str) -> list[str]:
            """전체 팀 비교에서 한 팀의 기록 + 경기 목록."""
            rows = []
            cnt = s[key]
            games_key = f"{key}_games"
            g_list = s.get(games_key, [])
            last5 = " ".join(s["last5"])
            rows.append(f"  {t}: {cnt}{label} (최근5: {last5})")
            for g in g_list:
                rows.append(f"    {_fmt_game(g)}")
            return rows

        # 현재 연승 Top
        lines.append("■ 현재 연승 기록")
        for t, s in sorted(team_streaks, key=lambda x: -x[1]["cur_win"]):
            if s["cur_win"] > 0:
                lines.extend(_fmt_team_streak(t, s, "cur_win", "연승 중"))
        lines.append("")

        # 현재 연패 Top
        lines.append("■ 현재 연패 기록")
        for t, s in sorted(team_streaks, key=lambda x: -x[1]["cur_loss"]):
            if s["cur_loss"] > 0:
                lines.extend(_fmt_team_streak(t, s, "cur_loss", "연패 중"))
        lines.append("")

        # 현재 무패 Top
        lines.append("■ 현재 무패 행진")
        for t, s in sorted(team_streaks, key=lambda x: -x[1]["cur_unbeaten"]):
            if s["cur_unbeaten"] >= 3:
                lines.extend(_fmt_team_streak(t, s, "cur_unbeaten", "경기 무패"))
        lines.append("")

        # 시즌 최장 연승
        lines.append("■ 시즌 최장 연승 기록")
        for t, s in sorted(team_streaks, key=lambda x: -x[1]["best_win"])[:5]:
            lines.extend(_fmt_team_streak(t, s, "best_win", "연승"))
        lines.append("")

        # 시즌 최장 무패
        lines.append("■ 시즌 최장 무패 기록")
        for t, s in sorted(team_streaks, key=lambda x: -x[1]["best_unbeaten"])[:5]:
            lines.extend(_fmt_team_streak(t, s, "best_unbeaten", "경기 무패"))
        lines.append("")

        # 연속 득점 / 연속 무득점
        lines.append("■ 현재 연속 득점")
        for t, s in sorted(team_streaks, key=lambda x: -x[1]["cur_scoring"]):
            if s["cur_scoring"] >= 3:
                lines.extend(_fmt_team_streak(t, s, "cur_scoring", "경기 연속 득점 중"))
        lines.append("")

        lines.append("■ 현재 연속 무득점")
        for t, s in sorted(team_streaks, key=lambda x: -x[1]["cur_scoreless"]):
            if s["cur_scoreless"] > 0:
                lines.extend(_fmt_team_streak(t, s, "cur_scoreless", "경기 연속 무득점 중"))

        return "\n".join(lines)


DETAIL_KEYWORDS = [
    "상세", "상세 정보", "자세히", "디테일", "detail",
    "경기 정보", "경기정보", "매치 정보", "매치정보",
]

BRIEFING_KEYWORDS = [
    "브리핑", "브리핑시트", "브리핑 시트",
    "프리뷰", "preview",
    "경기 전 자료", "경기전 자료", "경기 전 정보", "경기전 정보",
    "사전 자료", "사전 정보", "사전 브리핑",
    "경기 준비 자료", "경기준비",
    "두 팀 비교", "팀 비교 자료",
    "해설 자료", "캐스터 자료",
]


def _is_briefing_query(question: str) -> bool:
    return any(kw in question for kw in BRIEFING_KEYWORDS)


def _build_briefing_context(question: str, season: int = 2025, season_to: int | None = None) -> str:
    """
    두 팀 경기 전 브리핑 시트 컨텍스트 생성.
    순위·폼·홈원정·득점자·선제골승률·맞대결 전적을 Python에서 직접 집계.
    """
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams, _load_records
    from routers.stats import calculate_standings, _filter_league_only

    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    teams = _detect_teams(question)
    if len(teams) < 2:
        return ""

    team_a, team_b = teams[0], teams[1]
    range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"

    # 경기 기록 로드
    records: list[dict] = []
    for y in range(s_from, s_to + 1):
        records.extend(_load_records(y))
    seen: set = set()
    unique: list[dict] = []
    for r in records:
        gid = r.get("game_id")
        if gid not in seen:
            seen.add(gid)
            unique.append(r)
    league_records = _filter_league_only(unique)

    # 이벤트 데이터 로드 (선제골용, 생성된 가짜 데이터 제외)
    events_by_gid: dict[int, list] = {}
    for y in range(s_from, s_to + 1):
        p = _events_path(y)
        if not p.exists():
            continue
        if _is_generated_data(p):
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for g in data.get("events_by_game", []):
            events_by_gid[g["game_id"]] = g.get("events", [])

    # 순위표 계산
    standings_rows = calculate_standings(league_records)
    standings_by_team = {r["team"]: r for r in standings_rows}

    def get_team_standing(team: str) -> dict | None:
        for t, s in standings_by_team.items():
            if team in t or t in team:
                return s
        return None

    def fmt_standing(team: str) -> str:
        s = get_team_standing(team)
        if not s:
            return f"{team}: 순위 데이터 없음"
        gd = f"+{s['gd']}" if s['gd'] > 0 else str(s['gd'])
        return (
            f"{s['rank']}위 | {s['games']}경기 {s['win']}승{s['draw']}무{s['lose']}패 "
            f"| 승점 {s['points']} | 득점 {s['gf']} 실점 {s['ga']} 득실 {gd}"
        )

    # 최근 5경기 폼
    def get_recent_form(team: str, n: int = 5) -> tuple[list[dict], str]:
        team_games = [
            r for r in sorted(league_records, key=lambda x: x.get("date", ""))
            if team in r.get("home_team", "") or team in r.get("away_team", "")
        ]
        recent = team_games[-n:]
        form_chars = []
        for r in recent:
            is_home = team in r.get("home_team", "")
            gf = r["home_score"] if is_home else r["away_score"]
            ga = r["away_score"] if is_home else r["home_score"]
            if gf > ga:
                form_chars.append("W")
            elif gf < ga:
                form_chars.append("L")
            else:
                form_chars.append("D")
        return recent, " ".join(form_chars)

    def fmt_recent_games(games: list[dict], team: str) -> list[str]:
        lines = []
        for r in games:
            is_home = team in r.get("home_team", "")
            venue = "홈" if is_home else "원정"
            gf = r["home_score"] if is_home else r["away_score"]
            ga = r["away_score"] if is_home else r["home_score"]
            result = "승" if gf > ga else ("패" if gf < ga else "무")
            opp = r["away_team"] if is_home else r["home_team"]
            lines.append(
                f"  {r.get('date','?')} R{r.get('round','?')} vs {opp} ({venue}) {gf}-{ga} {result}"
            )
        return lines

    # 홈/원정 성적
    def get_home_away_record(team: str) -> str:
        home_games = [r for r in league_records if team in r.get("home_team", "")]
        away_games = [r for r in league_records if team in r.get("away_team", "")]

        def _calc(games: list[dict], is_home: bool) -> dict:
            w = d = l_ = gf = ga = 0
            for r in games:
                g = r["home_score"] if is_home else r["away_score"]
                c = r["away_score"] if is_home else r["home_score"]
                gf += g; ga += c
                if g > c: w += 1
                elif g < c: l_ += 1
                else: d += 1
            n = len(games)
            wr = round(w / n * 100, 1) if n else 0
            return {"n": n, "w": w, "d": d, "l": l_, "gf": gf, "ga": ga, "wr": wr}

        h = _calc(home_games, True)
        a = _calc(away_games, False)
        return (
            f"  홈:  {h['n']}경기 {h['w']}승{h['d']}무{h['l']}패 | "
            f"득점 {h['gf']} 실점 {h['ga']} | 승률 {h['wr']}%\n"
            f"  원정: {a['n']}경기 {a['w']}승{a['d']}무{a['l']}패 | "
            f"득점 {a['gf']} 실점 {a['ga']} | 승률 {a['wr']}%"
        )

    # 주요 득점자
    def get_top_scorers_for_team(team: str, n: int = 5) -> list[dict]:
        players: list[dict] = []
        for y in range(s_from, s_to + 1):
            p_path = AI_SERVER / "data" / "processed" / "players" / f"player_stats_{y}.json"
            if not p_path.exists():
                continue
            data = json.loads(p_path.read_text(encoding="utf-8"))
            for p in data.get("players", []):
                if team in p.get("team", ""):
                    players.append(p)
        agg: dict[str, dict] = {}
        for p in players:
            key = p["player_name"]
            if key not in agg:
                agg[key] = {
                    "player_name": key, "team": p.get("team", team),
                    "goals": 0, "assists": 0, "appearances": 0,
                }
            agg[key]["goals"] += p.get("goals", 0)
            agg[key]["assists"] += p.get("assists", 0)
            agg[key]["appearances"] += p.get("appearances", 0)
        return sorted(agg.values(), key=lambda x: (x["goals"], x["assists"]), reverse=True)[:n]

    # 선제골 승률
    def get_firstgoal_rate(team: str) -> str:
        sf_w = sf_d = sf_l = cf_w = cf_d = cf_l = 0
        for r in league_records:
            ht, at = r.get("home_team", ""), r.get("away_team", "")
            if team not in ht and team not in at:
                continue
            hs, aws = r.get("home_score", 0), r.get("away_score", 0)
            gid = r.get("game_id")
            evts = events_by_gid.get(gid, [])
            goals = sorted(
                [e for e in evts if e.get("type") in ("goal", "own_goal")],
                key=lambda e: e.get("minute", 999),
            )
            if not goals:
                continue
            first = goals[0]
            first_team = first.get("team", "")
            if first["type"] == "own_goal":
                scored_first = at if (team in ht) else ht
            else:
                scored_first = ht if (team in first_team or first_team in ht) else at

            # 팀 입장 결과
            is_home = team in ht
            if hs > aws:
                home_res = "W"
            elif hs == aws:
                home_res = "D"
            else:
                home_res = "L"
            team_res = home_res if is_home else (
                "W" if home_res == "L" else ("L" if home_res == "W" else "D")
            )

            if team in scored_first or scored_first in team:
                if team_res == "W": sf_w += 1
                elif team_res == "D": sf_d += 1
                else: sf_l += 1
            else:
                if team_res == "W": cf_w += 1
                elif team_res == "D": cf_d += 1
                else: cf_l += 1

        sf_total = sf_w + sf_d + sf_l
        cf_total = cf_w + cf_d + cf_l
        sf_wr = round(sf_w / sf_total * 100, 1) if sf_total else 0
        cf_wr = round(cf_w / cf_total * 100, 1) if cf_total else 0
        return (
            f"  선제골 득점 시: {sf_total}경기 {sf_w}승{sf_d}무{sf_l}패 (승률 {sf_wr}%)\n"
            f"  선제골 허용 시: {cf_total}경기 {cf_w}승{cf_d}무{cf_l}패 (승률 {cf_wr}%)"
        )

    # 맞대결 전적
    h2h = sorted(
        [
            r for r in league_records
            if (team_a in r.get("home_team", "") and team_b in r.get("away_team", ""))
            or (team_b in r.get("home_team", "") and team_a in r.get("away_team", ""))
        ],
        key=lambda r: r.get("date", ""),
    )
    a_wins = sum(
        1 for r in h2h
        if (team_a in r["home_team"] and r["home_score"] > r["away_score"])
        or (team_a in r["away_team"] and r["away_score"] > r["home_score"])
    )
    b_wins = sum(
        1 for r in h2h
        if (team_b in r["home_team"] and r["home_score"] > r["away_score"])
        or (team_b in r["away_team"] and r["away_score"] > r["home_score"])
    )
    h2h_draws = len(h2h) - a_wins - b_wins

    # 컨텍스트 조립
    lines = [
        f"[경기 전 브리핑 시트 — {range_label}시즌 K리그1]",
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"대상 경기: {team_a} vs {team_b}",
        "",
    ]

    for team in [team_a, team_b]:
        lines.append(f"━━━ {team} ━━━")

        lines += [f"▶ 시즌 순위·성적:", f"  {fmt_standing(team)}", ""]

        recent_games, form_str = get_recent_form(team)
        lines += [f"▶ 최근 {len(recent_games)}경기 폼: {form_str}"]
        lines += fmt_recent_games(recent_games, team)
        lines.append("")

        lines.append("▶ 홈/원정 성적:")
        lines.append(get_home_away_record(team))
        lines.append("")

        scorers = get_top_scorers_for_team(team)
        if scorers:
            lines.append("▶ 주요 득점자 (Top 5):")
            for i, p in enumerate(scorers, 1):
                lines.append(
                    f"  {i}. {p['player_name']} — {p['goals']}골 {p['assists']}도움 ({p['appearances']}경기)"
                )
            lines.append("")

        lines.append("▶ 선제골 승률:")
        lines.append(get_firstgoal_rate(team))
        lines.append("")

    lines += [
        f"━━━ 맞대결 전적 ({team_a} vs {team_b}) ━━━",
        f"총 {len(h2h)}경기: {team_a} {a_wins}승 {h2h_draws}무 {b_wins}패 ({team_b} 기준)",
    ]
    if h2h:
        lines.append("최근 5경기:")
        for r in h2h[-5:]:
            lines.append(
                f"  {r.get('date','?')} R{r.get('round','?')} "
                f"{r['home_team']} {r['home_score']}-{r['away_score']} {r['away_team']}"
            )
    lines.append("")

    return "\n".join(lines)

def _lineups_path(season: int) -> Path:
    return AI_SERVER / "data" / "processed" / "matches" / f"match_lineups_{season}.json"


def _load_lineups(season: int) -> list[dict]:
    """match_lineups_{season}.json → 실제 선발 데이터가 있는 경기 목록만 반환.
    round가 0인 경우 k1_team_results.json의 game_id → round 매핑으로 보완."""
    p = _lineups_path(season)
    if not p.exists():
        return []
    data = json.loads(p.read_text(encoding="utf-8"))
    games = data.get("lineups_by_game", [])

    # 실제 선발 선수 데이터가 있는 경기만 유지
    games = [
        g for g in games
        if g.get("lineups", {}).get("home", {}).get("starters")
        or g.get("lineups", {}).get("away", {}).get("starters")
    ]
    if not games:
        return []

    # round가 0인 경기는 k1_team_results.json에서 보완
    if any(g.get("round", 0) == 0 for g in games):
        results_path = AI_SERVER / "data" / "processed" / "teams" / "k1_team_results.json"
        round_map: dict[int, int] = {}
        if results_path.exists():
            records = json.loads(results_path.read_text(encoding="utf-8"))
            for r in records:
                if r.get("season") == season and r.get("game_id") and r.get("round"):
                    round_map[r["game_id"]] = r["round"]
        for g in games:
            if g.get("round", 0) == 0:
                gid = g.get("game_id")
                if gid and gid in round_map:
                    g["round"] = round_map[gid]

    return games


def _is_lineup_query(question: str) -> bool:
    return any(kw in question for kw in LINEUP_KEYWORDS)


def _build_lineup_context(question: str, season: int = 2025) -> str:
    """
    라인업 질문에 대한 컨텍스트 문자열 반환.

    질문에서 팀명과 라운드/날짜를 추출해 match_lineups_{season}.json에서 경기를 찾습니다.
    팀명이 없으면 라운드 번호로만 검색합니다.
    """
    import re
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams

    NO_DATA_SEASONS = "2013(일부), 2015~2019, 2022~2026"

    games = _load_lineups(season)
    if not games:
        return (
            f"[라인업 데이터 없음]\n"
            f"{season}시즌의 선발 명단 데이터가 존재하지 않습니다.\n"
            f"실제 데이터가 있는 시즌: {NO_DATA_SEASONS}\n"
            f"해당 시즌에 대해서는 선발 명단을 제공할 수 없습니다."
        )

    # 팀 추출
    teams = _detect_teams(question)

    # 라운드 번호 추출 (예: "1라운드", "R1", "1R")
    round_num: int | None = None
    m = re.search(r"(\d{1,3})\s*(?:라운드|round|R)", question, re.IGNORECASE)
    if not m:
        m = re.search(r"R\s*(\d{1,3})", question, re.IGNORECASE)
    if m:
        round_num = int(m.group(1))

    # 날짜 추출 (예: "2월 15일", "02.15")
    date_hint: str | None = None
    m = re.search(r"(\d{1,2})[월./-](\d{1,2})[일]?", question)
    if m:
        date_hint = f"{int(m.group(1)):02d}.{int(m.group(2)):02d}"

    # 경기 필터링
    matched: list[dict] = []
    for g in games:
        home = g.get("home_team", "")
        away = g.get("away_team", "")

        if teams:
            if len(teams) >= 2:
                t1, t2 = teams[0], teams[1]
                if not (
                    (t1 in home and t2 in away) or (t2 in home and t1 in away)
                ):
                    continue
            else:
                t = teams[0]
                if t not in home and t not in away:
                    continue

        if round_num is not None and g.get("round") != round_num:
            continue

        if date_hint and date_hint not in g.get("date", ""):
            continue

        matched.append(g)

    if not matched:
        hint = ""
        if teams:
            hint += f" 팀: {', '.join(teams)}"
        if round_num:
            hint += f" {round_num}라운드"
        return (
            f"[라인업 데이터 조회 결과]\n"
            f"{season}시즌{hint} 라인업 데이터를 찾지 못했습니다.\n"
            f"(실제 데이터 보유 시즌: 2013(일부), 2015~2019, 2022~2026)"
        )

    # 여러 경기 매칭 시 첫 번째 경기 사용 (팀+라운드 특정 시 보통 1건)
    g = matched[0]
    home_team = g.get("home_team", "")
    away_team = g.get("away_team", "")
    date = g.get("date", "")
    round_str = g.get("round", "")
    home_score = g.get("home_score", "-")
    away_score = g.get("away_score", "-")

    lineups = g.get("lineups", {})

    # substitutions가 비어있으면 match_events에서 보완
    subs = g.get("substitutions") or []
    if not subs:
        events_data = _load_events(season)
        ev_game = events_data.get(g["game_id"], {})
        subs = ev_game.get("substitutions", [])

    # 교체 아웃 선수가 선발 명단에 없으면 선발에 추가 (데이터 결함 보완)
    def _patch_starters(side_data: dict, team_name: str, team_subs: list[dict]) -> dict:
        """교체 아웃된 선수가 선발에 없으면 추가해 데이터 결함 보완."""
        starters = list(side_data.get("starters", []))
        starter_names = {p["player"] for p in starters}
        for s in team_subs:
            off = s.get("player_off", "")
            if off and off not in starter_names:
                starters.append({"player": off, "team": team_name, "position": "?", "jersey": "?"})
                starter_names.add(off)
        return {**side_data, "starters": starters}

    home_subs = [s for s in subs if home_team in s.get("team", "")]
    away_subs = [s for s in subs if away_team in s.get("team", "")]

    home_lineups = _patch_starters(lineups.get("home", {}), home_team, home_subs)
    away_lineups = _patch_starters(lineups.get("away", {}), away_team, away_subs)

    def _fmt_side(side_data: dict, team_name: str) -> list[str]:
        lines = []
        starters = side_data.get("starters", [])
        bench = side_data.get("bench", [])
        lines.append(f"  [선발 11인]")
        for p in starters:
            pos = p.get("position", "")
            jersey = p.get("jersey", "")
            name = p.get("player", "")
            lines.append(f"    #{jersey} {name} ({pos})")
        if bench:
            lines.append(f"  [벤치]")
            for p in bench:
                pos = p.get("position", "")
                jersey = p.get("jersey", "")
                name = p.get("player", "")
                lines.append(f"    #{jersey} {name} ({pos})")
        return lines

    def _fmt_subs(team_subs: list[dict]) -> list[str]:
        if not team_subs:
            return []
        lines = ["  [교체]"]
        for s in sorted(team_subs, key=lambda x: x.get("minute", 0)):
            off = s.get("player_off", "")
            on = s.get("player_on", "")
            minute = s.get("minute", "?")
            if on:
                lines.append(f"    {minute}' {off} → {on}")
            elif off:
                lines.append(f"    {minute}' {off} OUT")
        return lines

    lines = [
        "[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"{season}시즌 {round_str}라운드  {date}",
        f"{home_team} {home_score}-{away_score} {away_team}",
        "",
        f"▶ {home_team} (홈)",
    ]
    lines += _fmt_side(home_lineups, home_team)
    lines += _fmt_subs(home_subs)
    lines += ["", f"▶ {away_team} (원정)"]
    lines += _fmt_side(away_lineups, away_team)
    lines += _fmt_subs(away_subs)

    if len(matched) > 1:
        lines.append(
            f"\n※ 조건에 맞는 경기가 {len(matched)}건 있어 첫 번째 경기를 표시했습니다. "
            "라운드나 날짜를 함께 말씀해 주세요."
        )

    return "\n".join(lines)


def _events_path(season: int) -> Path:
    return AI_SERVER / "data" / "processed" / "matches" / f"match_events_{season}.json"


def _is_generated_data(path: Path) -> bool:
    """데이터 파일이 실제 크롤링이 아닌 랜덤 생성 데이터인지 확인합니다."""
    if not path.exists():
        return False
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data.get("source") == "generated"
    except Exception:
        return False


def _load_events(season: int = 2025) -> dict:
    """match_events_{season}.json 로드 → game_id 키 딕셔너리 반환.
    생성된 가짜 데이터는 로드하지 않습니다."""
    p = _events_path(season)
    if not p.exists():
        return {}
    if _is_generated_data(p):
        return {}
    data = json.loads(p.read_text(encoding="utf-8"))
    return {g["game_id"]: g for g in data.get("events_by_game", [])}


def _is_event_query(question: str) -> bool:
    return any(kw in question for kw in EVENT_KEYWORDS)


def _parse_event_conditions(question: str) -> dict:
    """
    질문에서 이벤트 필터 조건을 추출.
    Python에서 직접 필터링해 LLM 할루시네이션 방지.
    """
    import re
    cond: dict = {}

    # 시간 조건: "N분 이전/이내/전에/안에"
    m = re.search(r'(\d+)\s*분\s*(?:이전|이내|전에|안에|미만)', question)
    if m:
        cond["minute_before"] = int(m.group(1))

    # 시간 조건: "N분 이후/넘어/부터"
    m = re.search(r'(\d+)\s*분\s*(?:이후|넘어|부터|초과|이상)', question)
    if m:
        cond["minute_after"] = int(m.group(1))

    # 전반(1-45분) / 후반(46-90분)
    if "전반에 득점" in question or "전반에 골" in question:
        cond["half"] = "first"
    elif "후반에 득점" in question or "후반에 골" in question:
        cond["half"] = "second"

    # 이벤트 타입
    if any(kw in question for kw in ["득점", "골을 넣", "스코어", "선제골", "동점골", "역전골"]):
        cond["event_types"] = {"goal", "own_goal"}
    elif any(kw in question for kw in ["경고", "황색 카드", "황카"]):
        cond["event_types"] = {"yellow_card"}
    elif any(kw in question for kw in ["퇴장", "적색 카드", "적카"]):
        cond["event_types"] = {"red_card", "yellow_red"}
    elif any(kw in question for kw in ["카드"]):
        cond["event_types"] = {"yellow_card", "red_card", "yellow_red"}

    return cond


def _filter_games_by_condition(games: list[dict], teams: list[str], cond: dict) -> list[dict]:
    """
    Python에서 직접 조건 필터링.
    조건에 맞는 이벤트가 하나라도 있는 경기만 반환.
    """
    if not cond:
        return games

    minute_before = cond.get("minute_before")
    minute_after  = cond.get("minute_after")
    half          = cond.get("half")
    event_types   = cond.get("event_types")

    filtered = []
    for g in games:
        evts = g.get("events", [])
        found = False
        for e in evts:
            # 팀 조건: 특정 팀의 이벤트인지 확인
            if teams:
                evt_team = e.get("team", "")
                if not any(t in evt_team for t in teams):
                    continue

            # 이벤트 타입 조건
            if event_types and e.get("type") not in event_types:
                continue

            minute = e.get("minute", 999)

            # 시간 조건
            if minute_before is not None and minute >= minute_before:
                continue
            if minute_after is not None and minute <= minute_after:
                continue
            if half == "first" and minute > 45:
                continue
            if half == "second" and minute <= 45:
                continue

            found = True
            break

        if found:
            filtered.append(g)

    return filtered


def _build_event_context(question: str, season: int = 2025, season_to: int | None = None) -> tuple[str, list[dict]]:
    """경기 이벤트 컨텍스트 구성.
    Python에서 팀·시간·이벤트 조건을 직접 필터링 후 LLM에 전달.
    LLM이 필터링을 다시 하지 않으므로 할루시네이션 차단.
    """
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams

    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    all_games: list[dict] = []
    for y in range(s_from, s_to + 1):
        p = _events_path(y)
        if not p.exists():
            continue
        if _is_generated_data(p):
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        all_games.extend(data.get("events_by_game", []))

    if not all_games:
        return "", []

    teams = _detect_teams(question)

    # 1차: 팀 필터
    if len(teams) >= 2:
        t1, t2 = teams[0], teams[1]
        matched = [g for g in all_games
                   if (t1 in g.get("home_team","") and t2 in g.get("away_team",""))
                   or (t2 in g.get("home_team","") and t1 in g.get("away_team",""))]
    elif len(teams) == 1:
        t = teams[0]
        matched = [g for g in all_games
                   if t in g.get("home_team","") or t in g.get("away_team","")]
    else:
        matched = list(all_games)

    # 2차: 이벤트 조건 Python 직접 필터링 (LLM에 맡기지 않음)
    cond = _parse_event_conditions(question)
    if cond:
        matched = _filter_games_by_condition(matched, teams, cond)

    matched = sorted(matched, key=lambda g: g.get("date", ""))[:30]

    lines = []
    source_events = []
    for g in matched:
        evts = g.get("events", [])
        header = f"{g['date']} {g['home_team']} {g['home_score']}-{g['away_score']} {g['away_team']}"
        detail_parts = []
        for e in evts:
            t = e["type"]
            if t == "goal":
                assist_str = f" (도움: {e['assist']})" if e.get("assist") else ""
                detail_parts.append(f"  ⚽ {e['minute']}분 [{e['team']}] {e['player']}{assist_str}")
            elif t == "own_goal":
                detail_parts.append(f"  ⚽ {e['minute']}분 [{e['team']}] {e['player']} (자책골)")
            elif t == "yellow_card":
                detail_parts.append(f"  🟨 {e['minute']}분 [{e['team']}] {e['player']} 경고")
            elif t in ("red_card", "yellow_red"):
                detail_parts.append(f"  🟥 {e['minute']}분 [{e['team']}] {e['player']} 퇴장")

        if detail_parts:
            lines.append(header)
            lines.extend(detail_parts)
            source_events.append({
                "game_id":    g.get("game_id"),
                "date":       g["date"],
                "home_team":  g["home_team"],
                "away_team":  g["away_team"],
                "home_score": g["home_score"],
                "away_score": g["away_score"],
                "events":     evts,
            })

    context = "\n".join(lines) if lines else ""
    return context, source_events


class QueryRequest(BaseModel):
    question: str
    season: int = 2025
    season_to: int | None = None


def _is_detail_query(question: str) -> bool:
    """특정 경기 상세 정보 질문인지 판별."""
    return any(kw in question for kw in DETAIL_KEYWORDS)


def _build_detail_context(question: str, season: int = 2025, season_to: int | None = None) -> tuple[str, list[dict]]:
    """특정 경기 상세 정보 컨텍스트 구성.
    경기 기록(스코어, 관중, 경기장) + 이벤트(득점, 경고, 퇴장)를 합침.
    """
    import re
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams, _load_records

    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    q_season = _extract_season_from_question(question) or s_from
    teams = _detect_teams(question)
    round_num = _extract_round(question)

    # 경기 기록 로드
    records: list[dict] = []
    for y in range(s_from, s_to + 1):
        records.extend(_load_records(y))

    # k1_team_results에 해당 시즌 데이터가 없으면 match_events 파일에서 보완
    loaded_seasons = {r.get("season") for r in records}
    for y in range(s_from, s_to + 1):
        if y not in loaded_seasons:
            p = _events_path(y)
            if p.exists() and not _is_generated_data(p):
                ev_data = json.loads(p.read_text(encoding="utf-8"))
                for g in ev_data.get("events_by_game", []):
                    records.append({
                        "game_id":    g.get("game_id"),
                        "season":     y,
                        "round":      g.get("round"),
                        "date":       g.get("date", ""),
                        "home_team":  g.get("home_team", ""),
                        "away_team":  g.get("away_team", ""),
                        "home_score": g.get("home_score"),
                        "away_score": g.get("away_score"),
                    })

    # game_id 중복 제거
    seen, unique = set(), []
    for r in records:
        gid = r.get("game_id")
        if gid not in seen:
            seen.add(gid)
            unique.append(r)

    # 팀 + 라운드로 필터
    matched = unique
    if teams:
        if len(teams) >= 2:
            t1, t2 = teams[0], teams[1]
            matched = [r for r in matched
                       if (t1 in r.get("home_team", "") and t2 in r.get("away_team", ""))
                       or (t2 in r.get("home_team", "") and t1 in r.get("away_team", ""))]
        else:
            t = teams[0]
            matched = [r for r in matched if t in r.get("home_team", "") or t in r.get("away_team", "")]

    if round_num is not None:
        round_filtered = [r for r in matched if r.get("round") == round_num]
        if round_filtered:
            matched = round_filtered
        # 라운드 정보 없는 경우 필터 건너뜀 (하위 날짜 필터 또는 팀 필터 결과 그대로 사용)

    # 날짜 파싱: "3월 1일", "03.01" 등
    date_match = re.search(r'(\d{1,2})\s*월\s*(\d{1,2})\s*일', question)
    if date_match:
        m, d = int(date_match.group(1)), int(date_match.group(2))
        date_str = f"{q_season}.{m:02d}.{d:02d}"
        matched = [r for r in matched if r.get("date") == date_str]

    if not matched:
        return "", []

    # 최대 5경기까지만
    matched = sorted(matched, key=lambda r: r.get("date", ""))[:5]

    # 이벤트 데이터 로드 (game_id로 매칭, 생성된 가짜 데이터 제외)
    events_by_gid: dict[int, list] = {}
    for y in range(s_from, s_to + 1):
        p = _events_path(y)
        if not p.exists():
            continue
        if _is_generated_data(p):
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        for g in data.get("events_by_game", []):
            events_by_gid[g["game_id"]] = g.get("events", [])

    lines = []
    source_events = []
    for r in matched:
        gid = r.get("game_id")
        evts = events_by_gid.get(gid, [])
        att = r.get("attendance", 0)
        venue = r.get("venue", "")
        time_str = r.get("time", "")

        lines.append(f"=== 경기 상세 정보 ===")
        lines.append(f"날짜: {r['date']} {time_str}")
        lines.append(f"라운드: {r.get('round', '?')}라운드")
        lines.append(f"홈팀: {r['home_team']}")
        lines.append(f"원정팀: {r['away_team']}")
        lines.append(f"스코어: {r['home_score']} - {r['away_score']}")
        lines.append(f"경기장: {venue}")
        if att:
            lines.append(f"관중: {att:,}명")

        goals = [e for e in evts if e["type"] in ("goal", "own_goal")]
        yellows = [e for e in evts if e["type"] == "yellow_card"]
        reds = [e for e in evts if e["type"] in ("red_card", "yellow_red")]

        if goals:
            lines.append(f"\n[득점 기록]")
            for e in goals:
                assist_str = f" (도움: {e['assist']})" if e.get("assist") else ""
                og_str = " (자책골)" if e["type"] == "own_goal" else ""
                lines.append(f"  ⚽ {e['minute']}분 [{e['team']}] {e['player']}{assist_str}{og_str}")

        if yellows:
            lines.append(f"\n[경고]")
            for e in yellows:
                lines.append(f"  🟨 {e['minute']}분 [{e['team']}] {e['player']}")

        if reds:
            lines.append(f"\n[퇴장]")
            for e in reds:
                lines.append(f"  🟥 {e['minute']}분 [{e['team']}] {e['player']}")

        if not evts:
            lines.append(f"\n(이벤트 상세 데이터 없음)")

        lines.append("")

        source_events.append({
            "game_id": gid,
            "date": r["date"],
            "home_team": r["home_team"],
            "away_team": r["away_team"],
            "home_score": r["home_score"],
            "away_score": r["away_score"],
            "events": evts[:15],
        })

    context = "\n".join(lines)
    return context, source_events


def _build_firstgoal_context(question: str, season: int = 2025, season_to: int | None = None) -> str:
    """선제골 득점/실점 시 승률 집계 컨텍스트."""
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams, _load_records
    from routers.stats import _filter_league_only

    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    # 경기 기록 로드 (승패 판정용)
    records: list[dict] = []
    for y in range(s_from, s_to + 1):
        records.extend(_load_records(y))
    seen, unique = set(), []
    for r in records:
        gid = r.get("game_id")
        if gid not in seen:
            seen.add(gid)
            unique.append(r)
    records = _filter_league_only(unique)
    rec_by_gid = {r.get("game_id"): r for r in records}

    # 이벤트 로드 (선제골 판정용, 생성된 가짜 데이터 제외)
    all_events: list[dict] = []
    for y in range(s_from, s_to + 1):
        p = _events_path(y)
        if not p.exists():
            continue
        if _is_generated_data(p):
            continue
        data = json.loads(p.read_text(encoding="utf-8"))
        all_events.extend(data.get("events_by_game", []))

    if not all_events:
        range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"
        return f"[데이터 없음] {range_label}시즌 이벤트 데이터가 없습니다."

    # 팀별 집계: {team: {scored_first: {W,D,L}, conceded_first: {W,D,L}, no_goal: int}}
    stats: dict[str, dict] = {}

    def ensure(team: str):
        if team not in stats:
            stats[team] = {
                "sf_w": 0, "sf_d": 0, "sf_l": 0,  # scored first → win/draw/lose
                "cf_w": 0, "cf_d": 0, "cf_l": 0,  # conceded first → win/draw/lose
                "ng": 0,  # 무득점 무실점 (0-0)
            }

    for g in all_events:
        gid = g.get("game_id")
        rec = rec_by_gid.get(gid)
        if not rec:
            continue

        ht = rec["home_team"]
        at = rec["away_team"]
        hs = rec["home_score"]
        aws = rec["away_score"]
        ensure(ht)
        ensure(at)

        # 첫 골 찾기
        goals = [e for e in g.get("events", []) if e.get("type") in ("goal", "own_goal")]
        if not goals:
            # 0-0 경기이거나 이벤트가 없음
            if hs == 0 and aws == 0:
                stats[ht]["ng"] += 1
                stats[at]["ng"] += 1
            continue

        goals.sort(key=lambda e: e.get("minute", 999))
        first = goals[0]
        first_team = first.get("team", "")

        # 자책골이면 상대팀이 득점한 것
        if first["type"] == "own_goal":
            # 자책골 = 상대팀에게 선제골 허용
            if first_team == ht or any(t in first_team for t in [ht]):
                scored_first_team = at
            else:
                scored_first_team = ht
        else:
            # 어느 팀이 선제골?
            if first_team == ht or any(t in first_team for t in [ht]):
                scored_first_team = ht
            else:
                scored_first_team = at

        conceded_first_team = at if scored_first_team == ht else ht

        # 경기 결과 판정
        if hs > aws:
            home_result = "W"
        elif hs == aws:
            home_result = "D"
        else:
            home_result = "L"

        sf_result = home_result if scored_first_team == ht else (
            "W" if home_result == "L" else ("L" if home_result == "W" else "D")
        )
        cf_result = "W" if sf_result == "L" else ("L" if sf_result == "W" else "D")

        stats[scored_first_team][f"sf_{sf_result.lower()}"] += 1
        stats[conceded_first_team][f"cf_{cf_result.lower()}"] += 1

    if not stats:
        return ""

    teams_filter = _detect_teams(question)
    range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"

    rows = []
    for team, s in stats.items():
        sf_total = s["sf_w"] + s["sf_d"] + s["sf_l"]
        cf_total = s["cf_w"] + s["cf_d"] + s["cf_l"]
        rows.append({
            "team": team,
            "sf_total": sf_total,
            "sf_w": s["sf_w"], "sf_d": s["sf_d"], "sf_l": s["sf_l"],
            "sf_wr": round(s["sf_w"] / sf_total * 100, 1) if sf_total else 0,
            "cf_total": cf_total,
            "cf_w": s["cf_w"], "cf_d": s["cf_d"], "cf_l": s["cf_l"],
            "cf_wr": round(s["cf_w"] / cf_total * 100, 1) if cf_total else 0,
            "ng": s["ng"],
        })

    if teams_filter:
        rows = [r for r in rows if any(t in r["team"] for t in teams_filter)]

    rows.sort(key=lambda r: -r["sf_wr"])

    lines = [
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"K리그1 {range_label}시즌 선제골 득점/실점 시 승률 현황:",
        "",
        "▶ 선제골 득점 시 (먼저 골을 넣었을 때):",
        f"{'팀':8}  {'경기':>4}  {'승':>3}  {'무':>3}  {'패':>3}  {'승률':>6}",
        "─" * 38,
    ]
    for r in rows:
        lines.append(
            f"{r['team']:8}  {r['sf_total']:>4}  {r['sf_w']:>3}  {r['sf_d']:>3}  {r['sf_l']:>3}  {r['sf_wr']:>5.1f}%"
        )

    rows.sort(key=lambda r: -r["cf_wr"])
    lines += [
        "",
        "▶ 선제골 실점 시 (먼저 골을 허용했을 때):",
        f"{'팀':8}  {'경기':>4}  {'승':>3}  {'무':>3}  {'패':>3}  {'승률':>6}",
        "─" * 38,
    ]
    for r in rows:
        lines.append(
            f"{r['team']:8}  {r['cf_total']:>4}  {r['cf_w']:>3}  {r['cf_d']:>3}  {r['cf_l']:>3}  {r['cf_wr']:>5.1f}%"
        )

    return "\n".join(lines)


def _is_cleansheet_query(question: str) -> bool:
    return any(kw in question for kw in CLEANSHEET_KEYWORDS)


def _build_cleansheet_context(question: str, season: int = 2025, season_to: int | None = None) -> str:
    """클린시트(무실점) 집계 컨텍스트 생성."""
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams, _load_records
    from routers.stats import _filter_league_only

    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    q_season_from = _extract_season_from_question(question) or s_from

    records: list[dict] = []
    for y in range(q_season_from, s_to + 1):
        records.extend(_load_records(y))

    # game_id 중복 제거
    seen, unique = set(), []
    for r in records:
        gid = r.get("game_id")
        if gid not in seen:
            seen.add(gid)
            unique.append(r)

    records = _filter_league_only(unique)
    if not records:
        range_label = str(q_season_from) if q_season_from == s_to else f"{q_season_from}~{s_to}"
        return f"[데이터 없음] {range_label}시즌 경기 기록이 없습니다."

    teams = _detect_teams(question)

    # 팀별 클린시트 집계
    team_cs: dict[str, dict] = {}
    cs_games: list[dict] = []  # 클린시트 경기 목록

    for r in records:
        hs, aws = r.get("home_score", 0), r.get("away_score", 0)
        ht, at = r["home_team"], r["away_team"]

        for team_name, is_home in [(ht, True), (at, False)]:
            if team_name not in team_cs:
                team_cs[team_name] = {"team": team_name, "games": 0, "cs": 0, "home_cs": 0, "away_cs": 0}
            t = team_cs[team_name]
            t["games"] += 1

            ga = aws if is_home else hs
            if ga == 0:
                t["cs"] += 1
                if is_home:
                    t["home_cs"] += 1
                else:
                    t["away_cs"] += 1
                # 특정 팀 필터 시 경기 목록에 추가
                if teams and any(tm in team_name for tm in teams):
                    cs_games.append({
                        "date": r.get("date", ""),
                        "round": r.get("round", ""),
                        "home": ht,
                        "away": at,
                        "score": f"{hs}-{aws}",
                        "venue": r.get("venue", ""),
                        "cs_team": team_name,
                        "location": "홈" if is_home else "원정",
                    })

    rows = sorted(team_cs.values(), key=lambda x: (-x["cs"], -x["home_cs"]))
    for i, row in enumerate(rows, 1):
        row["rank"] = i
        row["cs_rate"] = round(row["cs"] / row["games"] * 100, 1) if row["games"] else 0

    range_label = str(q_season_from) if q_season_from == s_to else f"{q_season_from}~{s_to}"

    lines = [
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"K리그1 {range_label}시즌 클린시트(무실점) 현황 ({len(records)}경기 기준):",
        "",
        "▶ 팀별 클린시트 순위:",
        f"{'순위':>3}  {'팀':8}  {'경기':>4}  {'클린시트':>6}  {'홈CS':>4}  {'원정CS':>5}  {'CS비율':>6}",
        "─" * 50,
    ]
    for row in rows:
        lines.append(
            f"{row['rank']:>3}  {row['team']:8}  {row['games']:>4}  {row['cs']:>6}  "
            f"{row['home_cs']:>4}  {row['away_cs']:>5}  {row['cs_rate']:>5.1f}%"
        )

    # 특정 팀 지정 시 해당 팀 클린시트 경기 목록도 추가
    if teams and cs_games:
        cs_games.sort(key=lambda x: x["date"])
        lines += ["", f"▶ {'/'.join(teams)} 클린시트 경기 목록:"]
        for g in cs_games:
            lines.append(
                f"  {g['date']} {g['round']}R {g['home']} {g['score']} {g['away']} "
                f"({g['location']}) [{g['venue']}]"
            )

    # ── 선수(골키퍼)별 클린시트 순위 ──────────────────
    player_cs_rows: list[dict] = []
    games_with_lineup_total = 0
    for y in range(q_season_from, s_to + 1):
        cs_path = AI_SERVER / "data" / "processed" / "players" / f"player_cleansheets_{y}.json"
        if cs_path.exists():
            cs_data = json.loads(cs_path.read_text(encoding="utf-8"))
            games_with_lineup_total += cs_data.get("games_with_lineup", 0)
            for p in cs_data.get("players", []):
                # 멀티시즌일 경우 같은 선수가 여러 시즌에 걸칠 수 있으므로 합산
                key = (p["team"], p["player_name"])
                existing = next((r for r in player_cs_rows if (r["team"], r["player_name"]) == key), None)
                if existing:
                    existing["clean_sheets"] += p["clean_sheets"]
                    existing["cs_home"]      += p["cs_home"]
                    existing["cs_away"]      += p["cs_away"]
                    existing["games_played"] += p["games_played"]
                else:
                    player_cs_rows.append({
                        "player_name":  p["player_name"],
                        "team":         p["team"],
                        "clean_sheets": p["clean_sheets"],
                        "cs_home":      p["cs_home"],
                        "cs_away":      p["cs_away"],
                        "games_played": p["games_played"],
                    })

    if player_cs_rows:
        player_cs_rows.sort(key=lambda x: (-x["clean_sheets"], -x["cs_home"]))
        for i, r in enumerate(player_cs_rows, 1):
            r["rank"] = i
            r["cs_rate"] = round(r["clean_sheets"] / r["games_played"] * 100, 1) if r["games_played"] else 0.0

        # 특정 팀 필터 시 해당 팀만 표시, 아니면 전체 Top 20
        if teams:
            filtered = [r for r in player_cs_rows if any(tm in r["team"] for tm in teams)]
        else:
            filtered = player_cs_rows[:20]

        if filtered:
            lines += [
                "",
                "▶ 선수(골키퍼)별 클린시트 순위:",
                f"{'순위':>3}  {'선수':8}  {'팀':8}  {'경기':>4}  {'클린시트':>6}  {'홈CS':>4}  {'원정CS':>5}  {'CS비율':>6}",
                "─" * 60,
            ]
            for r in filtered:
                lines.append(
                    f"{r['rank']:>3}  {r['player_name']:8}  {r['team']:8}  {r['games_played']:>4}  "
                    f"{r['clean_sheets']:>6}  {r['cs_home']:>4}  {r['cs_away']:>5}  {r['cs_rate']:>5.1f}%"
                )
            lines.append(f"  ※ 라인업 데이터 기준: {games_with_lineup_total}경기 반영")
    else:
        lines += [
            "",
            "▶ 선수(골키퍼)별 클린시트: 라인업 데이터 없음 (run_crawl_lineups.py 실행 후 재조회)",
        ]

    return "\n".join(lines)


def _is_standings_query(question: str) -> bool:
    # 선수 관련 키워드가 함께 있으면 순위표가 아니라 선수 쿼리임
    player_hints = ["선수", "득점왕", "어시스트", "공격수", "미드필더", "수비수", "골키퍼", "개인", "도움왕"]
    if any(kw in question for kw in player_hints):
        return False
    return any(kw in question for kw in STANDINGS_KEYWORDS)


def _is_attendance_query(question: str) -> bool:
    return any(kw in question for kw in ATTENDANCE_KEYWORDS)


def _is_minutes_query(question: str) -> bool:
    return any(kw in question for kw in MINUTES_KEYWORDS)


def _build_attendance_context(question: str, season: int = 2025, season_to: int | None = None) -> str:
    """관중 질문에 대한 정확한 집계 컨텍스트 생성."""
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from routers.stats import _load_unique_records, _filter_league_only

    s_from = season
    s_to   = season_to if season_to is not None else season
    q_season = _extract_season_from_question(question) or s_from

    # 범위 지원: q_season ~ s_to
    q_season_to = s_to if s_to and s_to >= q_season else q_season
    records = _filter_league_only(_load_unique_records(q_season, q_season_to))
    att_records = [r for r in records if r.get("attendance") and r["attendance"] > 0]
    if not att_records:
        label_s = str(q_season) if q_season == q_season_to else f"{q_season}~{q_season_to}"
        return f"[데이터 없음] {label_s}시즌 관중 데이터가 없습니다."

    # 질문에 특정 팀이 언급된 경우 해당 팀 경기별 상세 포함
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams
    mentioned_teams = _detect_teams(question)

    # 팀별 홈 관중 집계
    team_home: dict[str, dict] = {}
    for r in att_records:
        ht = r["home_team"]
        if ht not in team_home:
            team_home[ht] = {"games": 0, "total": 0, "max": 0, "records": []}
        t = team_home[ht]
        t["games"] += 1
        t["total"] += r["attendance"]
        t["max"] = max(t["max"], r["attendance"])
        t["records"].append(r)

    team_rows = sorted(
        [{"team": ht, **{k: v for k, v in v.items() if k != "records"}, "avg": round(v["total"] / v["games"])} for ht, v in team_home.items()],
        key=lambda r: -r["avg"],
    )

    top10 = sorted(att_records, key=lambda r: -r["attendance"])[:10]
    total_att = sum(r["attendance"] for r in att_records)
    label_s = str(q_season) if q_season == q_season_to else f"{q_season}~{q_season_to}"

    lines = [
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"K리그1 {label_s}시즌 관중 현황 ({len(att_records)}경기 기준):",
        f"시즌 총 관중: {total_att:,}명 | 경기당 평균: {total_att // len(att_records):,}명",
        "",
        "▶ 팀별 홈 평균 관중 순위:",
        f"{'순위':>3}  {'팀':8}  {'경기':>4}  {'합계':>8}  {'평균':>7}  {'최대':>7}",
        "─" * 50,
    ]
    for i, row in enumerate(team_rows, 1):
        lines.append(
            f"{i:>3}  {row['team']:8}  {row['games']:>4}  {row['total']:>8,}  {row['avg']:>7,}  {row['max']:>7,}"
        )

    lines += ["", "▶ 최다 관중 TOP 10 경기:"]
    for r in top10:
        lines.append(
            f"  {r['date']} {r['home_team']} vs {r['away_team']} — {r['attendance']:,}명"
            f" [{r.get('venue','')}]"
        )

    # 특정 팀 언급 시: 해당 팀의 전체 경기별 관중 수 추가
    if mentioned_teams:
        for team in mentioned_teams:
            team_records = sorted(
                [r for r in att_records if team in r.get("home_team", "") or team in r.get("away_team", "")],
                key=lambda r: r.get("date", ""),
            )
            if team_records:
                lines += ["", f"▶ {team} 경기별 관중 수 ({len(team_records)}경기):"]
                for r in team_records:
                    venue_tag = "(홈)" if team in r["home_team"] else "(원정)"
                    att_str = f"{r['attendance']:,}명" if r.get("attendance") else "정보없음"
                    lines.append(
                        f"  {r['date']} {r['round']}R {r['home_team']} {r['home_score']}-{r['away_score']} {r['away_team']}"
                        f" {venue_tag} 관중:{att_str} [{r.get('venue','')}]"
                    )

    return "\n".join(lines)


def _build_minutes_context(question: str, season: int = 2025) -> str:
    """선수 출전시간/출전경기 질문에 대한 컨텍스트 생성.

    우선순위:
      1) player_minutes_{season}.json  — 경기별 실제 출전분 포함 (라인업 크롤 필요)
      2) player_stats_{season}.json    — appearances(출전경기수) 기반 폴백
    """
    import re
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from run_ingest import _detect_teams

    # ── 데이터 소스 결정 ──────────────────────────────
    minutes_path = AI_SERVER / "data" / "processed" / "players" / f"player_minutes_{season}.json"
    stats_path   = AI_SERVER / "data" / "processed" / "players" / f"player_stats_{season}.json"

    use_minutes = False
    players: list[dict] = []
    data_label = ""

    if minutes_path.exists() and not _is_generated_data(minutes_path):
        raw = json.loads(minutes_path.read_text(encoding="utf-8"))
        if raw.get("players"):
            players = raw["players"]
            use_minutes = True
            data_label = f"출전시간(분) 기준 — 라인업 데이터 {raw.get('total_players', 0)}명"

    if not players and stats_path.exists():
        raw = json.loads(stats_path.read_text(encoding="utf-8"))
        stats_players = raw.get("players", [])
        if stats_players:
            # player_stats → player_minutes 형식으로 변환 (출전시간 미상 → appearances 기준)
            players = [
                {
                    "player_name":   p["player_name"],
                    "team":          p["team"],
                    "total_minutes": None,          # 실제 분 데이터 없음
                    "appearances":   p.get("appearances", 0),
                    "starter_count": p.get("appearances", 0),  # 선발/교체 구분 불가
                    "games":         [],
                }
                for p in stats_players
            ]
            data_label = f"출전경기수 기준 (라인업 미수집 — 실제 출전분 미반영) — {len(players)}명"

    if not players:
        return f"[데이터 없음] {season}시즌 출전 데이터가 없습니다."

    teams = _detect_teams(question)

    # ── 선수 이름 감지 ────────────────────────────────
    team_keywords = {
        "전북", "울산", "서울", "수원", "포항", "인천", "전남", "광주", "강원", "성남",
        "제주", "대전", "김천", "수원FC", "대구", "시즌", "라운드", "경기", "선수",
        "출전", "출장", "순위", "많이", "가장", "뛰었", "시간",
    }
    name_candidates = re.findall(r'[가-힣]{2,5}', question)
    name_candidates = [n for n in name_candidates if n not in team_keywords]

    matched_players: list[dict] = []
    for name in name_candidates:
        found = [p for p in players if name in p.get("player_name", "")]
        if teams:
            found = [p for p in found if any(t in p.get("team", "") for t in teams)]
        matched_players.extend(found)

    # 중복 제거
    seen: set = set()
    unique_matched: list[dict] = []
    for p in matched_players:
        k = (p["player_name"], p["team"])
        if k not in seen:
            seen.add(k)
            unique_matched.append(p)

    header = f"[데이터 직접 조회 결과 — 할루시네이션 없음]\nK리그1 {season}시즌 선수 출전 현황 ({data_label}):"

    # ── Case 1: 특정 선수 지정 ────────────────────────
    if unique_matched:
        lines = [header, ""]
        for p in unique_matched[:3]:
            if use_minutes and p.get("total_minutes") is not None:
                avg = round(p["total_minutes"] / p["appearances"], 1) if p["appearances"] else 0
                lines += [
                    f"▶ {p['player_name']} ({p['team']}) — 총 {p['total_minutes']}분 / {p['appearances']}경기 "
                    f"(선발 {p.get('starter_count', 0)}회, 평균 {avg}분)",
                    f"{'라운드':>4}  {'날짜':10}  {'홈팀':8}  {'원정팀':8}  {'스코어':6}  {'출전':>5}  {'비고'}",
                    "─" * 62,
                ]
                for g in sorted(p.get("games", []), key=lambda g: (g.get("date", ""), g.get("round", 0))):
                    note = ""
                    if g.get("subbed_off") is not None:
                        note = f"{g['subbed_off']}분 교체아웃"
                    elif g.get("subbed_on") is not None:
                        note = f"{g['subbed_on']}분 교체인"
                    elif g.get("starter"):
                        note = "선발"
                    lines.append(
                        f"{str(g.get('round','?'))+'R':>4}  {g.get('date',''):10}  "
                        f"{g.get('home_team',''):8}  {g.get('away_team',''):8}  "
                        f"{g.get('home_score','?')}-{g.get('away_score','?'):<6}  "
                        f"{g.get('minutes', 0):>4}분  {note}"
                    )
            else:
                lines.append(
                    f"▶ {p['player_name']} ({p['team']}) — {p['appearances']}경기 출전"
                    + (" (출전시간 데이터 미수집)" if not use_minutes else "")
                )
        return "\n".join(lines)

    # ── Case 2: 팀 지정 (선수 미지정) ────────────────
    if teams:
        team_players = [p for p in players if any(t in p.get("team", "") for t in teams)]
        if not team_players:
            return f"[데이터 없음] {season}시즌 {'/'.join(teams)} 출전 데이터가 없습니다."
        team_players.sort(key=lambda p: -(p["total_minutes"] or 0) if use_minutes else -p["appearances"])
        lines = [
            header, "",
            f"{'선수명':8}  {'팀':8}  {'경기':>3}  {'선발':>3}  {'총 출전시간':>10}  {'경기평균':>7}",
            "─" * 50,
        ]
        for p in team_players[:30]:
            if use_minutes and p.get("total_minutes") is not None:
                avg = round(p["total_minutes"] / p["appearances"], 1) if p["appearances"] else 0
                lines.append(
                    f"{p['player_name']:8}  {p['team']:8}  {p['appearances']:>3}  "
                    f"{p.get('starter_count', 0):>3}  {p['total_minutes']:>8}분  {avg:>6.1f}분"
                )
            else:
                lines.append(
                    f"{p['player_name']:8}  {p['team']:8}  {p['appearances']:>3}경기  (출전시간 미수집)"
                )
        return "\n".join(lines)

    # ── Case 3: 전체 순위 (팀/선수 미지정) ───────────
    if use_minutes:
        ranked = sorted(players, key=lambda p: -(p["total_minutes"] or 0))
    else:
        ranked = sorted(players, key=lambda p: -p["appearances"])

    top_n = 30
    lines = [
        header, "",
        f"▶ 출전 {'시간' if use_minutes else '경기수'} 상위 {top_n}명:",
        f"{'순위':>3}  {'선수명':8}  {'팀':8}  {'경기':>3}  {'선발':>3}  "
        + (f"{'총 출전시간':>10}  {'경기평균':>7}" if use_minutes else ""),
        "─" * (60 if use_minutes else 40),
    ]
    for i, p in enumerate(ranked[:top_n], 1):
        if use_minutes and p.get("total_minutes") is not None:
            avg = round(p["total_minutes"] / p["appearances"], 1) if p["appearances"] else 0
            lines.append(
                f"{i:>3}  {p['player_name']:8}  {p['team']:8}  {p['appearances']:>3}  "
                f"{p.get('starter_count', 0):>3}  {p['total_minutes']:>8}분  {avg:>6.1f}분"
            )
        else:
            lines.append(
                f"{i:>3}  {p['player_name']:8}  {p['team']:8}  {p['appearances']:>3}경기"
            )
    return "\n".join(lines)


def _extract_round(question: str) -> int | None:
    import re
    m = re.search(r"(\d+)\s*라운드", question)
    return int(m.group(1)) if m else None


def _extract_season_from_question(question: str) -> int | None:
    import re
    m = re.search(r"(20\d{2})\s*(?:시즌|년)?", question)
    return int(m.group(1)) if m else None


def _build_standings_context(question: str, season: int = 2025) -> str:
    """순위 질문에 대한 정확한 순위표 컨텍스트 생성."""
    import sys
    sys.path.insert(0, str(AI_SERVER))
    from routers.stats import _load_unique_records, calculate_standings, _filter_league_only

    q_season = _extract_season_from_question(question) or season
    round_to = _extract_round(question)

    records = _filter_league_only(_load_unique_records(q_season, q_season))
    if not records:
        return f"[데이터 없음] {q_season}시즌 경기 기록이 없습니다."

    if round_to is not None:
        filtered = [r for r in records if (r.get("round") or 0) <= round_to]
        label = f"{q_season}시즌 {round_to}라운드까지"
    else:
        filtered = records
        label = f"{q_season}시즌 전체"

    rows = calculate_standings(filtered)
    if not rows:
        return f"[데이터 없음] {label} 집계 가능한 경기가 없습니다."

    lines = [
        f"[데이터 직접 조회 결과 — 할루시네이션 없음]",
        f"K리그1 {label} 순위표 ({len(rows)}팀, {len(filtered)}경기 기준):",
        f"순위 결정 기준: 승점 → 다득점 → 득실차",
        "",
        f"{'순위':>3}  {'팀명':<8}  {'경기':>3}  {'승':>2}  {'무':>2}  {'패':>2}  {'승점':>3}  {'득점':>3}  {'득실':>4}  {'실점':>3}",
        "─" * 55,
    ]
    for r in rows:
        gd_str = f"+{r['gd']}" if r['gd'] > 0 else str(r['gd'])
        lines.append(
            f"{r['rank']:>3}  {r['team']:<8}  {r['games']:>3}  {r['win']:>2}  {r['draw']:>2}  {r['lose']:>2}  "
            f"{r['points']:>3}  {r['gf']:>3}  {gd_str:>4}  {r['ga']:>3}"
        )
    return "\n".join(lines)


def _is_player_query(question: str) -> bool:
    has_player_kw = any(kw in question for kw in PLAYER_KEYWORDS)
    if not has_player_kw:
        return False
    # "선수 득점 순위" 같은 경우 선수 쿼리 우선
    strong_player = ["선수", "득점왕", "어시스트왕", "도움왕", "공격수", "미드필더", "수비수", "골키퍼"]
    if any(kw in question for kw in strong_player):
        return True
    # 경기 맞대결 키워드가 강하면 경기 쿼리 우선
    if any(kw in question for kw in MATCH_PRIORITY_KEYWORDS):
        return False
    return True


def _build_player_context(question: str, season: int = 2025, season_to: int | None = None) -> tuple[str, list[dict]]:
    """선수 관련 질문에 대한 컨텍스트를 구성합니다."""
    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    # 2010~2012는 Wikipedia 출처 (상위 6~7명, 영어 이름, appearances=0) — 제외하여 데이터 오염 방지
    WIKIPEDIA_SEASONS = {2010, 2011, 2012}
    wiki_excluded = [y for y in range(s_from, s_to + 1) if y in WIKIPEDIA_SEASONS]

    raw_players: list[dict] = []
    for y in range(s_from, s_to + 1):
        if y in WIKIPEDIA_SEASONS:
            continue
        player_path = AI_SERVER / "data" / "processed" / "players" / f"player_stats_{y}.json"
        if not player_path.exists():
            continue
        if _is_generated_data(player_path):
            continue
        data = json.loads(player_path.read_text(encoding="utf-8"))
        for p in data.get("players", []):
            raw_players.append({**p, "_season": y})

    if not raw_players:
        if wiki_excluded:
            return (
                f"[선수 데이터 없음]\n"
                f"{s_from}~{s_to} 범위 중 {wiki_excluded}년은 공식 선수 통계가 없습니다(위키피디아 제한 데이터 제외).\n"
                f"2013년 이후 시즌을 선택하시면 정확한 데이터를 조회할 수 있습니다."
            ), []
        return "", []

    is_multi_season = s_from != s_to

    # 다중 시즌이면 동일 선수 기록 합산
    if is_multi_season:
        agg: dict[str, dict] = {}
        for p in raw_players:
            key = p.get("player_name", "")
            if not key:
                continue
            if key not in agg:
                agg[key] = {
                    "player_name": key,
                    "team": p.get("team", ""),
                    "position": p.get("position", ""),
                    "appearances": 0, "goals": 0, "assists": 0,
                    "yellow_cards": 0, "red_cards": 0, "own_goals": 0,
                    "_teams": set(),
                    "_seasons": set(),
                }
            a = agg[key]
            a["appearances"] += p.get("appearances", 0)
            a["goals"]       += p.get("goals", 0)
            a["assists"]     += p.get("assists", 0)
            a["yellow_cards"]+= p.get("yellow_cards", 0)
            a["red_cards"]   += p.get("red_cards", 0)
            a["own_goals"]   += p.get("own_goals", 0)
            a["_teams"].add(p.get("team", ""))
            a["_seasons"].add(p.get("_season"))
            # 최신 팀/포지션으로 업데이트
            a["team"] = p.get("team", a["team"])
            a["position"] = p.get("position", "") or a["position"]

        players: list[dict] = []
        for a in agg.values():
            teams_set = a.pop("_teams")
            seasons_set = a.pop("_seasons")
            # 여러 팀 소속이면 표시
            a["team"] = "/".join(sorted(teams_set)) if len(teams_set) > 1 else a["team"]
            a["_season_count"] = len(seasons_set)
            players.append(a)
    else:
        players = raw_players

    # 팀 필터
    from run_ingest import _detect_teams
    teams = _detect_teams(question)
    if teams:
        players = [p for p in players if any(t in p.get("team", "") for t in teams)]

    # 포지션 필터
    pos_map = {"공격수": "FW", "포워드": "FW", "미드필더": "MF", "수비수": "DF", "골키퍼": "GK"}
    for ko, en in pos_map.items():
        if ko in question:
            players = [p for p in players if p.get("position") == en]
            break

    # 득점/도움 최솟값 추출 (e.g. "3골 이상", "2득점 이상")
    import re
    min_goals = 0
    min_assists = 0
    goal_match = re.search(r"(\d+)\s*(?:골|득점)(?:\s*이상)?", question)
    assist_match = re.search(r"(\d+)\s*(?:도움|어시스트)(?:\s*이상)?", question)
    if goal_match:
        min_goals = int(goal_match.group(1))
        players = [p for p in players if p.get("goals", 0) >= min_goals]
    if assist_match:
        min_assists = int(assist_match.group(1))
        players = [p for p in players if p.get("assists", 0) >= min_assists]

    # 도움 관련 질문이면 도움 우선 정렬, 아니면 득점 우선 정렬
    # 동률 시 경기수 적은 선수 우선 (공식 kleague 기준)
    assist_keywords = ["도움", "어시스트", "assist"]
    if any(kw in question for kw in assist_keywords):
        players.sort(key=lambda p: (-p.get("assists", 0), p.get("appearances", 999), -p.get("goals", 0)))
    else:
        players.sort(key=lambda p: (-p.get("goals", 0), p.get("appearances", 999), -p.get("assists", 0)))

    range_label = str(s_from) if s_from == s_to else f"{s_from}~{s_to}"
    is_multi = s_from != s_to

    lines = []
    for p in players:
        position = p.get("position", "")
        pos_str = f" ({position})" if position else ""
        own_goals = p.get("own_goals", 0)
        og_str = f" 자책골{own_goals}" if own_goals else ""
        season_count = p.get("_season_count", 1)
        agg_str = f" [{season_count}시즌 합산]" if is_multi else ""
        lines.append(
            f"{p['team']} {p['player_name']}{pos_str}{agg_str} — "
            f"{p['appearances']}경기 {p['goals']}골 {p['assists']}도움{og_str} "
            f"황카{p['yellow_cards']} 적카{p['red_cards']}"
        )

    header_note = " (아래 수치는 해당 기간 전 시즌 합산)" if is_multi else ""
    context = f"[{range_label} 시즌 K리그1 선수 기록{header_note}]\n" + "\n".join(lines) if lines else ""
    return context, players


def _check_generated_seasons(s_from: int, s_to: int) -> str | None:
    """요청한 시즌 범위에 생성된 가짜 데이터가 있는지 확인하고 경고 메시지를 반환합니다."""
    generated_seasons = []
    for y in range(s_from, s_to + 1):
        events_p = _events_path(y)
        if events_p.exists() and _is_generated_data(events_p):
            generated_seasons.append(y)
        minutes_p = AI_SERVER / "data" / "processed" / "players" / f"player_minutes_{y}.json"
        if minutes_p.exists() and _is_generated_data(minutes_p) and y not in generated_seasons:
            generated_seasons.append(y)

    if generated_seasons:
        seasons_str = ", ".join(str(y) for y in sorted(generated_seasons))
        return (
            f"⚠️ {seasons_str}시즌 데이터는 실제 kleague.com 크롤링 데이터가 아닌 "
            f"랜덤 생성 데이터입니다.\n"
            f"정확한 통계 제공이 불가능하므로 해당 시즌 질문에는 답변드리기 어렵습니다.\n"
            f"실제 크롤링이 완료된 후 다시 질문해 주세요."
        )
    return None


def _get_pipeline(question: str, season: int = 2025, season_to: int | None = None):
    """질문에 맞는 파이프라인 또는 직접 필터 결과를 반환합니다."""
    import sys
    sys.path.insert(0, str(AI_SERVER))

    s_from = season
    s_to = season_to if season_to is not None else season
    if s_from > s_to:
        s_from, s_to = s_to, s_from

    # 생성된 가짜 데이터 시즌 요청 차단
    generated_warning = _check_generated_seasons(s_from, s_to)
    if generated_warning:
        return "generated_data_blocked", generated_warning, []

    # 브리핑 시트 질문 처리 (가장 먼저 — 두 팀 필요)
    if _is_briefing_query(question):
        from run_ingest import _detect_teams
        if len(_detect_teams(question)) >= 2:
            context = _build_briefing_context(question, s_from, s_to if s_to != s_from else None)
            if context:
                return "briefing", context, []

    # 경기 상세 정보 질문 처리 (가장 먼저)
    if _is_detail_query(question):
        context, source_events = _build_detail_context(question, s_from, s_to)
        if context:
            return "detail", context, source_events

    # 선발 명단 / 라인업 질문 처리 — 데이터 없음 메시지도 lineup 모드로 처리 (RAG 할루시네이션 방지)
    if _is_lineup_query(question):
        context = _build_lineup_context(question, s_from)
        return "lineup", context, []

    # 시간대별 득점 분포 질문 처리
    if _is_timedist_query(question):
        context = _build_timedist_context(question, s_from, s_to if s_to != s_from else None)
        if context:
            return "timedist", context, []

    # 연속 기록(스트릭) 질문 처리
    if _is_streak_query(question):
        context = _build_streak_context(question, s_from, s_to if s_to != s_from else None)
        if context:
            return "streak", context, []

    # 선제골 승률 질문 처리
    if _is_firstgoal_query(question):
        context = _build_firstgoal_context(question, s_from, s_to if s_to != s_from else None)
        if context:
            return "firstgoal", context, []

    # 클린시트 질문 처리
    if _is_cleansheet_query(question):
        context = _build_cleansheet_context(question, s_from, s_to if s_to != s_from else None)
        if context:
            return "cleansheet", context, []

    # 관중 질문 처리
    if _is_attendance_query(question):
        context = _build_attendance_context(question, s_from, s_to if s_to != s_from else None)
        if context:
            return "attendance", context, []

    # 순위 질문 처리 (라운드 지정 가능)
    if _is_standings_query(question):
        context = _build_standings_context(question, s_from)
        if context:
            return "standings", context, []

    # 경기 이벤트 질문 처리
    if _is_event_query(question):
        context, source_events = _build_event_context(question, s_from, s_to)
        if context:
            return "event", context, source_events

    # 출전시간 질문 처리
    if _is_minutes_query(question):
        context = _build_minutes_context(question, s_from)
        if context:
            return "minutes", context, []

    # 선수 관련 질문 처리
    if _is_player_query(question):
        context, players = _build_player_context(question, s_from, s_to)
        if context:
            return "player", context, players

    from run_ingest import _detect_teams, _load_records

    teams = _detect_teams(question)
    round_num = _extract_round(question)
    records: list[dict] = []
    for y in range(s_from, s_to + 1):
        records.extend(_load_records(y))

    # k1_team_results에 해당 시즌 데이터가 없으면 match_events 파일에서 보완
    loaded_seasons = {r.get("season") for r in records}
    for y in range(s_from, s_to + 1):
        if y not in loaded_seasons:
            p = _events_path(y)
            if p.exists() and not _is_generated_data(p):
                ev_data = json.loads(p.read_text(encoding="utf-8"))
                for g in ev_data.get("events_by_game", []):
                    records.append({
                        "game_id":    g.get("game_id"),
                        "season":     y,
                        "round":      g.get("round"),
                        "date":       g.get("date", ""),
                        "home_team":  g.get("home_team", ""),
                        "away_team":  g.get("away_team", ""),
                        "home_score": g.get("home_score"),
                        "away_score": g.get("away_score"),
                    })

    if teams:
        # game_id 중복 제거
        seen, unique = set(), []
        for r in records:
            gid = r.get("game_id")
            if gid not in seen:
                seen.add(gid)
                unique.append(r)

        if len(teams) >= 2:
            t1, t2 = teams[0], teams[1]
            matched = [
                r for r in unique
                if (t1 in r.get("home_team", "") and t2 in r.get("away_team", ""))
                or (t2 in r.get("home_team", "") and t1 in r.get("away_team", ""))
            ]
        else:
            t = teams[0]
            matched = [
                r for r in unique
                if t in r.get("home_team", "") or t in r.get("away_team", "")
            ]

        # 라운드 필터
        round_note = ""
        if round_num is not None and matched:
            round_filtered = [r for r in matched if r.get("round") == round_num]
            if round_filtered:
                matched = round_filtered
            else:
                # 라운드 정보가 없는 시즌(match_events 보완 데이터)에서는 필터 불가
                # → 전체 반환하고 라운드 데이터 없음 안내
                round_note = f"[안내] {s_from}시즌 데이터에는 라운드 정보가 없어 {round_num}라운드를 특정할 수 없습니다. 아래는 해당 팀 전체 경기 결과입니다.\n\n"

        matched.sort(key=lambda r: r.get("date", ""))
        def _fmt_match(r: dict) -> str:
            att = r.get("attendance")
            att_str = f" 관중:{att:,}명" if att and att > 0 else ""
            round_str = f"{r['round']}라운드: " if r.get("round") else ""
            return (
                f"{r['date']} {round_str}"
                f"{r['home_team']}(H) {r['home_score']}-{r['away_score']} {r['away_team']}(A)"
                f"{att_str} [{r.get('venue', '')}]"
            )
        context = round_note + "\n".join(_fmt_match(r) for r in matched)
        return "direct", context, matched
    else:
        from rag.document_loader import KLeagueDocumentLoader
        from rag.pipeline import build_pipeline

        k1_path = AI_SERVER / "data" / "processed" / "teams" / "k1_team_results.json"
        docs = KLeagueDocumentLoader().load_from_file(k1_path) if k1_path.exists() else []
        pipeline = build_pipeline(documents=docs)
        return "rag", pipeline, []


@router.post("/query")
async def query_stream(req: QueryRequest):
    """SSE 스트리밍 답변."""

    async def generate():
        try:
            mode, payload, matched = await asyncio.get_event_loop().run_in_executor(
                None, _get_pipeline, req.question, req.season, req.season_to
            )

            if mode == "generated_data_blocked":
                # 가짜 데이터 차단 - 즉시 경고 메시지 반환
                yield f"data: {json.dumps({'type': 'token', 'content': payload}, ensure_ascii=False)}\n\n"
                yield "data: {\"type\": \"done\"}\n\n"
                return

            if mode == "briefing":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                briefing_system = (
                    "당신은 K리그 중계 전문 AI 해설 보조입니다.\n"
                    "아래 [경기 전 브리핑 시트 데이터]는 실제 경기 기록을 집계한 정확한 수치입니다.\n"
                    "이 데이터를 바탕으로 해설위원·캐스터가 방송 직전에 바로 활용할 수 있는 브리핑 시트를 작성해주세요.\n"
                    "데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n\n"
                    "출력 형식 (반드시 이 순서로, 마크다운 사용):\n"
                    "## ⚔️ [팀A] vs [팀B] — 경기 전 브리핑\n\n"
                    "### 📊 시즌 성적 비교\n"
                    "두 팀 성적을 표(| 팀 | 순위 | 경기 | 승 | 무 | 패 | 승점 | 득점 | 실점 | 득실 |)로 정리\n\n"
                    "### 📈 최근 폼 & 홈/원정 성적\n"
                    "각 팀 최근 5경기 폼 문자열과 경기 목록 / 홈·원정 성적을 표로 비교\n\n"
                    "### 🏆 주요 득점자\n"
                    "두 팀 주요 득점자를 나란히 표(| 팀 | 선수 | 골 | 도움 | 경기 |)로 정리\n\n"
                    "### 🎯 선제골 승률\n"
                    "두 팀 선제골 득점·허용 시 승률을 표(| 팀 | 상황 | 경기 | 승 | 무 | 패 | 승률 |)로 비교\n\n"
                    "### 🔄 맞대결 전적\n"
                    "상대 전적 요약 + 최근 맞대결 목록\n\n"
                    "### 📝 해설 포인트 (데이터 기반)\n"
                    "오늘 경기에서 주목할 3가지 포인트를 bullet로 (반드시 위 데이터에서 도출된 것만 작성)"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", briefing_system),
                    ("human", "{context}\n\n요청: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.2, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            elif mode == "timedist":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                td_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [시간대별 득점/실점 분포 데이터]는 실제 경기 이벤트를 집계한 정확한 수치입니다.\n"
                    "이 데이터를 바탕으로 질문에 답해주세요. 데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n\n"
                    "출력 형식:\n"
                    "- 시간대별 분포를 반드시 마크다운 표로 정리 (시간대 | 골 수 | 비율)\n"
                    "- 전반/후반 비율도 정리 (전반 = 1~45분 합계, 후반 = 46분 이후 합계)\n"
                    "- 표 아래 해설에 유용한 인사이트를 2~3줄 추가 (예: '후반 30분 이후 집중력이 떨어지는 팀', '전반에 강한 팀' 등)\n"
                    "- 전체 팀 비교 시에도 마크다운 표로 한눈에 비교 가능하게"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", td_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            elif mode == "streak":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                streak_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [연속 기록 데이터]는 실제 경기 기록을 집계한 정확한 수치입니다.\n"
                    "이 데이터를 바탕으로 질문에 답해주세요. 데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n\n"
                    "핵심 규칙:\n"
                    "- 사용자가 특정 연속 기록(예: 연승, 연패, 무패 등)을 물어보면 해당 기록만 집중적으로 답변하세요.\n"
                    "- 물어보지 않은 다른 종류의 연속 기록은 나열하지 마세요.\n"
                    "- 예를 들어 '최다 연승 기록'을 물어보면 연승 기록과 해당 경기 목록만 답변하세요.\n\n"
                    "출력 형식:\n"
                    "- 먼저 답변을 한 줄로 명확히 (예: 'FC 서울의 시즌 최다 연승 기록은 4경기입니다.')\n"
                    "- 그 아래 해당 연속 기록을 구성하는 경기 목록을 마크다운 표로 정리 (날짜 | 라운드 | 홈팀 | 스코어 | 원정팀 | H/A)\n"
                    "- 현재 진행 중인 기록이 있으면 '현재 N경기 진행 중'으로 별도 표시\n"
                    "- 표 아래 해설에 유용한 인사이트를 1~2줄 추가\n"
                    "- 사용자가 전체 연속 기록을 물어볼 때만 전체 요약 표(구분 | 현재 | 시즌최장)를 보여주세요."
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", streak_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            elif mode == "firstgoal":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                fg_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [선제골 데이터]는 실제 경기 이벤트를 집계한 정확한 수치입니다.\n"
                    "이 데이터를 바탕으로 질문에 답해주세요. 데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n\n"
                    "출력 형식:\n"
                    "- 선제골 득점 시 승률과 선제골 실점 시 승률을 각각 마크다운 표로 정리\n"
                    "- 표 아래 흥미로운 인사이트를 2~3줄 추가 (예: 가장 뒤집기를 잘하는 팀, 선제골 넣으면 거의 지지 않는 팀 등)"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", fg_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            elif mode == "cleansheet":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                cs_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [클린시트 데이터]는 실제 경기 기록을 집계한 정확한 수치입니다.\n"
                    "이 데이터를 바탕으로 질문에 답해주세요. 데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n\n"
                    "출력 형식:\n"
                    "- 팀별 클린시트 순위는 마크다운 표로 정리 (순위 | 팀 | 경기 | 클린시트 | 홈CS | 원정CS | CS비율)\n"
                    "- 특정 팀의 클린시트 경기 목록도 표로 정리\n"
                    "- 표 아래 간단한 분석 코멘트 1~2줄 추가"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", cs_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            elif mode == "attendance":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                att_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [관중 데이터]는 실제 경기 기록을 집계한 정확한 수치입니다.\n"
                    "이 데이터를 바탕으로 질문에 답해주세요. 데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n"
                    "순위표나 목록은 보기 좋게 정리하고, 흥미로운 포인트를 간단히 코멘트해도 좋습니다."
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", att_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            elif mode == "detail":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                detail_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [경기 상세 데이터]는 실제 경기 기록입니다.\n"
                    "이 데이터를 바탕으로 경기 상세 정보를 보기 좋게 정리해주세요.\n"
                    "데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n\n"
                    "출력 형식:\n"
                    "- 경기 개요(날짜, 라운드, 팀, 스코어, 경기장, 관중)를 먼저 정리\n"
                    "- 득점 기록은 시간순으로 마크다운 표(| 시간 | 팀 | 득점자 | 도움 |)로 정리\n"
                    "- 경고/퇴장이 있으면 별도 표로 정리\n"
                    "- 마지막에 간단한 경기 요약 1~2줄 추가"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", detail_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

                if matched:
                    sources = [
                        {
                            "date":       g["date"],
                            "home_team":  g["home_team"],
                            "away_team":  g["away_team"],
                            "home_score": g["home_score"],
                            "away_score": g["away_score"],
                            "events":     g.get("events", [])[:15],
                        }
                        for g in matched[:5]
                    ]
                    yield f"data: {json.dumps({'type': 'event_sources', 'content': sources}, ensure_ascii=False)}\n\n"

            elif mode == "standings":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                standings_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [순위표 데이터]는 실제 경기 기록을 집계한 정확한 데이터입니다.\n"
                    "이 데이터 그대로 순위를 정리해 알려주세요. 데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n"
                    "표 형식으로 보기 좋게 정리하고, 주요 포인트(1위 팀, 승점 차이 등)를 간단히 코멘트해도 좋습니다."
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", standings_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            elif mode == "event":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                event_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [경기 데이터]는 이미 조건에 맞게 필터링된 경기만 포함됩니다.\n"
                    "반드시 이 데이터에 있는 경기만 나열하세요. 데이터에 없는 경기는 절대 추가하거나 창작하지 마세요.\n"
                    "경기가 0건이면 '해당 조건을 만족하는 경기가 없습니다'라고 답하세요.\n"
                    "각 경기의 날짜, 팀, 스코어, 해당 이벤트(득점자·시간 등)를 명확히 정리하세요."
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", event_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.2, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

                if matched:
                    sources = [
                        {
                            "date":       g["date"],
                            "home_team":  g["home_team"],
                            "away_team":  g["away_team"],
                            "home_score": g["home_score"],
                            "away_score": g["away_score"],
                            "events":     g["events"][:12],
                        }
                        for g in matched[:8]
                    ]
                    yield f"data: {json.dumps({'type': 'event_sources', 'content': sources}, ensure_ascii=False)}\n\n"

            elif mode == "player":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                player_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "제공된 선수 기록 데이터를 바탕으로 질문에 정확하게 답변하세요.\n"
                    "데이터에 없는 내용은 추측하지 말고 제공된 데이터 기준임을 명시하세요.\n\n"
                    "출력 형식:\n"
                    "- 선수 순위/목록은 반드시 마크다운 표(| 구분자)로 정리하세요.\n"
                    "- 표 컬럼 예: 순위 | 선수명 | 팀 | 포지션 | 경기 | 골 | 도움\n"
                    "- 표 아래에 간단한 요약을 1~2줄 추가하세요."
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", player_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.2,
                    streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()

                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

                if matched:
                    sources = [
                        {
                            "player_name": p.get("player_name", ""),
                            "team": p.get("team", ""),
                            "position": p.get("position", ""),
                            "goals": p.get("goals", 0),
                            "assists": p.get("assists", 0),
                            "appearances": p.get("appearances", 0),
                        }
                        for p in matched[:10]
                    ]
                    yield f"data: {json.dumps({'type': 'player_sources', 'content': sources}, ensure_ascii=False)}\n\n"

            elif mode == "minutes":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                minutes_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [출전시간 데이터]는 실제 경기 기록을 집계한 정확한 수치입니다.\n"
                    "이 데이터를 바탕으로 질문에 답해주세요. 데이터에 없는 내용은 절대 추가하거나 창작하지 마세요.\n\n"
                    "출력 형식:\n"
                    "- 경기별 출전시간은 라운드 순으로 표(| 라운드 | 날짜 | 상대팀 | 출전시간 | 비고 |)로 정리\n"
                    "- 총 출전시간·평균·선발 횟수 요약을 표 아래에 추가\n"
                    "- 팀 전체 요약이면 총 출전시간 순 표(| 순위 | 선수명 | 경기 | 선발 | 총 출전 | 평균 |)로 정리"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", minutes_system),
                    ("human", "{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            elif mode == "direct":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI
                from rag.pipeline import SYSTEM_PROMPT, HUMAN_PROMPT

                prompt = ChatPromptTemplate.from_messages([
                    ("system", SYSTEM_PROMPT),
                    ("human", HUMAN_PROMPT),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini",
                    temperature=0.3,
                    streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()

                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

                # 소스 경기 전송
                if matched:
                    sources = [
                        {
                            "date": r["date"],
                            "round": r.get("round"),
                            "date": r["date"],
                            "round": r.get("round"),
                            "home_team": r["home_team"],
                            "away_team": r["away_team"],
                            "home_score": r["home_score"],
                            "away_score": r["away_score"],
                            "venue": r.get("venue", ""),
                            "attendance": r.get("attendance"),
                        }
                        for r in matched
                    ]
                    yield f"data: {json.dumps({'type': 'sources', 'content': sources}, ensure_ascii=False)}\n\n"

            elif mode == "lineup":
                from langchain_core.output_parsers import StrOutputParser
                from langchain_core.prompts import ChatPromptTemplate
                from langchain_openai import ChatOpenAI

                lineup_system = (
                    "당신은 K리그 AI 해설 보조입니다.\n"
                    "아래 [라인업 데이터]는 실제 경기 선발/벤치 명단입니다.\n\n"
                    "중요 규칙:\n"
                    "- [라인업 데이터 없음]이라고 표시된 경우, 반드시 '해당 시즌의 선발 명단 데이터가 없습니다'라고 솔직하게 답하세요.\n"
                    "- 데이터에 없는 선수명이나 정보를 절대 창작하거나 추측하지 마세요.\n"
                    "- 실제 데이터가 있을 때만 선발 명단을 제공하세요.\n\n"
                    "출력 형식 (데이터가 있는 경우):\n"
                    "- 홈팀과 원정팀 선발 11인을 포지션별로 정리 (표 형식: | 번호 | 선수명 | 포지션 |)\n"
                    "- 벤치 명단도 같은 형식으로 정리\n"
                    "- 질문이 특정 팀만 묻는 경우 해당 팀 정보만 출력"
                )
                prompt = ChatPromptTemplate.from_messages([
                    ("system", lineup_system),
                    ("human", "[라인업 데이터]\n{context}\n\n질문: {question}"),
                ])
                llm = ChatOpenAI(
                    model="gpt-4o-mini", temperature=0.1, streaming=True,
                    openai_api_key=os.environ["OPENAI_API_KEY"],
                )
                chain = prompt | llm | StrOutputParser()
                for chunk in chain.stream({"context": payload, "question": req.question}):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            else:
                # RAG 파이프라인 스트리밍
                pipeline = payload
                for chunk in pipeline.stream(req.question):
                    yield f"data: {json.dumps({'type': 'token', 'content': chunk}, ensure_ascii=False)}\n\n"

            yield "data: [DONE]\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.post("/query/sync")
async def query_sync(req: QueryRequest):
    """동기 답변 (테스트·디버그용)."""
    mode, payload, matched = await asyncio.get_event_loop().run_in_executor(
        None, _get_pipeline, req.question
    )

    if mode == "direct":
        from langchain_core.output_parsers import StrOutputParser
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
        from rag.pipeline import SYSTEM_PROMPT, HUMAN_PROMPT

        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ])
        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3,
                         openai_api_key=os.environ["OPENAI_API_KEY"])
        chain = prompt | llm | StrOutputParser()
        answer = chain.invoke({"context": payload, "question": req.question})
    else:
        answer = payload.query(req.question)

    return {"answer": answer, "sources": [
        {"date": r["date"], "home_team": r["home_team"],
         "away_team": r["away_team"], "score": f"{r['home_score']}-{r['away_score']}"}
        for r in matched
    ]}
