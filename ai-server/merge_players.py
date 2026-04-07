"""
players_sofascore/all_players_*.json 파일들을 하나로 병합.

수집 순서:
  1. 각 시즌별 수집 (연도마다 실행):
       python run_fetch_all_players.py --season 2025 --resume
       python run_fetch_all_players.py --season 2024 --resume
       python run_fetch_all_players.py --season 2023 --resume
       ...

  2. 병합 (이 스크립트):
       python merge_players.py

  3. 비교 테스트:
       python compare_players.py 손준호 세징야 --season 2024

출력: data/processed/players_sofascore/all_players_merged.json
"""

import json
import glob
from pathlib import Path

OUTPUT_DIR = Path(__file__).parent / "data" / "processed" / "players_sofascore"
OUTPUT_PATH = OUTPUT_DIR / "all_players_merged.json"


def merge():
    pattern = str(OUTPUT_DIR / "all_players_*.json")
    files = [f for f in sorted(glob.glob(pattern)) if "merged" not in f]

    if not files:
        print("수집된 파일이 없습니다.")
        print("먼저 아래 명령어로 시즌별 데이터를 수집하세요:\n")
        for year in range(2026, 2019, -1):
            print(f"  python run_fetch_all_players.py --season {year} --resume")
        return

    print(f"파일 {len(files)}개 발견:")
    for f in files:
        print(f"  {f}")
    print()

    merged: dict[int, dict] = {}

    for filepath in files:
        players = json.loads(Path(filepath).read_text(encoding="utf-8"))
        new_count = 0
        stat_added = 0

        for p in players:
            pid = p.get("id")
            if pid is None:
                continue

            if pid not in merged:
                merged[pid] = {
                    "id": pid,
                    "name": p.get("name", ""),
                    "position": p.get("position", ""),
                    "current_team": p.get("current_team", ""),
                    "season_stats": [],
                }
                new_count += 1

            # season_stats 병합 — (league_id, season) 중복 제거
            existing_keys = {
                (s.get("league_id"), s.get("season"))
                for s in merged[pid]["season_stats"]
            }
            for stat in p.get("season_stats", []):
                key = (stat.get("league_id"), stat.get("season"))
                if key not in existing_keys:
                    merged[pid]["season_stats"].append(stat)
                    existing_keys.add(key)
                    stat_added += 1

        fname = Path(filepath).name
        print(f"  {fname}: 선수 {len(players)}명 (신규 {new_count}명, 통계 +{stat_added}건)")

    result = list(merged.values())

    # K리그1 시즌별 선수 수 집계
    from collections import Counter
    k1_dist: Counter = Counter()
    for p in result:
        for s in p.get("season_stats", []):
            if s.get("league_id") == 410:
                k1_dist[s["season"]] += 1

    OUTPUT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )

    print(f"\n병합 완료: 총 {len(result)}명")
    print(f"저장: {OUTPUT_PATH}")
    print("\nK리그1 시즌별 선수 수:")
    for season in sorted(k1_dist):
        print(f"  {season}: {k1_dist[season]}명")


if __name__ == "__main__":
    merge()
