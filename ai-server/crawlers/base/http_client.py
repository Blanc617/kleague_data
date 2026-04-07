"""
공통 HTTP 클라이언트.
소스별 헤더·딜레이·재시도 정책을 캡슐화합니다.
"""

import random
import time
from typing import Any

import requests
from fake_useragent import UserAgent
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from crawlers.config.settings import SourceConfig


class HttpClient:
    """
    소스별 헤더·딜레이·재시도 정책을 캡슐화한 공통 HTTP 클라이언트.
    차단 리스크가 높은 소스는 UA 로테이션 + 랜덤 딜레이로 대응합니다.
    """

    _ua = UserAgent()

    def __init__(self, source_name: str, config: SourceConfig) -> None:
        self.source_name = source_name
        self.config = config
        self.session = requests.Session()
        self._request_count = 0

    def get(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> requests.Response:
        """
        동기 GET 요청.
        429 / 503 시 지수 백오프 재시도.
        """
        self._random_delay()
        headers = self._build_headers(extra_headers)

        for attempt in range(1, self.config.max_retries + 1):
            try:
                resp = self.session.get(
                    url,
                    params=params,
                    headers=headers,
                    timeout=self.config.timeout,
                )
                self._request_count += 1

                if resp.status_code == 200:
                    return resp

                if resp.status_code in (429, 503):
                    wait = 2 ** attempt + random.uniform(0, 1)
                    logger.warning(
                        f"[{self.source_name}] {resp.status_code} — {url} | "
                        f"retry {attempt}/{self.config.max_retries} in {wait:.1f}s"
                    )
                    time.sleep(wait)
                    headers = self._build_headers(extra_headers)  # UA 재로테이션
                    continue

                logger.warning(
                    f"[{self.source_name}] HTTP {resp.status_code} — {url}"
                )
                return resp

            except requests.RequestException as e:
                logger.error(f"[{self.source_name}] Request error: {e} | {url}")
                if attempt == self.config.max_retries:
                    raise

                time.sleep(2 ** attempt)

        raise RuntimeError(
            f"[{self.source_name}] Max retries ({self.config.max_retries}) exceeded: {url}"
        )

    def get_json(
        self,
        url: str,
        params: dict[str, Any] | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> dict | list:
        """JSON 응답 반환 헬퍼."""
        resp = self.get(url, params=params, extra_headers=extra_headers)
        resp.raise_for_status()
        return resp.json()

    def health_check(self, url: str) -> bool:
        """소스 가용성 확인 (HEAD 요청)."""
        try:
            resp = self.session.head(
                url,
                headers=self._build_headers(),
                timeout=5,
                allow_redirects=True,
            )
            return resp.status_code < 400
        except Exception:
            return False

    # ── private ──────────────────────────────────────

    def _random_delay(self) -> None:
        """robots.txt 준수 및 차단 방지용 랜덤 딜레이."""
        delay = random.uniform(self.config.min_delay, self.config.max_delay)
        time.sleep(delay)

    def _build_headers(
        self, extra: dict[str, str] | None = None
    ) -> dict[str, str]:
        """매 요청마다 새 UA 생성 + 기본 헤더 구성."""
        headers = {
            "User-Agent": self._ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
            "Accept-Encoding": "gzip, deflate, br",
            "Connection": "keep-alive",
        }
        if extra:
            headers.update(extra)
        return headers

    @property
    def request_count(self) -> int:
        return self._request_count
