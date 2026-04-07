"""
Redis 기반 RAG 쿼리 캐시.
동일 질문에 대한 LLM·임베딩 API 호출을 방지합니다.
Redis 미연결 시 캐시 비활성화로 graceful degradation됩니다.
"""

import hashlib
import json
import os
from contextlib import contextmanager

from loguru import logger

try:
    import redis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class RAGCache:
    """
    TTL 기반 Redis 쿼리 캐시.

    환경변수:
        REDIS_URL — Redis 연결 URL (기본값: redis://localhost:6379/0)

    TTL 전략:
        - 경기 결과 데이터는 불변 → 1시간(3600초) TTL
        - 라이브 중계 중에는 TTL을 줄여 최신성 확보 가능
    """

    DEFAULT_TTL = 3600         # 1시간
    KEY_PREFIX = "rag:query:"

    def __init__(
        self,
        redis_url: str | None = None,
        ttl: int = DEFAULT_TTL,
    ) -> None:
        self._ttl = ttl
        self._enabled = False
        self._client = None

        if not _REDIS_AVAILABLE:
            logger.warning("redis 패키지 미설치 → 캐시 비활성화")
            return

        url = redis_url or os.environ.get("REDIS_URL", "redis://localhost:6379/0")
        try:
            self._client = redis.from_url(url, decode_responses=True)
            self._client.ping()
            self._enabled = True
            logger.info(f"Redis 캐시 연결 완료: {url}")
        except Exception as e:
            logger.warning(f"Redis 연결 실패 → 캐시 비활성화: {e}")

    def get(self, query: str, filters: dict | None = None) -> str | None:
        """캐시 히트 시 저장된 답변을 반환합니다. 미스 시 None."""
        if not self._enabled:
            return None
        try:
            key = self.make_key(query, filters)
            value = self._client.get(key)
            if value:
                logger.debug(f"캐시 히트: {key[:16]}...")
            return value
        except Exception as e:
            logger.warning(f"캐시 get 실패: {e}")
            return None

    def set(self, query: str, answer: str, filters: dict | None = None) -> None:
        """답변을 TTL과 함께 캐시에 저장합니다."""
        if not self._enabled:
            return
        try:
            key = self.make_key(query, filters)
            self._client.setex(key, self._ttl, answer)
            logger.debug(f"캐시 저장: {key[:16]}... (TTL={self._ttl}s)")
        except Exception as e:
            logger.warning(f"캐시 set 실패: {e}")

    def make_key(self, query: str, filters: dict | None = None) -> str:
        """SHA-256 기반 캐시 키 생성."""
        raw = query + json.dumps(filters or {}, sort_keys=True)
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"{self.KEY_PREFIX}{digest}"

    def is_available(self) -> bool:
        """Redis 연결 상태 확인."""
        return self._enabled

    def flush_all(self) -> None:
        """캐시 전체 삭제 (개발/테스트용)."""
        if not self._enabled:
            return
        keys = self._client.keys(f"{self.KEY_PREFIX}*")
        if keys:
            self._client.delete(*keys)
            logger.info(f"캐시 {len(keys)}개 삭제 완료")

    @contextmanager
    def disabled(self):
        """캐시를 일시 비활성화하는 컨텍스트 매니저 (테스트용)."""
        original = self._enabled
        self._enabled = False
        try:
            yield
        finally:
            self._enabled = original
