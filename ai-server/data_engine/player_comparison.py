"""
선수 시즌 통계 비교 엔진.

데이터 소스:
- player_stats_{year}.json   : 출장·골·도움·카드 (K리그 공식)
- player_minutes_{year}.json : 출장 시간 (경기별 세부)
- players_sofascore/all_players_{year}.json : xG·xA·평점·슈팅 등 (Sofascore)

할루시네이션 없음 — JSON 직접 조회만 사용합니다.
"""

import json
import glob
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Optional

from loguru import logger

DATA_ROOT = Path(__file__).parent.parent / "data" / "processed"

K_LEAGUE_1_LEAGUE_ID = 410


# ── 데이터클래스 ──────────────────────────────────────────────────────────────

@dataclass
class BasicStat:
    season: int
    team: str
    player_name: str
    appearances: int
    goals: int
    assists: int
    own_goals: int
    yellow_cards: int
    red_cards: int
    total_minutes: int = 0          # player_minutes에서 보강
    starter_count: int = 0


@dataclass
class RichStat:
    """Sofascore 기반 고급 통계 (K리그1 필터링된 단일 시즌)."""
    appearances: int
    minutes_played: int
    goals: int
    assists: int
    rating: float
    total_shots: int
    shots_on_target: int
    xg: float
    xa: float
    key_passes: int
    accurate_passes: int
    total_passes: int
    successful_dribbles: int
    tackles: int
    interceptions: int
    yellow_cards: int
    red_cards: int


@dataclass
class PlayerProfile:
    name: str
    matched_name: str           # 실제 파일에서 찾은 이름
    similarity: float           # 이름 매칭 유사도
    basic: Optional[BasicStat] = None
    rich: Optional[RichStat] = None

    def found(self) -> bool:
        return self.basic is not None or self.rich is not None


# ── 메인 엔진 ─────────────────────────────────────────────────────────────────

class PlayerComparisonEngine:
    """
    두 선수의 K리그 시즌 통계를 비교합니다.

    사용 예:
        engine = PlayerComparisonEngine()
        result = engine.compare("손준호", "세징야", 2024)
        print(result["summary"])
    """

    def __init__(self, data_root: Optional[Path] = None) -> None:
        self._root = data_root or DATA_ROOT
        self._basic_stats: dict[int, list[dict]] = {}   # season → players
        self._minutes: dict[int, list[dict]] = {}        # season → players
        self._sofascore: list[dict] = []                 # all players
        self._loaded = False

    def load(self) -> "PlayerComparisonEngine":
        if self._loaded:
            return self
        self._load_basic_stats()
        self._load_minutes()
        self._load_sofascore()
        self._loaded = True
        seasons = sorted(self._basic_stats.keys())
        logger.info(
            f"PlayerComparisonEngine 로드: "
            f"기본통계 {sum(len(v) for v in self._basic_stats.values())}명 "
            f"({seasons[0] if seasons else '?'}~{seasons[-1] if seasons else '?'}), "
            f"Sofascore {len(self._sofascore)}명"
        )
        return self

    # ── 공개 메서드 ───────────────────────────────────────────────────────────

    def compare(
        self,
        name1: str,
        name2: str,
        season: Optional[int] = None,
    ) -> dict:
        """
        두 선수의 시즌 통계를 비교합니다.

        Args:
            name1: 첫 번째 선수 이름 (부분 이름 허용)
            name2: 두 번째 선수 이름 (부분 이름 허용)
            season: 시즌 연도. None이면 가장 최근 데이터 시즌.

        Returns:
            {
                "season": int,
                "player1": PlayerProfile,
                "player2": PlayerProfile,
                "summary": str,         # 해설용 텍스트
                "table": str,           # 마크다운 표
            }
        """
        self._ensure_loaded()

        if season is None:
            season = max(self._basic_stats.keys()) if self._basic_stats else 2025
            logger.info(f"season 미지정 → {season} 사용")

        p1 = self._build_profile(name1, season)
        p2 = self._build_profile(name2, season)

        summary = self._format_summary(p1, p2, season)
        table = self._format_table(p1, p2, season)

        return {
            "season": season,
            "player1": p1,
            "player2": p2,
            "summary": summary,
            "table": table,
        }

    def get_available_seasons(self) -> list[int]:
        self._ensure_loaded()
        return sorted(self._basic_stats.keys())

    def search_player(self, name: str, season: Optional[int] = None) -> list[str]:
        """이름 검색 — 유사 선수 목록 반환."""
        self._ensure_loaded()
        seasons = [season] if season else list(self._basic_stats.keys())
        candidates: set[str] = set()
        for s in seasons:
            for p in self._basic_stats.get(s, []):
                candidates.add(p["player_name"])
        return sorted(candidates, key=lambda n: -_similarity(name, n))[:10]

    # ── 데이터 로딩 ───────────────────────────────────────────────────────────

    def _load_basic_stats(self) -> None:
        pattern = str(self._root / "players" / "player_stats_*.json")
        for filepath in sorted(glob.glob(pattern)):
            data = json.loads(Path(filepath).read_text(encoding="utf-8"))
            season = data.get("season", 0)
            self._basic_stats[season] = data.get("players", [])

    def _load_minutes(self) -> None:
        pattern = str(self._root / "players" / "player_minutes_*.json")
        for filepath in sorted(glob.glob(pattern)):
            data = json.loads(Path(filepath).read_text(encoding="utf-8"))
            season = data.get("season", 0)
            self._minutes[season] = data.get("players", [])

    def _load_sofascore(self) -> None:
        """
        players_sofascore/all_players_*.json 파일을 모두 로드해 선수 ID 기준으로 병합.

        같은 선수가 여러 파일에 있을 경우, season_stats를 합산하고 중복(league+season)은 제거.
        """
        pattern = str(self._root / "players_sofascore" / "all_players_*.json")
        files = sorted(glob.glob(pattern))
        if not files:
            logger.warning("Sofascore 데이터 없음")
            return

        # 선수 ID → dict 로 병합
        merged: dict[int, dict] = {}
        for filepath in files:
            try:
                players = json.loads(Path(filepath).read_text(encoding="utf-8"))
            except Exception as e:
                logger.warning(f"Sofascore 파일 로드 실패 ({filepath}): {e}")
                continue

            for p in players:
                pid = p.get("id")
                if pid is None:
                    continue
                if pid not in merged:
                    merged[pid] = {
                        "id": pid,
                        "name": p.get("name", ""),
                        "position": p.get("position", ""),
                        "current_team": p.get("current_team", ""),
                        "season_stats": [],
                    }
                # season_stats 병합 — (league_id, season) 기준 중복 제거
                existing_keys = {
                    (s.get("league_id"), s.get("season"))
                    for s in merged[pid]["season_stats"]
                }
                for stat in p.get("season_stats", []):
                    key = (stat.get("league_id"), stat.get("season"))
                    if key not in existing_keys:
                        merged[pid]["season_stats"].append(stat)
                        existing_keys.add(key)

        self._sofascore = list(merged.values())
        logger.info(f"Sofascore 병합 완료: {len(files)}개 파일 → {len(self._sofascore)}명")

    # ── 프로필 구성 ───────────────────────────────────────────────────────────

    def _build_profile(self, name: str, season: int) -> PlayerProfile:
        basic = self._find_basic(name, season)
        rich = self._find_rich(name, season)

        matched_name = (
            basic["player_name"] if basic
            else (rich[0] if rich else name)
        )
        sim = _similarity(name, matched_name)

        profile = PlayerProfile(name=name, matched_name=matched_name, similarity=sim)

        if basic:
            # minutes 보강
            total_minutes, starter_count = self._get_minutes(matched_name, season)
            profile.basic = BasicStat(
                season=season,
                team=basic.get("team", ""),
                player_name=matched_name,
                appearances=basic.get("appearances", 0),
                goals=basic.get("goals", 0),
                assists=basic.get("assists", 0),
                own_goals=basic.get("own_goals", 0),
                yellow_cards=basic.get("yellow_cards", 0),
                red_cards=basic.get("red_cards", 0),
                total_minutes=total_minutes,
                starter_count=starter_count,
            )

        if rich:
            _, rich_stat = rich
            profile.rich = rich_stat

        if not profile.found():
            logger.warning(f"'{name}' — {season}시즌 데이터 없음")

        return profile

    def _find_basic(self, name: str, season: int) -> Optional[dict]:
        players = self._basic_stats.get(season, [])
        return _best_match(name, players, key="player_name")

    def _find_rich(self, name: str, season: int) -> Optional[tuple[str, RichStat]]:
        """Sofascore에서 K리그1 해당 시즌 통계 검색."""
        best_player = None
        best_sim = 0.0

        for player in self._sofascore:
            pname = player.get("name", "")
            sim = _similarity(name, pname)
            if sim > best_sim and sim >= 0.5:
                best_sim = sim
                best_player = player

        if best_player is None:
            return None

        season_str = str(season)
        for stat in best_player.get("season_stats", []):
            if (
                stat.get("league_id") == K_LEAGUE_1_LEAGUE_ID
                and stat.get("season") == season_str
            ):
                return best_player["name"], RichStat(
                    appearances=stat.get("appearances", 0),
                    minutes_played=stat.get("minutes_played", 0),
                    goals=stat.get("goals", 0),
                    assists=stat.get("assists", 0),
                    rating=stat.get("rating", 0.0),
                    total_shots=stat.get("total_shots", 0),
                    shots_on_target=stat.get("shots_on_target", 0),
                    xg=stat.get("xg", 0.0),
                    xa=stat.get("xa", 0.0),
                    key_passes=stat.get("key_passes", 0),
                    accurate_passes=stat.get("accurate_passes", 0),
                    total_passes=stat.get("total_passes", 0),
                    successful_dribbles=stat.get("successful_dribbles", 0),
                    tackles=stat.get("tackles", 0),
                    interceptions=stat.get("interceptions", 0),
                    yellow_cards=stat.get("yellow_cards", 0),
                    red_cards=stat.get("red_cards", 0),
                )
        return None

    def _get_minutes(self, name: str, season: int) -> tuple[int, int]:
        players = self._minutes.get(season, [])
        match = _best_match(name, players, key="player_name")
        if match:
            return match.get("total_minutes", 0), match.get("starter_count", 0)
        return 0, 0

    # ── 포맷터 ────────────────────────────────────────────────────────────────

    def _format_table(self, p1: PlayerProfile, p2: PlayerProfile, season: int) -> str:
        rows = []

        def row(label: str, v1, v2, higher_is_better: bool = True):
            if v1 == "-" and v2 == "-":
                return
            try:
                n1, n2 = float(str(v1).replace("-", "0")), float(str(v2).replace("-", "0"))
                if higher_is_better:
                    mark1 = " ▲" if n1 > n2 else (" ▼" if n1 < n2 else "")
                    mark2 = " ▲" if n2 > n1 else (" ▼" if n2 < n1 else "")
                else:
                    mark1 = " ▲" if n1 < n2 else (" ▼" if n1 > n2 else "")
                    mark2 = " ▲" if n2 < n1 else (" ▼" if n2 > n1 else "")
            except (ValueError, TypeError):
                mark1 = mark2 = ""
            rows.append(f"| {label} | {v1}{mark1} | {v2}{mark2} |")

        name1 = p1.matched_name if p1.found() else p1.name
        name2 = p2.matched_name if p2.found() else p2.name

        header = (
            f"| 항목 | {name1} ({_team(p1)}) | {name2} ({_team(p2)}) |\n"
            f"|------|------|------|\n"
        )

        # ── 기본 통계 ──
        b1, b2 = p1.basic, p2.basic
        row("출장수", b1.appearances if b1 else "-", b2.appearances if b2 else "-")
        row("출전시간(분)", b1.total_minutes if b1 else "-", b2.total_minutes if b2 else "-")
        row("선발 출장", b1.starter_count if b1 else "-", b2.starter_count if b2 else "-")
        row("골", b1.goals if b1 else "-", b2.goals if b2 else "-")
        row("도움", b1.assists if b1 else "-", b2.assists if b2 else "-")
        g_and_a_1 = (b1.goals + b1.assists) if b1 else "-"
        g_and_a_2 = (b2.goals + b2.assists) if b2 else "-"
        row("공격포인트(G+A)", g_and_a_1, g_and_a_2)
        row("경고", b1.yellow_cards if b1 else "-", b2.yellow_cards if b2 else "-", higher_is_better=False)
        row("퇴장", b1.red_cards if b1 else "-", b2.red_cards if b2 else "-", higher_is_better=False)

        # ── Sofascore 고급 통계 ──
        r1, r2 = p1.rich, p2.rich
        if r1 or r2:
            rows.append("|  |  |  |")
            rows.append("| **[Sofascore]** | | |")
            row("평점", f"{r1.rating:.2f}" if r1 else "-", f"{r2.rating:.2f}" if r2 else "-")
            row("슈팅", r1.total_shots if r1 else "-", r2.total_shots if r2 else "-")
            row("유효슈팅", r1.shots_on_target if r1 else "-", r2.shots_on_target if r2 else "-")
            row("xG", f"{r1.xg:.2f}" if (r1 and r1.xg) else "-", f"{r2.xg:.2f}" if (r2 and r2.xg) else "-")
            row("xA", f"{r1.xa:.2f}" if (r1 and r1.xa) else "-", f"{r2.xa:.2f}" if (r2 and r2.xa) else "-")
            row("키패스", r1.key_passes if r1 else "-", r2.key_passes if r2 else "-")
            row("드리블 성공", r1.successful_dribbles if r1 else "-", r2.successful_dribbles if r2 else "-")
            row("태클", r1.tackles if r1 else "-", r2.tackles if r2 else "-")
            row("인터셉트", r1.interceptions if r1 else "-", r2.interceptions if r2 else "-")
            pass_acc_1 = f"{r1.accurate_passes}/{r1.total_passes}" if r1 else "-"
            pass_acc_2 = f"{r2.accurate_passes}/{r2.total_passes}" if r2 else "-"
            rows.append(f"| 패스 성공/시도 | {pass_acc_1} | {pass_acc_2} |")

        return header + "\n".join(rows)

    def _format_summary(self, p1: PlayerProfile, p2: PlayerProfile, season: int) -> str:
        lines = [f"## {season}시즌 선수 비교: {p1.matched_name} vs {p2.matched_name}\n"]

        if not p1.found():
            lines.append(f"- **{p1.name}**: {season}시즌 데이터 없음")
        if not p2.found():
            lines.append(f"- **{p2.name}**: {season}시즌 데이터 없음")
        if not p1.found() or not p2.found():
            return "\n".join(lines)

        b1, b2 = p1.basic, p2.basic
        r1, r2 = p1.rich, p2.rich

        # 공격 포인트 비교
        if b1 and b2:
            ga1 = b1.goals + b1.assists
            ga2 = b2.goals + b2.assists
            leader = p1.matched_name if ga1 > ga2 else (p2.matched_name if ga2 > ga1 else None)
            if leader:
                lines.append(f"- 공격포인트: **{leader}** 우세 ({ga1} vs {ga2})")
            else:
                lines.append(f"- 공격포인트 동률: 각 {ga1}포인트")

            # 출전 시간 대비 효율
            if b1.total_minutes and b2.total_minutes:
                eff1 = round(b1.total_minutes / max(b1.goals + b1.assists, 1))
                eff2 = round(b2.total_minutes / max(b2.goals + b2.assists, 1))
                better = p1.matched_name if eff1 < eff2 else (p2.matched_name if eff2 < eff1 else None)
                if better:
                    lines.append(
                        f"- 공격 효율(분/공격포인트): **{better}** 우세 ({eff1}분 vs {eff2}분)"
                    )

        # 평점 비교
        if r1 and r2 and r1.rating and r2.rating:
            better = p1.matched_name if r1.rating > r2.rating else p2.matched_name
            lines.append(f"- Sofascore 평점: **{better}** 우세 ({r1.rating:.2f} vs {r2.rating:.2f})")

        # 카드 경고
        if b1 and b2:
            if b1.red_cards or b2.red_cards:
                lines.append(f"- 퇴장: {p1.matched_name} {b1.red_cards}회 / {p2.matched_name} {b2.red_cards}회")

        return "\n".join(lines)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()


# ── 유틸 함수 ─────────────────────────────────────────────────────────────────

def _similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def _best_match(name: str, players: list[dict], key: str = "player_name") -> Optional[dict]:
    best, best_sim = None, 0.0
    for p in players:
        sim = _similarity(name, p.get(key, ""))
        if sim > best_sim:
            best_sim = sim
            best = p
    # 0.55 미만은 너무 다름 → None 반환 (한국어 3글자 이름 기준 적정값)
    return best if best_sim >= 0.55 else None


def _team(profile: PlayerProfile) -> str:
    if profile.basic:
        return profile.basic.team
    return "?"
