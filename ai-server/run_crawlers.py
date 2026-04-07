"""
K리그 데이터 크롤러 메인 실행 진입점.

사용법:
  python run_crawlers.py                          # 전체 수집
  python run_crawlers.py --league K1              # K리그1만
  python run_crawlers.py --phase players          # 선수 명단만
  python run_crawlers.py --season 2025            # 2025 시즌만
  python run_crawlers.py --dry-run                # 저장 없이 테스트
  python run_crawlers.py --phase players derby    # 복수 페이즈
"""

import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

# 로그 설정
logger.remove()
logger.add(sys.stdout, format="<green>{time:HH:mm:ss}</green> | {level} | {message}")
logger.add(
    Path("logs") / "crawl_{time:YYYYMMDD}.log",
    rotation="1 day",
    retention="7 days",
    encoding="utf-8",
)

load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="K리그 데이터 크롤러",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument(
        "--league",
        nargs="+",
        choices=["K1", "K2"],
        default=["K1", "K2"],
        help="수집할 리그 (기본: K1 K2)",
    )
    parser.add_argument(
        "--season",
        nargs="+",
        type=int,
        default=[2024, 2025],
        help="수집할 시즌 연도 (기본: 2024 2025)",
    )
    parser.add_argument(
        "--phase",
        nargs="+",
        choices=["players", "player_stats", "team_results", "derby", "articles", "standings"],
        default=None,
        help="실행할 페이즈 (기본: 전체)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="실제 파일 저장 없이 테스트 실행",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 프로젝트 루트 = run_crawlers.py가 있는 디렉토리
    base_dir = Path(__file__).parent

    # 오케스트레이터 임포트 (여기서 해야 dotenv 로드 후 env 참조 가능)
    from crawlers.pipeline.orchestrator import CrawlOrchestrator

    orchestrator = CrawlOrchestrator(base_dir=base_dir, dry_run=args.dry_run)

    report = orchestrator.run(
        leagues=args.league,
        seasons=args.season,
        phases=args.phase,
    )

    # 종료 코드: 실패가 있으면 1
    if report.total_failures > 0:
        logger.warning(f"실패 항목 {report.total_failures}건 — 로그를 확인하세요.")
        sys.exit(1)


if __name__ == "__main__":
    main()
