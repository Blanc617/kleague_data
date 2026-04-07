"""
K리그1 전체 선수 SofaScore 상세 기록 일괄 수집.

사용법:
  python run_fetch_all_players.py                    # 최신 시즌 전체 팀
  python run_fetch_all_players.py --season 2025      # 특정 시즌
  python run_fetch_all_players.py --season 2025 --team 6908   # 특정 팀만
  python run_fetch_all_players.py --dry-run          # 선수 목록만 확인
  python run_fetch_all_players.py --resume           # 중단된 곳부터 재개

출력: data/processed/players_sofascore/
  - all_players_{season}.json   : 모든 선수 프로필 + 통계
  - progress_{season}.json      : 수집 진행 상태 (재개용)
"""

import argparse
import json
import sys
import time
from pathlib import Path

try:
    from curl_cffi import requests as cf_requests
except ImportError:
    print("[오류] curl_cffi 패키지가 없습니다: pip install curl_cffi")
    sys.exit(1)

# ── 상수 ──────────────────────────────────────────────────
K1_LEAGUE_ID = 410
BASE = "https://api.sofascore.com/api/v1"
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.sofascore.com/",
    "Accept": "application/json",
}
OUTPUT_DIR = Path(__file__).parent / "data" / "processed" / "players_sofascore"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

DELAY_SHORT = 0.5   # 선수 통계 요청 간격 (초)
DELAY_LONG  = 1.5   # 팀 로스터 요청 간격 (초)


def make_session():
    s = cf_requests.Session(impersonate="chrome124")
    s.headers.update(HEADERS)
    return s


# ── SofaScore API 헬퍼 ────────────────────────────────────

def get_seasons(s) -> list[dict]:
    r = s.get(f"{BASE}/unique-tournament/{K1_LEAGUE_ID}/seasons", timeout=15)
    r.raise_for_status()
    return r.json().get("seasons", [])


def get_teams(s, season_id: int) -> list[dict]:
    r = s.get(f"{BASE}/unique-tournament/{K1_LEAGUE_ID}/season/{season_id}/teams", timeout=15)
    r.raise_for_status()
    return r.json().get("teams", [])


def get_team_players(s, team_id: int) -> list[dict]:
    r = s.get(f"{BASE}/team/{team_id}/players", timeout=15)
    if r.status_code != 200:
        return []
    data = r.json()
    players = []
    for p in data.get("players", []) + data.get("foreignPlayers", []):
        player = p.get("player", p)
        if isinstance(player, dict) and player.get("id"):
            players.append(player)
    # 중복 제거
    seen = set()
    unique = []
    for p in players:
        if p["id"] not in seen:
            seen.add(p["id"])
            unique.append(p)
    return unique


def get_player_season_stats(s, player_id: int, league_id: int, season_id: int) -> dict:
    """특정 선수의 특정 리그+시즌 통계."""
    url = f"{BASE}/player/{player_id}/unique-tournament/{league_id}/season/{season_id}/statistics/overall"
    r = s.get(url, timeout=15)
    if r.status_code != 200:
        return {}
    return r.json().get("statistics", {})


def get_player_all_seasons(s, player_id: int) -> list[dict]:
    """선수의 전 시즌 통계 (모든 리그 포함)."""
    r = s.get(f"{BASE}/player/{player_id}/statistics/seasons", timeout=15)
    if r.status_code != 200:
        return []

    season_entries = r.json().get("uniqueTournamentSeasons", [])
    all_stats = []

    for entry in season_entries:
        league = entry["uniqueTournament"]
        for season in entry.get("seasons", []):
            url = (
                f"{BASE}/player/{player_id}"
                f"/unique-tournament/{league['id']}"
                f"/season/{season['id']}"
                f"/statistics/overall"
            )
            try:
                rs = s.get(url, timeout=15)
                if rs.status_code != 200:
                    continue
                stats = rs.json().get("statistics", {})
                all_stats.append({
                    "league": league["name"],
                    "league_id": league["id"],
                    "season": season.get("year") or season.get("name", ""),
                    "season_id": season["id"],
                    "appearances": stats.get("appearances", 0),
                    "minutes_played": stats.get("minutesPlayed", 0),
                    "goals": stats.get("goals", 0),
                    "assists": stats.get("assists", 0),
                    "rating": round(stats.get("rating", 0), 2),
                    "total_shots": stats.get("totalShots", 0),
                    "shots_on_target": stats.get("shotsOnTarget", 0),
                    "xg": round(stats.get("expectedGoals", 0), 4),
                    "xa": round(stats.get("expectedAssists", 0), 4),
                    "key_passes": stats.get("keyPasses", 0),
                    "accurate_passes": stats.get("accuratePasses", 0),
                    "total_passes": stats.get("totalPasses", 0),
                    "successful_dribbles": stats.get("successfulDribbles", 0),
                    "tackles": stats.get("tackles", 0),
                    "interceptions": stats.get("interceptions", 0),
                    "yellow_cards": stats.get("yellowCards", 0),
                    "red_cards": stats.get("redCards", 0),
                })
                time.sleep(DELAY_SHORT)
            except Exception:
                continue

    all_stats.sort(key=lambda x: x.get("season", ""), reverse=True)
    return all_stats


# ── 메인 수집 로직 ────────────────────────────────────────

def collect(args):
    s = make_session()

    # 시즌 선택
    print("[1/4] 시즌 목록 로딩...")
    seasons = get_seasons(s)
    if not seasons:
        print("시즌 정보를 가져올 수 없습니다.")
        sys.exit(1)

    if args.season:
        season = next((x for x in seasons if str(x.get("year") or x.get("name")) == str(args.season)), None)
        if not season:
            print(f"시즌 {args.season}을 찾을 수 없습니다. 사용 가능: {[x.get('year') for x in seasons[:6]]}")
            sys.exit(1)
    else:
        season = seasons[0]  # 최신 시즌

    season_label = str(season.get("year") or season.get("name"))
    season_id = season["id"]
    print(f"    시즌: {season_label} (id={season_id})")

    # 팀 목록
    print("[2/4] 팀 로스터 로딩...")
    teams = get_teams(s, season_id)
    if args.team:
        teams = [t for t in teams if t["id"] == args.team]
        if not teams:
            print(f"팀 ID {args.team}을 찾을 수 없습니다.")
            sys.exit(1)
    print(f"    {len(teams)}개 팀")

    # 선수 목록 수집
    print("[3/4] 선수 목록 수집...")
    all_players_info = []  # {id, name, position, team_name, team_id}
    for team in teams:
        time.sleep(DELAY_LONG)
        players = get_team_players(s, team["id"])
        for p in players:
            all_players_info.append({
                "id": p["id"],
                "name": p.get("name", ""),
                "position": p.get("position", ""),
                "team_name": team["name"],
                "team_id": team["id"],
            })
        print(f"    {team['name']}: {len(players)}명")

    # 중복 선수 제거 (이적 등)
    seen = set()
    unique_players = []
    for p in all_players_info:
        if p["id"] not in seen:
            seen.add(p["id"])
            unique_players.append(p)

    print(f"    총 {len(unique_players)}명 (중복 제거 후)")

    if args.dry_run:
        print("\n[dry-run] 선수 목록:")
        for p in unique_players:
            print(f"  {p['name']} ({p['position']}) | {p['team_name']}")
        return

    # 진행 상태 파일 (재개용)
    progress_path = OUTPUT_DIR / f"progress_{season_label}.json"
    output_path = OUTPUT_DIR / f"all_players_{season_label}.json"

    # 재개: 이미 수집된 선수 목록 로드
    done_ids: set[int] = set()
    results: list[dict] = []
    if args.resume and progress_path.exists():
        progress = json.loads(progress_path.read_text(encoding="utf-8"))
        done_ids = set(progress.get("done_ids", []))
        if output_path.exists():
            results = json.loads(output_path.read_text(encoding="utf-8"))
        print(f"    재개: {len(done_ids)}명 이미 완료")

    remaining = [p for p in unique_players if p["id"] not in done_ids]

    # 통계 수집
    print(f"\n[4/4] 시즌별 통계 수집 ({len(remaining)}명)...")
    for i, p_info in enumerate(remaining, 1):
        pid = p_info["id"]
        name = p_info["name"]
        team = p_info["team_name"]

        try:
            stats = get_player_all_seasons(s, pid)
            results.append({
                "id": pid,
                "name": name,
                "position": p_info["position"],
                "current_team": team,
                "season_stats": stats,
            })
            done_ids.add(pid)

            # 진행 저장 (10명마다)
            if i % 10 == 0 or i == len(remaining):
                output_path.write_text(
                    json.dumps(results, ensure_ascii=False, indent=2),
                    encoding="utf-8"
                )
                progress_path.write_text(
                    json.dumps({"done_ids": list(done_ids)}, ensure_ascii=False),
                    encoding="utf-8"
                )
                print(f"    [{i}/{len(remaining)}] {name} ({team}) | {len(stats)}시즌 저장됨")
            else:
                print(f"    [{i}/{len(remaining)}] {name} ({team}) | {len(stats)}시즌")

        except Exception as e:
            print(f"    [{i}/{len(remaining)}] {name} 실패: {e}")
            continue

    print(f"\n완료! 총 {len(results)}명")
    print(f"저장 위치: {output_path}")

    # 진행 파일 정리
    if progress_path.exists():
        progress_path.unlink()


def main():
    parser = argparse.ArgumentParser(description="K리그1 전체 선수 SofaScore 통계 일괄 수집")
    parser.add_argument("--season", type=int, default=None, help="수집 시즌 (예: 2025)")
    parser.add_argument("--team", type=int, default=None, help="특정 팀 ID만 수집")
    parser.add_argument("--dry-run", action="store_true", help="선수 목록만 출력 (수집 안 함)")
    parser.add_argument("--resume", action="store_true", help="중단된 지점부터 재개")
    args = parser.parse_args()

    collect(args)


if __name__ == "__main__":
    main()
