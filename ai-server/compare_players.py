"""
선수 시즌 통계 비교 CLI.

사용법:
    python compare_players.py 손준호 세징야
    python compare_players.py 손준호 세징야 --season 2024
    python compare_players.py 손준호 세징야 --season 2025 --json
    python compare_players.py --search 손준호
"""

import argparse
import json
import sys

from data_engine.player_comparison import PlayerComparisonEngine


def main():
    parser = argparse.ArgumentParser(description="K리그 선수 시즌 통계 비교")
    parser.add_argument("player1", nargs="?", help="첫 번째 선수 이름")
    parser.add_argument("player2", nargs="?", help="두 번째 선수 이름")
    parser.add_argument("--season", type=int, default=None, help="시즌 연도 (기본: 최신)")
    parser.add_argument("--json", action="store_true", help="JSON 원본 출력")
    parser.add_argument("--search", metavar="NAME", help="선수 이름 검색")
    parser.add_argument("--seasons", action="store_true", help="사용 가능한 시즌 목록 출력")
    args = parser.parse_args()

    engine = PlayerComparisonEngine().load()

    # ── 시즌 목록 ──
    if args.seasons:
        print("사용 가능한 시즌:", engine.get_available_seasons())
        return

    # ── 선수 검색 ──
    if args.search:
        results = engine.search_player(args.search, args.season)
        print(f"'{args.search}' 검색 결과 (유사도 순):")
        for name in results:
            print(f"  - {name}")
        return

    # ── 비교 ──
    if not args.player1 or not args.player2:
        parser.print_help()
        sys.exit(1)

    result = engine.compare(args.player1, args.player2, args.season)

    if args.json:
        # PlayerProfile은 dataclass라 직렬화 필요
        from dataclasses import asdict
        output = {
            "season": result["season"],
            "player1": asdict(result["player1"]),
            "player2": asdict(result["player2"]),
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
        return

    # ── 일반 출력 ──
    p1, p2 = result["player1"], result["player2"]

    if not p1.found():
        print(f"\n[경고] '{args.player1}' — {result['season']}시즌 데이터 없음")
        print(f"  비슷한 이름:", ", ".join(engine.search_player(args.player1, result["season"])[:5]))
    if not p2.found():
        print(f"\n[경고] '{args.player2}' — {result['season']}시즌 데이터 없음")
        print(f"  비슷한 이름:", ", ".join(engine.search_player(args.player2, result["season"])[:5]))

    print()
    print(result["summary"])
    print()
    print(result["table"])


if __name__ == "__main__":
    main()
