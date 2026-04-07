"""
최근 5시즌 K리그1 선수 통계 일괄 수집 후 병합.

사용법:
  python run_fetch_5seasons.py            # 2022~2026 수집
  python run_fetch_5seasons.py --resume   # 중단된 지점부터 재개
  python run_fetch_5seasons.py --dry-run  # 선수 목록만 확인 (수집 안 함)

완료 후 자동으로 merge_players.py 실행 → all_players_merged.json 생성
"""

import argparse
import subprocess
import sys
from pathlib import Path

SEASONS = [2026, 2025, 2024, 2023, 2022]
OUTPUT_DIR = Path(__file__).parent / "data" / "processed" / "players_sofascore"


def already_done(season: int) -> bool:
    """해당 시즌 파일이 이미 완성됐는지 확인 (progress 파일 없고 output 있으면 완료)."""
    output = OUTPUT_DIR / f"all_players_{season}.json"
    progress = OUTPUT_DIR / f"progress_{season}.json"
    return output.exists() and not progress.exists()


def main():
    parser = argparse.ArgumentParser(description="최근 5시즌 K리그1 선수 통계 일괄 수집")
    parser.add_argument("--resume", action="store_true", help="중단된 지점부터 재개")
    parser.add_argument("--dry-run", action="store_true", help="선수 목록만 확인")
    args = parser.parse_args()

    python = sys.executable

    print(f"수집 대상 시즌: {SEASONS}")
    print("=" * 50)

    for season in SEASONS:
        if already_done(season) and not args.resume:
            print(f"\n[{season}] 이미 완료됨 — 건너뜀")
            continue

        print(f"\n[{season}] 수집 시작...")
        cmd = [python, "run_fetch_all_players.py", "--season", str(season)]
        if args.resume:
            cmd.append("--resume")
        if args.dry_run:
            cmd.append("--dry-run")

        result = subprocess.run(cmd, cwd=Path(__file__).parent)

        if result.returncode != 0:
            print(f"\n[{season}] 수집 중 오류 발생 (종료코드 {result.returncode})")
            print("나머지 시즌을 계속 진행하려면 Enter, 중단하려면 Ctrl+C...")
            try:
                input()
            except KeyboardInterrupt:
                print("\n중단됨.")
                sys.exit(1)
        else:
            print(f"[{season}] 완료 ✓")

    if args.dry_run:
        return

    # 모든 시즌 수집 후 병합
    print("\n" + "=" * 50)
    print("병합 시작...")
    subprocess.run([python, "merge_players.py"], cwd=Path(__file__).parent)
    print("\n전체 완료!")
    print("이제 비교 기능에서 5시즌 전체 선수 데이터를 사용할 수 있습니다.")
    print("테스트: python compare_players.py 손준호 세징야 --season 2024")


if __name__ == "__main__":
    main()
