"""
크롤러 전역 설정값.
"""

from dataclasses import dataclass


@dataclass
class SourceConfig:
    name: str
    min_delay: float       # 요청 간 최소 대기 (초)
    max_delay: float       # 요청 간 최대 대기 (초)
    max_retries: int       # 최대 재시도 횟수
    timeout: int           # 요청 타임아웃 (초)
    cache_ttl_hours: int   # raw 캐시 유효 시간


SOURCE_CONFIGS: dict[str, SourceConfig] = {
    "kleague": SourceConfig(
        name="kleague",
        min_delay=2.0,
        max_delay=4.0,
        max_retries=3,
        timeout=15,
        cache_ttl_hours=24,
    ),
    "transfermarkt": SourceConfig(
        name="transfermarkt",
        min_delay=3.0,
        max_delay=6.0,
        max_retries=3,
        timeout=20,
        cache_ttl_hours=24,
    ),
    "wikipedia": SourceConfig(
        name="wikipedia",
        min_delay=0.5,
        max_delay=1.0,
        max_retries=2,
        timeout=10,
        cache_ttl_hours=72,
    ),
    "naver": SourceConfig(
        name="naver",
        min_delay=1.0,
        max_delay=2.0,
        max_retries=3,
        timeout=15,
        cache_ttl_hours=12,
    ),
    "fotmob": SourceConfig(
        name="fotmob",
        min_delay=1.0,
        max_delay=2.5,
        max_retries=3,
        timeout=15,
        cache_ttl_hours=6,
    ),
}

# 수집 대상 시즌
TARGET_SEASONS = [2024, 2025]

# 데이터 저장 경로 (run_crawlers.py 기준 상대경로)
DATA_RAW_DIR = "data/raw"
DATA_PROCESSED_DIR = "data/processed"
LOG_DIR = "logs"
