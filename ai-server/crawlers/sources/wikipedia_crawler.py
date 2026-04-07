"""
위키피디아 MediaWiki API 크롤러.
차단 위험 없음. 팀 역사·더비 전적·선수 커리어 수집에 특화됩니다.
"""

from pathlib import Path
from typing import Literal

import wikitextparser as wtp
from loguru import logger

from crawlers.base.base_crawler import BaseCrawler
from crawlers.config.settings import SOURCE_CONFIGS
from crawlers.config.teams import DerbyMeta, TeamMeta


class WikipediaCrawler(BaseCrawler):
    """
    위키피디아 MediaWiki API로 구단 역사, 더비 전적, 선수 커리어 수집.

    사용 API:
    - action=parse&prop=wikitext  → 원문 위키텍스트 파싱
    - action=query&prop=revisions → 현재 문서 내용

    robots.txt: 완전 허용 (딜레이 0.5~1초)
    """

    KO_API = "https://ko.wikipedia.org/w/api.php"
    EN_API = "https://en.wikipedia.org/w/api.php"

    def __init__(self, raw_cache_dir: Path) -> None:
        super().__init__(SOURCE_CONFIGS["wikipedia"], raw_cache_dir)

    def is_available(self) -> bool:
        return self.http.health_check(self.KO_API)

    # ── BaseCrawler 추상 메서드 구현 ──────────────────

    def crawl_players(self, league: Literal["K1", "K2"]) -> list[dict]:
        """
        위키피디아는 선수 명단 수집에 최적화되어 있지 않습니다.
        팀별 '선수단' 섹션에서 기본 정보만 추출합니다.
        """
        logger.info(f"[Wikipedia] crawl_players: {league} (제한적 지원)")
        return []

    def crawl_player_stats(
        self, player_id: str, seasons: list[int]
    ) -> list[dict]:
        """위키피디아에서 개인 기록 추출은 지원하지 않습니다."""
        return []

    def crawl_team_results(self, team_name: str, season: int) -> list[dict]:
        """
        팀 위키 문서의 '역대 시즌 통계' 테이블에서 경기 결과 추출.
        상세 라운드별 결과보다 시즌 요약 통계에 적합합니다.
        """
        logger.info(f"[Wikipedia] crawl_team_results: {team_name} {season}")
        return self.crawl_season_stats_table(team_name)

    # ── Wikipedia 전용 메서드 ─────────────────────────

    def crawl_team_history(self, team: TeamMeta) -> dict:
        """
        팀 위키 문서에서 창단 연도, 홈 구장, 역대 우승 기록 수집.
        Infobox 파싱 → 정형 데이터 변환.
        """
        logger.info(f"[Wikipedia] 팀 역사 수집: {team.name_ko}")
        wikitext = self._fetch_wikitext(team.wikipedia_ko, lang="ko")
        if not wikitext:
            return {}

        parsed = wtp.parse(wikitext)
        result = {
            "team_name": team.name_ko,
            "founded": team.founded,
            "stadium": team.stadium,
            "titles": [],
            "summary": "",
        }

        # Infobox에서 우승 기록 추출
        for template in parsed.templates:
            tname = template.name.strip()
            if "정보상자" in tname or "infobox" in tname.lower():
                for arg in template.arguments:
                    pname = arg.name.strip() if arg.name else ""
                    pvalue = arg.value.strip()
                    if any(
                        k in pname
                        for k in ["우승", "리그", "컵", "title", "league"]
                    ):
                        result["titles"].append(f"{pname}: {pvalue}")

        # 도입부 텍스트 (첫 500자)
        plain = parsed.plain_text()
        result["summary"] = plain[:500].strip()

        return result

    def crawl_season_stats_table(self, team_name_ko: str) -> list[dict]:
        """
        팀 위키 문서의 '역대 시즌 통계' 테이블 파싱.
        컬럼: 시즌, 승, 무, 패, 득점, 실점, 승점, 순위
        """
        logger.info(f"[Wikipedia] 시즌 통계 테이블: {team_name_ko}")
        wiki_title = team_name_ko.replace(" ", "_")
        wikitext = self._fetch_wikitext(wiki_title, lang="ko")
        if not wikitext:
            return []

        return self._parse_season_table(wikitext)

    def crawl_derby_records(self, derby: DerbyMeta) -> dict:
        """
        더비 매치 문서 파싱.
        총 전적 요약 + 최근 경기 결과 리스트 반환.
        """
        logger.info(f"[Wikipedia] 더비 전적: {derby.name}")
        wikitext = self._fetch_wikitext(derby.wikipedia_ko, lang="ko")
        if not wikitext:
            return {
                "derby_name": derby.name,
                "team_a": derby.team_a,
                "team_b": derby.team_b,
                "total_matches": 0,
                "history": [],
                "raw_summary": "",
            }

        parsed = wtp.parse(wikitext)
        plain = parsed.plain_text()

        # 첫 1000자를 더비 요약으로 사용
        summary = plain[:1000].strip()

        # 최근 경기 결과 테이블 파싱
        history = self._parse_match_history_table(wikitext)

        return {
            "derby_name": derby.name,
            "team_a": derby.team_a,
            "team_b": derby.team_b,
            "total_matches": len(history),
            "history": history[-20:],  # 최근 20경기만
            "raw_summary": summary,
            "source": "wikipedia",
        }

    def crawl_player_career(self, player_wiki_title: str) -> dict:
        """
        선수 위키 문서에서 커리어 요약, 국가대표 기록 수집.
        외국인 선수의 발음 가이드도 함께 추출.
        """
        logger.info(f"[Wikipedia] 선수 커리어: {player_wiki_title}")
        wikitext = self._fetch_wikitext(player_wiki_title, lang="ko")
        if not wikitext:
            # 한국어 위키 없으면 영어 위키 시도
            wikitext = self._fetch_wikitext(player_wiki_title, lang="en")

        if not wikitext:
            return {}

        parsed = wtp.parse(wikitext)
        result = {
            "wiki_title": player_wiki_title,
            "name_ko": "",
            "name_en": "",
            "nationality": "",
            "birth_date": "",
            "position": "",
            "career_summary": "",
            "pronunciation_guide": "",
        }

        # Infobox에서 기본 정보 추출
        for template in parsed.templates:
            tname = template.name.strip()
            if "정보상자" in tname or "football biography" in tname.lower():
                for arg in template.arguments:
                    pname = (arg.name.strip() if arg.name else "").lower()
                    pvalue = wtp.parse(arg.value).plain_text().strip()

                    if pname in ("이름", "name"):
                        result["name_ko"] = pvalue
                    elif pname in ("영어이름", "fullname"):
                        result["name_en"] = pvalue
                    elif pname in ("국적", "nationalteam"):
                        result["nationality"] = pvalue
                    elif pname in ("생년월일", "birth_date"):
                        result["birth_date"] = pvalue
                    elif pname in ("포지션", "position"):
                        result["position"] = pvalue

        # 커리어 요약 (도입부 300자)
        plain = parsed.plain_text()
        result["career_summary"] = plain[:300].strip()

        return result

    # ── 내부 유틸리티 ─────────────────────────────────

    def _fetch_wikitext(self, title: str, lang: str = "ko") -> str | None:
        """MediaWiki API로 위키텍스트 가져오기."""
        api_url = self.KO_API if lang == "ko" else self.EN_API
        params = {
            "action": "query",
            "prop": "revisions",
            "rvprop": "content",
            "rvslots": "main",
            "titles": title,
            "format": "json",
            "formatversion": "2",
        }

        try:
            data = self._get_json_cached(api_url, params=params)
            pages = data.get("query", {}).get("pages", [])
            if not pages:
                return None

            page = pages[0]
            if "missing" in page:
                logger.warning(f"[Wikipedia] 문서 없음: {title} ({lang})")
                return None

            return (
                page.get("revisions", [{}])[0]
                .get("slots", {})
                .get("main", {})
                .get("content", "")
            )
        except Exception as e:
            logger.error(f"[Wikipedia] fetch error: {title} | {e}")
            return None

    def _parse_season_table(self, wikitext: str) -> list[dict]:
        """
        위키텍스트에서 시즌별 통계 테이블을 파싱합니다.
        """
        parsed = wtp.parse(wikitext)
        results = []

        for table in parsed.tables:
            data = table.data(span=False)
            if not data or len(data) < 2:
                continue
            headers = [cell.strip() if cell else "" for cell in data[0]]
            for row in data[1:]:
                values = [cell.strip() if cell else "" for cell in row]
                entry = dict(zip(headers, values))
                if any(entry.values()):
                    results.append(entry)

        return results

    def _parse_match_history_table(self, wikitext: str) -> list[dict]:
        """더비 매치 역사 테이블에서 경기 결과 추출."""
        results = []
        lines = wikitext.split("\n")
        in_table = False
        headers: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("{|"):
                in_table = True
                headers = []
                continue
            if stripped.startswith("|}"):
                in_table = False
                continue
            if not in_table:
                continue

            if stripped.startswith("!"):
                raw_headers = stripped.lstrip("!").split("!!")
                headers = [
                    wtp.parse(h).plain_text().strip()
                    for h in raw_headers
                ]
            elif stripped.startswith("|") and not stripped.startswith("|-"):
                raw_values = stripped.lstrip("|").split("||")
                values = [
                    wtp.parse(v).plain_text().strip()
                    for v in raw_values
                ]
                if headers and values:
                    entry = dict(
                        zip(headers, values + [""] * (len(headers) - len(values)))
                    )
                    if any(entry.values()):
                        results.append(entry)

        return results
