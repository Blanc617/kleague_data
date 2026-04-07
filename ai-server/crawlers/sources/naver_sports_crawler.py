"""
네이버 스포츠 크롤러.
선수 인터뷰, 경기 프리뷰·리뷰 기사 수집에 특화됩니다.
네이버 검색 API 우선 → 없으면 직접 크롤링으로 폴백.
"""

import os
from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup
from loguru import logger

from crawlers.base.base_crawler import BaseCrawler
from crawlers.config.settings import SOURCE_CONFIGS


class NaverSportsCrawler(BaseCrawler):
    """
    네이버 검색 API (무료 일 25,000건) 우선 사용.
    API 키 없거나 한도 초과 시 직접 HTML 크롤링으로 폴백.
    """

    NAVER_NEWS_API = "https://openapi.naver.com/v1/search/news.json"
    SPORTS_BASE = "https://sports.naver.com/football"

    def __init__(self, raw_cache_dir: Path) -> None:
        super().__init__(SOURCE_CONFIGS["naver"], raw_cache_dir)
        self._client_id = os.getenv("NAVER_CLIENT_ID", "")
        self._client_secret = os.getenv("NAVER_CLIENT_SECRET", "")
        self._api_available = bool(self._client_id and self._client_secret)

        if not self._api_available:
            logger.warning(
                "[Naver] API 키 없음 → 직접 크롤링 모드 (속도 느림)"
            )

    def is_available(self) -> bool:
        return self.http.health_check(self.SPORTS_BASE)

    # ── BaseCrawler 추상 메서드 구현 ──────────────────

    def crawl_players(self, league: Literal["K1", "K2"]) -> list[dict]:
        """네이버는 선수 명단 수집에 사용하지 않습니다."""
        return []

    def crawl_player_stats(
        self, player_id: str, seasons: list[int]
    ) -> list[dict]:
        """네이버는 통계 수집에 사용하지 않습니다."""
        return []

    def crawl_team_results(self, team_name: str, season: int) -> list[dict]:
        """네이버는 경기 결과 수집에 사용하지 않습니다."""
        return []

    # ── Naver 전용 메서드 ─────────────────────────────

    def crawl_player_interviews(
        self,
        player_name: str,
        max_articles: int = 10,
    ) -> list[dict]:
        """
        선수 이름으로 인터뷰 기사 검색.
        쿼리: "{player_name} 인터뷰 K리그"
        """
        query = f"{player_name} 인터뷰 K리그"
        logger.info(f"[Naver] 인터뷰 검색: {query}")

        raw_articles = self._search_news(query, display=max_articles)
        return self._enrich_articles(raw_articles, player_name=player_name)

    def crawl_match_preview(
        self,
        home_team: str,
        away_team: str,
        match_date: str,
    ) -> dict | None:
        """
        경기 프리뷰 기사 검색.
        쿼리: "{home_team} vs {away_team} {match_date}"
        """
        query = f"{home_team} vs {away_team} {match_date}"
        logger.info(f"[Naver] 경기 프리뷰 검색: {query}")

        articles = self._search_news(query, display=3)
        if not articles:
            return None

        enriched = self._enrich_articles(articles[:1])
        return enriched[0] if enriched else None

    def crawl_team_news(
        self,
        team_name: str,
        days_back: int = 30,
    ) -> list[dict]:
        """팀별 최근 뉴스 수집."""
        query = f"{team_name} K리그"
        logger.info(f"[Naver] 팀 뉴스: {query}")

        articles = self._search_news(query, display=20)
        return self._enrich_articles(articles, team_name=team_name)

    # ── 내부 메서드 ───────────────────────────────────

    def _search_news(
        self,
        query: str,
        display: int = 10,
        start: int = 1,
    ) -> list[dict]:
        """
        네이버 검색 API 또는 직접 크롤링으로 뉴스 검색.
        """
        if self._api_available:
            return self._call_naver_api(query, display, start)
        return self._scrape_naver_search(query, display)

    def _call_naver_api(
        self,
        query: str,
        display: int = 10,
        start: int = 1,
    ) -> list[dict]:
        """네이버 검색 API 호출."""
        try:
            resp = self.http.get(
                self.NAVER_NEWS_API,
                params={"query": query, "display": display, "start": start, "sort": "date"},
                extra_headers={
                    "X-Naver-Client-Id": self._client_id,
                    "X-Naver-Client-Secret": self._client_secret,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            items = data.get("items", [])

            return [
                {
                    "title": self._clean_html_tags(item.get("title", "")),
                    "url": item.get("link", ""),
                    "published_at": item.get("pubDate", ""),
                    "description": self._clean_html_tags(item.get("description", "")),
                    "source": "naver_api",
                }
                for item in items
            ]
        except Exception as e:
            logger.error(f"[Naver] API 호출 실패: {e}")
            self._api_available = False
            return self._scrape_naver_search(query, display)

    def _scrape_naver_search(self, query: str, display: int = 10) -> list[dict]:
        """네이버 뉴스 검색 직접 크롤링 (API 폴백)."""
        url = "https://search.naver.com/search.naver"
        params = {"where": "news", "query": query, "sm": "tab_jum"}

        try:
            html = self._get_html(
                url + "?" + "&".join(f"{k}={v}" for k, v in params.items())
            )
            soup = BeautifulSoup(html, "html.parser")
            articles = []

            items = soup.select("ul.list_news li.bx")[:display]
            for item in items:
                title_tag = item.select_one("a.news_tit")
                desc_tag = item.select_one("div.dsc_wrap")
                date_tag = item.select_one("span.info")

                if not title_tag:
                    continue

                articles.append({
                    "title": title_tag.get_text(strip=True),
                    "url": title_tag.get("href", ""),
                    "published_at": date_tag.get_text(strip=True) if date_tag else "",
                    "description": desc_tag.get_text(strip=True) if desc_tag else "",
                    "source": "naver_scrape",
                })

            return articles

        except Exception as e:
            logger.error(f"[Naver] 직접 크롤링 실패: {e}")
            return []

    def _enrich_articles(
        self,
        articles: list[dict],
        player_name: str = "",
        team_name: str = "",
    ) -> list[dict]:
        """기사 URL에서 본문을 추출하여 articles를 enrichment."""
        enriched = []
        for article in articles:
            url = article.get("url", "")
            if not url:
                enriched.append(article)
                continue

            try:
                body = self._extract_article_body(url)
                enriched.append({
                    **article,
                    "content": body,
                    "player_name": player_name,
                    "team_name": team_name,
                    "keywords": self._extract_keywords(body, player_name, team_name),
                })
            except Exception as e:
                logger.debug(f"[Naver] 본문 추출 실패 (무시): {url} | {e}")
                enriched.append({**article, "content": article.get("description", "")})

        return enriched

    def _extract_article_body(self, article_url: str) -> str:
        """기사 본문 추출 (최대 2000자)."""
        html = self._get_html(article_url)
        soup = BeautifulSoup(html, "html.parser")

        # 여러 선택자 순서대로 시도
        selectors = [
            "article#dic_area",
            "div#articeBody",
            "div.article_body",
            "div#newsct_article",
            "div.news_end_box",
            "div._article_body_contents",
        ]

        for selector in selectors:
            tag = soup.select_one(selector)
            if tag:
                text = tag.get_text(separator=" ", strip=True)
                return self._clean_article_text(text)[:2000]

        # 폴백: <p> 태그 조합
        paragraphs = soup.find_all("p")
        text = " ".join(p.get_text(strip=True) for p in paragraphs if len(p.get_text(strip=True)) > 20)
        return self._clean_article_text(text)[:2000]

    def _clean_article_text(self, text: str) -> str:
        """광고 문구, 저작권 문구 제거."""
        remove_patterns = [
            "저작권자 ©",
            "무단전재 및 재배포 금지",
            "Copyright ©",
            "All rights reserved",
            "기자 소개",
            "구독하기",
        ]
        for pattern in remove_patterns:
            idx = text.find(pattern)
            if idx > 0:
                text = text[:idx]
        return text.strip()

    def _extract_keywords(
        self, text: str, player_name: str = "", team_name: str = ""
    ) -> list[str]:
        """기사에서 K리그 관련 키워드 추출 (간단한 규칙 기반)."""
        keywords = []
        if player_name and player_name in text:
            keywords.append(player_name)
        if team_name and team_name in text:
            keywords.append(team_name)

        k_league_keywords = ["K리그", "골", "도움", "선발", "교체", "부상", "인터뷰", "감독"]
        for kw in k_league_keywords:
            if kw in text:
                keywords.append(kw)

        return list(set(keywords))

    def _clean_html_tags(self, text: str) -> str:
        """<b>, </b> 등 HTML 태그 제거."""
        soup = BeautifulSoup(text, "html.parser")
        return soup.get_text(strip=True)
