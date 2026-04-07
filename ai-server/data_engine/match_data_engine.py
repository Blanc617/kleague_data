"""
K리그 경기 데이터 직접 조회 엔진.

JSON 파일만 읽어 정확한 데이터를 반환합니다.
LLM이 개입하지 않으므로 절대 할루시네이션이 발생하지 않습니다.

지원 쿼리:
- get_games_with_early_goal(team, max_minute)  : 특정 분 이전에 득점한 경기
- get_team_results(team, season)               : 팀 전체 경기 결과
- get_head_to_head(team1, team2, season)       : 맞대결 기록
- get_top_scorers(season, n)                   : 시즌 득점 순위
- get_game_events(game_id)                     : 특정 경기 이벤트
- get_team_goals_by_player(team, season)       : 팀 득점자 목록
"""

import json
import glob
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from loguru import logger


DATA_ROOT = Path(__file__).parent.parent / "data" / "processed"


@dataclass
class GameResult:
    game_id: int
    season: int
    round: int
    date: str
    home_team: str
    away_team: str
    home_score: int
    away_score: int
    venue: str = ""
    competition: str = "K리그1"

    def result_for(self, team: str) -> str:
        is_home = team in self.home_team
        gf = self.home_score if is_home else self.away_score
        ga = self.away_score if is_home else self.home_score
        if gf > ga:
            return "승"
        elif gf < ga:
            return "패"
        return "무"

    def score_for(self, team: str) -> tuple[int, int]:
        """Returns (goals_for, goals_against)."""
        is_home = team in self.home_team
        if is_home:
            return self.home_score, self.away_score
        return self.away_score, self.home_score

    def opponent(self, team: str) -> str:
        return self.away_team if team in self.home_team else self.home_team


@dataclass
class GoalEvent:
    minute: int
    player: str
    team: str
    assist: str = ""
    game_id: int = 0
    date: str = ""
    home_team: str = ""
    away_team: str = ""
    home_score: int = 0
    away_score: int = 0


@dataclass
class PlayerStat:
    season: int
    team: str
    player_name: str
    appearances: int
    goals: int
    assists: int
    yellow_cards: int
    red_cards: int


class MatchDataEngine:
    """
    K리그 경기 데이터 엔진.

    초기화 시 모든 JSON 파일을 메모리에 로드합니다.
    이후 모든 쿼리는 메모리 데이터만 사용하므로 항상 정확합니다.
    """

    def __init__(self, data_root: Optional[Path] = None) -> None:
        self._root = data_root or DATA_ROOT
        self._results: list[GameResult] = []
        self._events: dict[int, list[GoalEvent]] = {}   # game_id → goals
        self._all_events_by_year: dict[int, list[dict]] = {}
        self._player_stats: list[PlayerStat] = []
        self._loaded = False

    def load(self) -> "MatchDataEngine":
        """모든 데이터 파일을 로드합니다. 체인 가능."""
        if self._loaded:
            return self
        self._load_results()
        self._load_match_events()
        self._load_player_stats()
        self._loaded = True
        logger.info(
            f"MatchDataEngine 로드 완료: "
            f"경기결과 {len(self._results)}건, "
            f"이벤트 {sum(len(v) for v in self._events.values())}개 골, "
            f"선수통계 {len(self._player_stats)}명"
        )
        return self

    # ── 공개 쿼리 메서드 ──────────────────────────────────────────────────

    def get_games_with_early_goal(
        self,
        team: str,
        max_minute: int,
        half: str = "전반",   # "전반" | "후반" | "전체"
        season: Optional[int] = None,
    ) -> list[dict]:
        """
        특정 팀이 지정 분 이내에 득점한 경기 목록 반환.

        GoalEvent에 포함된 경기 정보(date, home_team, away_team, scores)를
        직접 사용하므로 game_id 충돌 문제가 없습니다.

        Returns:
            [{"game": GameResult, "goals": [GoalEvent, ...]}, ...]
        """
        self._ensure_loaded()
        result = []

        for composite_key, goals in self._events.items():
            # 해당 팀 골만 필터 + 분 범위 체크
            team_goals = [
                g for g in goals
                if team in g.team and self._in_minute_range(g.minute, max_minute, half)
            ]
            if not team_goals:
                continue

            # 대표 GoalEvent로 경기 정보 구성 (모든 이벤트의 경기 정보가 동일)
            ref = team_goals[0]
            if team not in ref.home_team and team not in ref.away_team:
                continue

            game_season = int(ref.date[:4]) if ref.date and len(ref.date) >= 4 else 0
            if season and game_season != season:
                continue

            game = GameResult(
                game_id=ref.game_id,
                season=game_season,
                round=0,
                date=ref.date,
                home_team=ref.home_team,
                away_team=ref.away_team,
                home_score=ref.home_score,
                away_score=ref.away_score,
            )
            result.append({"game": game, "goals": team_goals})

        result.sort(key=lambda x: x["game"].date)
        return result

    def get_team_results(
        self,
        team: str,
        season: Optional[int] = None,
    ) -> list[GameResult]:
        """팀의 전체 경기 결과 반환."""
        self._ensure_loaded()
        results = [
            r for r in self._results
            if team in r.home_team or team in r.away_team
        ]
        if season:
            results = [r for r in results if r.season == season]
        results.sort(key=lambda r: r.date)
        return results

    def get_head_to_head(
        self,
        team1: str,
        team2: str,
        season: Optional[int] = None,
    ) -> list[GameResult]:
        """두 팀 맞대결 기록 반환."""
        self._ensure_loaded()
        results = [
            r for r in self._results
            if (team1 in r.home_team and team2 in r.away_team)
            or (team2 in r.home_team and team1 in r.away_team)
        ]
        if season:
            results = [r for r in results if r.season == season]
        results.sort(key=lambda r: r.date)
        return results

    def get_top_scorers(
        self,
        season: Optional[int] = None,
        n: int = 10,
    ) -> list[PlayerStat]:
        """시즌 득점 순위 반환."""
        self._ensure_loaded()
        stats = self._player_stats
        if season:
            stats = [s for s in stats if s.season == season]
        return sorted(stats, key=lambda s: s.goals, reverse=True)[:n]

    def get_game_events(self, game_id: int, season: Optional[int] = None) -> list[GoalEvent]:
        """특정 경기의 골 이벤트 반환. season을 함께 전달하면 정확하게 조회."""
        self._ensure_loaded()
        if season:
            return self._events.get(f"{season}_{game_id}", [])
        # season 미지정 시 모든 연도에서 해당 game_id 통합 반환
        result = []
        for key, goals in self._events.items():
            if key.endswith(f"_{game_id}"):
                result.extend(goals)
        return result

    def get_team_goals_by_player(
        self,
        team: str,
        season: Optional[int] = None,
    ) -> list[PlayerStat]:
        """팀 득점자 목록 반환."""
        self._ensure_loaded()
        stats = [s for s in self._player_stats if team in s.team]
        if season:
            stats = [s for s in stats if s.season == season]
        return sorted(stats, key=lambda s: s.goals, reverse=True)

    def get_available_seasons(self) -> list[int]:
        """데이터가 있는 시즌 목록 반환."""
        self._ensure_loaded()
        return sorted({r.season for r in self._results if r.season})

    def get_all_teams(self) -> list[str]:
        """데이터에 있는 모든 팀 목록 반환."""
        self._ensure_loaded()
        teams: set[str] = set()
        for r in self._results:
            teams.add(r.home_team)
            teams.add(r.away_team)
        return sorted(teams)

    # ── 데이터 로딩 ────────────────────────────────────────────────────────

    def _load_results(self) -> None:
        """k1_team_results.json 로드."""
        path = self._root / "teams" / "k1_team_results.json"
        if not path.exists():
            logger.warning(f"k1_team_results.json 없음: {path}")
            return

        raw: list[dict] = json.loads(path.read_text(encoding="utf-8"))

        seen: set[int] = set()
        for rec in raw:
            gid = rec.get("game_id", 0)
            if gid in seen:
                continue
            seen.add(gid)
            self._results.append(GameResult(
                game_id=gid,
                season=rec.get("season", 0),
                round=rec.get("round", 0),
                date=rec.get("date", ""),
                home_team=rec.get("home_team", ""),
                away_team=rec.get("away_team", ""),
                home_score=rec.get("home_score", 0),
                away_score=rec.get("away_score", 0),
                venue=rec.get("venue", ""),
                competition=rec.get("competition", "K리그1"),
            ))

    def _load_match_events(self) -> None:
        """
        match_events_*.json 파일들 로드.

        주의: 각 연도 파일의 game_id는 해당 연도 내에서만 고유합니다.
        여러 연도에 걸쳐 동일한 game_id가 존재하므로 (year, game_id) 복합키 사용.
        내부적으로는 고유 키 `{year}_{game_id}` 문자열로 저장합니다.
        """
        pattern = str(self._root / "matches" / "match_events_*.json")
        files = sorted(glob.glob(pattern))
        if not files:
            logger.warning("match_events_*.json 파일 없음")
            return

        for filepath in files:
            data = json.loads(Path(filepath).read_text(encoding="utf-8"))
            year = data.get("season", 0)
            games = data.get("events_by_game", [])
            for game in games:
                game_id = game.get("game_id", 0)
                raw_events = game.get("events", [])
                goals = []
                for ev in raw_events:
                    if ev.get("type") != "goal":
                        continue
                    goals.append(GoalEvent(
                        minute=ev.get("minute", 0),
                        player=ev.get("player", ""),
                        team=ev.get("team", ""),
                        assist=ev.get("assist", ""),
                        game_id=game_id,
                        date=game.get("date", ""),
                        home_team=game.get("home_team", ""),
                        away_team=game.get("away_team", ""),
                        home_score=game.get("home_score", 0),
                        away_score=game.get("away_score", 0),
                    ))
                composite_key = f"{year}_{game_id}"
                self._events[composite_key] = goals

    def _load_player_stats(self) -> None:
        """player_stats_*.json 파일들 로드."""
        pattern = str(self._root / "players" / "player_stats_*.json")
        files = sorted(glob.glob(pattern))
        for filepath in files:
            data = json.loads(Path(filepath).read_text(encoding="utf-8"))
            season = data.get("season", 0)
            for p in data.get("players", []):
                self._player_stats.append(PlayerStat(
                    season=season,
                    team=p.get("team", ""),
                    player_name=p.get("player_name", ""),
                    appearances=p.get("appearances", 0),
                    goals=p.get("goals", 0),
                    assists=p.get("assists", 0),
                    yellow_cards=p.get("yellow_cards", 0),
                    red_cards=p.get("red_cards", 0),
                ))

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    def _find_game(self, game_id: int) -> Optional[GameResult]:
        """game_id로 GameResult 조회."""
        for r in self._results:
            if r.game_id == game_id:
                return r
        # match_events에만 있고 k1_team_results에 없는 경우 이벤트 데이터로 생성
        goals = self._events.get(game_id, [])
        if goals:
            first = goals[0]
            return GameResult(
                game_id=game_id,
                season=int(first.date[:4]) if first.date else 0,
                round=0,
                date=first.date,
                home_team=first.home_team,
                away_team=first.away_team,
                home_score=first.home_score,
                away_score=first.away_score,
            )
        return None

    @staticmethod
    def _in_minute_range(minute: int, max_minute: int, half: str) -> bool:
        if half == "전반":
            return 1 <= minute <= min(max_minute, 45)
        elif half == "후반":
            return 46 <= minute <= (45 + max_minute)
        else:  # 전체
            return minute <= max_minute
