"""
JSON 레코드 → LangChain Document 변환.
경기 결과를 해설자가 이해하기 쉬운 자연어 텍스트로 변환합니다.
각 경기를 홈팀 관점 + 원정팀 관점으로 분리해 검색 커버리지를 높입니다.
"""

import json
from pathlib import Path
from typing import Literal

from langchain_core.documents import Document
from loguru import logger


class KLeagueDocumentLoader:
    """
    K리그 수집 데이터 → LangChain Document 목록 변환.

    경기 결과 1건 → 홈팀 관점·원정팀 관점 2개 Document 생성.
    "전북이 이긴 경기"와 "전북이 진 경기" 두 쿼리 모두 검색 가능.
    """

    def load_from_file(self, path: Path) -> list[Document]:
        """JSON 파일에서 Document 목록을 읽습니다."""
        logger.info(f"로드: {path.name}")
        records = json.loads(path.read_text(encoding="utf-8"))
        return self.load(records)

    def load(self, records: list[dict]) -> list[Document]:
        """레코드 목록 → Document 목록 변환."""
        docs: list[Document] = []
        for rec in records:
            docs.extend(self._record_to_docs(rec))
        logger.info(f"  {len(records)}개 레코드 → {len(docs)}개 Document 생성")
        return docs

    # ── 내부 메서드 ──────────────────────────────────

    def _record_to_docs(self, rec: dict) -> list[Document]:
        """경기 1건 → 홈 관점 + 원정 관점 Document 2개."""
        home = rec.get("home_team", "")
        away = rec.get("away_team", "")
        hs = rec.get("home_score", 0)
        as_ = rec.get("away_score", 0)
        date = rec.get("date", "")
        venue = rec.get("venue", "")
        competition = rec.get("competition", "K리그")
        round_no = rec.get("round", 0)
        season = rec.get("season", 0)
        attendance = rec.get("attendance")

        # 날짜 포맷 "2025.02.16" → "2025년 2월 16일"
        date_str = self._format_date(date)

        # 관중 문구
        att_str = f" 관중 {attendance:,}명이 입장했다." if attendance else "."

        # 홈팀 관점
        home_result = self._result_word(hs, as_, perspective="home")
        home_text = (
            f"{competition} {round_no}라운드 경기. "
            f"{home}이(가) {venue}에서 {away}을(를) 상대로 홈 경기를 치러 "
            f"{hs}대{as_}로 {home_result}. "
            f"경기 날짜는 {date_str}이다{att_str}"
        )

        # 원정팀 관점
        away_result = self._result_word(as_, hs, perspective="away")
        away_text = (
            f"{competition} {round_no}라운드 경기. "
            f"{away}이(가) {venue}에서 {home}을(를) 상대로 원정 경기를 치러 "
            f"{as_}대{hs}로 {away_result}. "
            f"경기 날짜는 {date_str}이다."
        )

        base_meta = {
            "game_id":      rec.get("game_id"),
            "season":       season,
            "round":        round_no,
            "date":         date,
            "competition":  competition,
            "home_team":    home,
            "home_team_id": rec.get("home_team_id", ""),
            "away_team":    away,
            "away_team_id": rec.get("away_team_id", ""),
            "home_score":   hs,
            "away_score":   as_,
            "venue":        venue,
            "attendance":   attendance,
            "doc_type":     "match_result",
            "source":       rec.get("source", "kleague"),
        }

        return [
            Document(
                page_content=home_text,
                metadata={**base_meta, "perspective": "home", "team": home},
            ),
            Document(
                page_content=away_text,
                metadata={**base_meta, "perspective": "away", "team": away},
            ),
        ]

    def _result_word(
        self,
        score_a: int,
        score_b: int,
        perspective: Literal["home", "away"],
    ) -> str:
        if score_a > score_b:
            return "승리했다"
        elif score_a < score_b:
            return "패배했다"
        else:
            return "무승부로 끝났다"

    def _format_date(self, date_str: str) -> str:
        """'2025.02.16' → '2025년 2월 16일'."""
        try:
            parts = date_str.split(".")
            y, m, d = int(parts[0]), int(parts[1]), int(parts[2])
            return f"{y}년 {m}월 {d}일"
        except Exception:
            return date_str
