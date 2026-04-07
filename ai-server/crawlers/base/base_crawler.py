"""
모든 소스 크롤러가 구현해야 할 추상 기반 클래스.
"""

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from pathlib import Path
from typing import Literal

from loguru import logger

from crawlers.base.http_client import HttpClient
from crawlers.config.settings import SourceConfig


class BaseCrawler(ABC):
    """
    crawl() 호출 → 원본 HTML/JSON을 raw/ 캐시에 저장 후 파싱 결과 반환.
    캐시 히트 시 재요청 없이 cached 데이터를 반환합니다.
    """

    def __init__(
        self, config: SourceConfig, raw_cache_dir: Path
    ) -> None:
        self.config = config
        self.raw_cache_dir = raw_cache_dir
        self.raw_cache_dir.mkdir(parents=True, exist_ok=True)
        self.http = HttpClient(config.name, config)

    # ── 구현 필수 메서드 ──────────────────────────────

    @abstractmethod
    def crawl_players(
        self, league: Literal["K1", "K2"]
    ) -> list[dict]:
        """선수 명단 수집. 반환값은 정규화 전 원시 dict 리스트."""
        ...

    @abstractmethod
    def crawl_player_stats(
        self, player_id: str, seasons: list[int]
    ) -> list[dict]:
        """특정 선수의 시즌별 개인 기록 수집."""
        ...

    @abstractmethod
    def crawl_team_results(
        self, team_name: str, season: int
    ) -> list[dict]:
        """팀의 시즌 전체 경기 결과 수집."""
        ...

    def is_available(self) -> bool:
        """소스 접근 가능 여부 확인. 서브클래스에서 오버라이드 가능."""
        return True

    # ── 캐시 유틸리티 ─────────────────────────────────

    def _cache_key(self, url: str) -> str:
        """URL → 캐시 파일명 (MD5 해시)."""
        return hashlib.md5(url.encode()).hexdigest()

    def _save_raw(self, cache_key: str, content: str) -> Path:
        """원본 응답을 raw 캐시 디렉토리에 저장."""
        path = self.raw_cache_dir / f"{cache_key}.html"
        path.write_text(content, encoding="utf-8")
        return path

    def _save_raw_json(self, cache_key: str, data: dict | list) -> Path:
        """JSON 원본 응답을 캐시에 저장."""
        path = self.raw_cache_dir / f"{cache_key}.json"
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return path

    def _load_raw_if_fresh(self, cache_key: str, ext: str = "html") -> str | None:
        """
        캐시가 존재하고 TTL 이내이면 내용을 반환.
        만료됐거나 없으면 None 반환.
        """
        path = self.raw_cache_dir / f"{cache_key}.{ext}"
        if not path.exists():
            return None

        mtime = datetime.fromtimestamp(path.stat().st_mtime)
        if datetime.now() - mtime > timedelta(hours=self.config.cache_ttl_hours):
            logger.debug(f"Cache expired: {path.name}")
            return None

        logger.debug(f"Cache hit: {path.name}")
        return path.read_text(encoding="utf-8")

    def _get_html(self, url: str, extra_headers: dict | None = None) -> str:
        """
        캐시 우선 조회 후 없으면 HTTP GET.
        결과를 raw 캐시에 저장하고 HTML 문자열 반환.
        """
        key = self._cache_key(url)
        cached = self._load_raw_if_fresh(key, "html")
        if cached:
            return cached

        resp = self.http.get(url, extra_headers=extra_headers)
        resp.raise_for_status()
        html = resp.text
        self._save_raw(key, html)
        return html

    def _get_json_cached(self, url: str, params: dict | None = None) -> dict | list:
        """
        캐시 우선 조회 후 없으면 HTTP GET (JSON).
        """
        key = self._cache_key(url + str(params or ""))
        cached = self._load_raw_if_fresh(key, "json")
        if cached:
            return json.loads(cached)

        data = self.http.get_json(url, params=params)
        self._save_raw_json(key, data)
        return data
