"""
질문 유형 분류기.

LLM 없이 정규식 패턴으로만 분류합니다.
- STRUCTURED: 정확한 데이터가 필요한 사실형 질문 → MatchDataEngine으로 라우팅
- NARRATIVE : 분석/배경/맥락 질문 → RAG 파이프라인으로 라우팅

분류 결과에 params가 포함되어 MatchDataEngine 메서드를 바로 호출할 수 있습니다.
"""

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class QueryType(Enum):
    EARLY_GOAL = "early_goal"          # 전반 X분 이전 득점
    LATE_GOAL = "late_goal"            # 후반 X분 이후/추가시간 득점
    TEAM_STATS = "team_stats"          # 팀 시즌 성적/승패
    HEAD_TO_HEAD = "head_to_head"      # 맞대결 기록
    TOP_SCORERS = "top_scorers"        # 득점 순위
    GOAL_SCORER = "goal_scorer"        # 특정 선수 득점 기록
    TEAM_RESULTS = "team_results"      # 팀 경기 목록/결과
    NARRATIVE = "narrative"            # 분석·배경·맥락 → RAG


@dataclass
class ClassifyResult:
    query_type: QueryType
    params: dict = field(default_factory=dict)
    confidence: float = 1.0


# ── 팀 동의어 맵 ───────────────────────────────────────────────────────────
# 사용자가 다양한 방식으로 팀명을 쓸 수 있으므로 정규화
TEAM_ALIASES: dict[str, str] = {
    "fc서울": "서울", "fc 서울": "서울", "서울fc": "서울",
    "전북현대": "전북", "현대": "전북",
    "울산현대": "울산",
    "포항스틸러스": "포항", "스틸러스": "포항",
    "수원삼성": "수원", "삼성": "수원",
    "수원fc": "수원FC",
    "대구fc": "대구", "대구 fc": "대구",
    "성남fc": "성남",
    "인천유나이티드": "인천",
    "광주fc": "광주",
    "제주유나이티드": "제주",
    "강원fc": "강원",
    "김천상무": "김천",
    "전남드래곤즈": "전남",
    "부산아이파크": "부산",
    "대전하나시티즌": "대전",
    "충남아산fc": "충남아산",
    "천안시티fc": "천안",
}

# ── 분 추출 패턴 ──────────────────────────────────────────────────────────
_MINUTE_RE = re.compile(r"(\d{1,3})\s*분")
_HALF_RE = re.compile(r"(전반|후반)")
_SEASON_RE = re.compile(r"(20\d{2})\s*(?:시즌|년)?")

# ── 구조적 쿼리 패턴 목록 ────────────────────────────────────────────────
_WITHIN = r"(이전|이내|이하|까지|전에|안에|만에)"
_EARLY_GOAL_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"(전반|후반)?\s*\d+\s*분\s*(이전|이내|이하|까지|전에|안에|만에).*(득점|골)",
        r"(득점|골).*(이전|이내|이하|까지|전에|안에|만에).*\d+\s*분",
        r"(득점|골).*\d+\s*분\s*(이전|이내|이하|까지|전에|안에|만에)",
        r"선제골.*\d+\s*분",
        r"\d+\s*분\s*(이전|이내|이하|까지|전에|안에|만에).*(득점|골|넣)",
        r"(득점|골|넣).*\d+\s*분\s*(이전|이내|이하|까지|전에|안에|만에)",
        r"(전반|후반)\s*\d+\s*분\s*(이전|이내|이하|전|안에|만에)",
    ]
]

_LATE_GOAL_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"(후반|추가시간|인저리타임).*\d+\s*분.*(이후|이상|부터|넘어)",
        r"막판\s*득점",
        r"추가시간\s*득점",
        r"역전골",
        r"\d+\s*분\s*(이후|이상|넘어|부터).*득점",
    ]
]

_HEAD_TO_HEAD_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"맞대결",
        r"상대\s*(전적|기록|성적)",
        r"전적",
        r"vs\s*\S+",
        r"(이긴|진|비긴)\s*경기.*(?:횟수|몇\s*번|몇\s*경기)",
    ]
]

_TEAM_STATS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"(승률|승패|성적|순위|포인트|승점)",
        r"몇\s*승\s*몇\s*패",
        r"(홈|원정)\s*(승률|성적|경기)",
        r"연승|연패|무패",
    ]
]

_TOP_SCORERS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"득점왕",
        r"최다\s*득점",
        r"골\s*(순위|랭킹|1위|2위|3위)",
        r"득점\s*(순위|랭킹|1위|2위|3위)",
        r"시즌\s*\d+\s*골",
        r"도움\s*(왕|순위|랭킹)",
    ]
]

_TEAM_RESULTS_PATTERNS = [
    re.compile(p, re.IGNORECASE) for p in [
        r"경기\s*(결과|목록|기록)\s*(알려|보여|출력)",
        r"(이긴|진|비긴)\s*경기\s*(모두|전부|목록|다)",
        r"최근\s*\d+\s*경기",
        r"(홈|원정)\s*경기\s*(결과|기록)",
        r"(이긴|승리한|패배한|무승부)\s*경기",
        r"\d+\s*라운드\s*(경기|결과|기록)",
        r"(경기|결과)\s*\d+\s*라운드",
    ]
]


class QueryClassifier:
    """
    질문 유형 분류기.

    사용 예:
        clf = QueryClassifier()
        result = clf.classify("FC서울이 전반 15분 이전에 득점한 경기")
        # result.query_type == QueryType.EARLY_GOAL
        # result.params == {"team": "서울", "max_minute": 15, "half": "전반"}
    """

    def classify(self, question: str) -> ClassifyResult:
        """질문을 분류합니다."""
        q = question.strip()

        # 1. 선제골 / 빠른 득점 패턴
        if self._matches_any(q, _EARLY_GOAL_PATTERNS):
            return ClassifyResult(
                query_type=QueryType.EARLY_GOAL,
                params=self._extract_goal_params(q),
            )

        # 2. 늦은 득점 / 추가시간 패턴
        if self._matches_any(q, _LATE_GOAL_PATTERNS):
            return ClassifyResult(
                query_type=QueryType.LATE_GOAL,
                params=self._extract_goal_params(q, late=True),
            )

        # 3. 맞대결 패턴
        if self._matches_any(q, _HEAD_TO_HEAD_PATTERNS):
            teams = self._extract_teams(q)
            if len(teams) >= 2:
                return ClassifyResult(
                    query_type=QueryType.HEAD_TO_HEAD,
                    params={
                        "team1": teams[0],
                        "team2": teams[1],
                        "season": self._extract_season(q),
                    },
                )

        # 4. 팀 통계 패턴
        if self._matches_any(q, _TEAM_STATS_PATTERNS):
            teams = self._extract_teams(q)
            return ClassifyResult(
                query_type=QueryType.TEAM_STATS,
                params={
                    "team": teams[0] if teams else None,
                    "season": self._extract_season(q),
                },
            )

        # 5. 득점 순위 패턴
        if self._matches_any(q, _TOP_SCORERS_PATTERNS):
            return ClassifyResult(
                query_type=QueryType.TOP_SCORERS,
                params={"season": self._extract_season(q), "n": 10},
            )

        # 6. 팀 경기 결과 목록
        if self._matches_any(q, _TEAM_RESULTS_PATTERNS):
            teams = self._extract_teams(q)
            return ClassifyResult(
                query_type=QueryType.TEAM_RESULTS,
                params={
                    "team": teams[0] if teams else None,
                    "season": self._extract_season(q),
                },
            )

        # 7. 기본: 서사형 → RAG
        return ClassifyResult(
            query_type=QueryType.NARRATIVE,
            params={},
            confidence=0.8,
        )

    # ── 내부 헬퍼 ─────────────────────────────────────────────────────────

    @staticmethod
    def _matches_any(text: str, patterns: list[re.Pattern]) -> bool:
        return any(p.search(text) for p in patterns)

    @staticmethod
    def _extract_season(text: str) -> Optional[int]:
        m = _SEASON_RE.search(text)
        return int(m.group(1)) if m else None

    @staticmethod
    def _extract_minute(text: str) -> Optional[int]:
        m = _MINUTE_RE.search(text)
        return int(m.group(1)) if m else None

    @staticmethod
    def _extract_half(text: str) -> str:
        m = _HALF_RE.search(text)
        return m.group(1) if m else "전반"

    def _extract_goal_params(self, text: str, late: bool = False) -> dict:
        minute = self._extract_minute(text)
        half = self._extract_half(text)
        teams = self._extract_teams(text)
        season = self._extract_season(text)

        if late:
            return {
                "team": teams[0] if teams else None,
                "min_minute": minute or 80,
                "half": half,
                "season": season,
            }
        return {
            "team": teams[0] if teams else None,
            "max_minute": minute or 15,
            "half": half,
            "season": season,
        }

    def _extract_teams(self, text: str) -> list[str]:
        """텍스트에서 팀명을 추출합니다."""
        # K리그 팀 키워드 (짧은 단어가 먼저 매칭되지 않도록 길이 내림차순)
        TEAM_KEYWORDS = sorted([
            "전북", "울산", "포항", "서울", "수원FC", "수원", "제주",
            "인천", "광주", "대구", "성남", "강원", "김천", "전남",
            "부산", "대전", "충남아산", "경남", "안산", "부천", "충북청주",
            "FC서울", "fc서울",
        ], key=len, reverse=True)

        found = []
        lower = text.lower()

        # 동의어 정규화
        for alias, canonical in TEAM_ALIASES.items():
            if alias in lower:
                if canonical not in found:
                    found.append(canonical)

        # 기본 팀명 직접 매칭
        for kw in TEAM_KEYWORDS:
            if kw in text and kw.lower() not in [f.lower() for f in found]:
                # FC서울 → 서울로 정규화
                canonical = TEAM_ALIASES.get(kw.lower(), kw)
                if canonical not in found:
                    found.append(canonical)

        return found
