"""
SofaScore 기반 선수 기록 수집기.

사용법:
  python run_fetch_player.py "cho gue-sung"
  python run_fetch_player.py "son heung-min" --save
  python run_fetch_player.py "lee jae-sung" --pretty

출력 예시:
  조규성 (FW, 대한민국)
  ──────────────────────────────────────────
  리그              시즌   경기  골   도움  평점   xG   슈팅  출장(분)
  K League 1        2022   31   17    5   7.33  0.00  102   2462
  K League 1        2023   12    5    1   7.22  0.00   30    879
  Danish Superliga  23/24  30   12    4   7.24  0.00   66   2446
  ...
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

OUTPUT_DIR = Path(__file__).parent / "data" / "processed" / "players_sofascore"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

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

# 포지션 코드 한국어
POS_KO = {"F": "FW", "M": "MF", "D": "DF", "G": "GK"}


def make_session() -> cf_requests.Session:
    s = cf_requests.Session(impersonate="chrome124")
    s.headers.update(HEADERS)
    return s


def search_player(session, name: str) -> list[dict]:
    """영문 이름으로 선수 검색 → 후보 목록 반환."""
    r = session.get(f"{BASE}/search/all", params={"q": name}, timeout=15)
    r.raise_for_status()
    data = r.json()

    players = []
    for item in data.get("results", []):
        entity = item.get("entity", item)
        if not entity.get("id"):
            continue
        # type 필드가 있으면 player 타입만, 없으면 포지션으로 판단
        entity_type = item.get("type", "")
        position = entity.get("position", "")
        if entity_type and entity_type != "player":
            continue
        if not (position or entity.get("team")):
            continue
        players.append({
            "id": entity["id"],
            "name": entity.get("name", ""),
            "slug": entity.get("slug", ""),
            "position": POS_KO.get(position, position),
            "team": entity.get("team", {}).get("name", ""),
            "country": entity.get("country", {}).get("name", ""),
        })
    return players


def get_player_profile(session, player_id: int) -> dict:
    """선수 기본 프로필 반환."""
    r = session.get(f"{BASE}/player/{player_id}", timeout=15)
    r.raise_for_status()
    p = r.json().get("player", {})
    return {
        "id": p.get("id"),
        "name": p.get("name", ""),
        "position": POS_KO.get(p.get("position", ""), p.get("position", "")),
        "country": p.get("country", {}).get("name", ""),
        "date_of_birth": p.get("dateOfBirthTimestamp", ""),
        "height": p.get("height"),
        "preferred_foot": p.get("preferredFoot", ""),
        "shirt_number": p.get("shirtNumber"),
        "team": p.get("team", {}).get("name", "") if p.get("team") else "",
    }


def get_all_season_stats(session, player_id: int) -> list[dict]:
    """모든 시즌·리그 통계 반환."""
    r = session.get(f"{BASE}/player/{player_id}/statistics/seasons", timeout=15)
    r.raise_for_status()
    data = r.json()
    season_entries = data.get("uniqueTournamentSeasons", [])

    all_stats = []
    for entry in season_entries:
        league = entry["uniqueTournament"]
        league_name = league["name"]
        league_id = league["id"]
        league_country = league.get("category", {}).get("name", "")

        for season in entry.get("seasons", []):
            season_id = season["id"]
            season_label = season.get("year") or season.get("name", "")

            url = (
                f"{BASE}/player/{player_id}"
                f"/unique-tournament/{league_id}"
                f"/season/{season_id}"
                f"/statistics/overall"
            )
            try:
                rs = session.get(url, timeout=15)
                if rs.status_code != 200:
                    continue
                stats = rs.json().get("statistics", {})
                all_stats.append({
                    "league": league_name,
                    "league_country": league_country,
                    "league_id": league_id,
                    "season": season_label,
                    "season_id": season_id,
                    # 기본 기록
                    "appearances": stats.get("appearances", stats.get("matches", 0)),
                    "minutes_played": stats.get("minutesPlayed", 0),
                    "goals": stats.get("goals", 0),
                    "assists": stats.get("assists", 0),
                    "rating": round(stats.get("rating", 0), 2),
                    # 슈팅
                    "total_shots": stats.get("totalShots", 0),
                    "shots_on_target": stats.get("shotsOnTarget", 0),
                    "xg": round(stats.get("expectedGoals", 0), 4),
                    "xg_per90": round(stats.get("expectedGoalsPerNinety", 0), 4),
                    # 패스
                    "accurate_passes": stats.get("accuratePasses", 0),
                    "total_passes": stats.get("totalPasses", 0),
                    "key_passes": stats.get("keyPasses", 0),
                    "xa": round(stats.get("expectedAssists", 0), 4),
                    # 드리블
                    "successful_dribbles": stats.get("successfulDribbles", 0),
                    "total_dribbles": stats.get("totalDribbles", 0),
                    # 수비
                    "tackles": stats.get("tackles", 0),
                    "interceptions": stats.get("interceptions", 0),
                    "clearances": stats.get("clearances", 0),
                    # 카드
                    "yellow_cards": stats.get("yellowCards", 0),
                    "red_cards": stats.get("redCards", 0),
                    # 빅찬스
                    "big_chances_created": stats.get("bigChancesCreated", 0),
                    "big_chances_missed": stats.get("bigChancesMissed", 0),
                })
                time.sleep(0.4)
            except Exception as e:
                print(f"  [스킵] {league_name} {season_label}: {e}", file=sys.stderr)
                continue

    # 시즌 최신순 정렬
    all_stats.sort(key=lambda x: x.get("season", ""), reverse=True)
    return all_stats


def print_stats_table(profile: dict, stats: list[dict]) -> None:
    """터미널 테이블 출력."""
    pos = profile.get("position", "")
    country = profile.get("country", "")
    team = profile.get("team", "")
    print(f"\n{'='*62}")
    print(f"  {profile['name']}  ({pos}, {country}){f'  |  {team}' if team else ''}")
    print(f"{'='*62}")

    if not stats:
        print("  기록 없음")
        return

    # 리그별 그룹
    from itertools import groupby
    key = lambda x: x["league"]
    grouped = {}
    for s in stats:
        grouped.setdefault(s["league"], []).append(s)

    # 헤더
    print(f"  {'리그':<22} {'시즌':<8} {'경기':>4} {'골':>4} {'도움':>4} {'평점':>5} {'xG':>5} {'슈팅':>5} {'출장':>6}")
    print(f"  {'-'*22} {'-'*8} {'-'*4} {'-'*4} {'-'*4} {'-'*5} {'-'*5} {'-'*5} {'-'*6}")

    for league, entries in grouped.items():
        for e in entries:
            rating = f"{e['rating']:.2f}" if e["rating"] else "  -  "
            xg = f"{e['xg']:.2f}" if e["xg"] else "  -  "
            print(
                f"  {league:<22} {e['season']:<8} "
                f"{e['appearances']:>4} {e['goals']:>4} {e['assists']:>4} "
                f"{rating:>5} {xg:>5} {e['total_shots']:>5} "
                f"{e['minutes_played']:>6}"
            )
        print()

    print(f"{'='*62}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="SofaScore 선수 기록 수집")
    parser.add_argument("name", help="선수 영문 이름 (예: cho gue-sung)")
    parser.add_argument("--save", action="store_true", help="JSON 파일로 저장")
    parser.add_argument("--pretty", action="store_true", help="터미널 테이블 출력 (기본)")
    parser.add_argument("--id", type=int, default=None, help="선수 ID 직접 지정 (검색 생략)")
    args = parser.parse_args()

    session = make_session()

    # ── 선수 검색 ──────────────────────────────────────
    if args.id:
        player_id = args.id
        print(f"[직접 지정] 선수 ID: {player_id}")
    else:
        print(f"[검색] '{args.name}' 검색 중...")
        candidates = search_player(session, args.name)

        if not candidates:
            print("검색 결과 없음. 영문 이름을 확인하세요.")
            sys.exit(1)

        if len(candidates) == 1:
            player_id = candidates[0]["id"]
            print(f"  -> {candidates[0]['name']} ({candidates[0]['position']}, {candidates[0]['country']}) | {candidates[0]['team']}")
        else:
            print(f"  {len(candidates)}명 검색됨:")
            for i, c in enumerate(candidates[:8]):
                print(f"  [{i+1}] {c['name']} ({c['position']}, {c['country']}) — {c['team']}")
            try:
                choice = int(input("  선택 번호: ")) - 1
                player_id = candidates[choice]["id"]
            except (ValueError, IndexError):
                print("잘못된 선택입니다.")
                sys.exit(1)

    # ── 프로필 & 통계 수집 ────────────────────────────
    print(f"[수집] 선수 프로필 로딩...")
    profile = get_player_profile(session, player_id)
    print(f"  → {profile['name']} ({profile.get('position')}, {profile.get('country')})")

    print(f"[수집] 시즌별 통계 수집 중...")
    stats = get_all_season_stats(session, player_id)
    print(f"  → {len(stats)}개 시즌 수집 완료")

    # ── 출력 ──────────────────────────────────────────
    print_stats_table(profile, stats)

    # ── 저장 ──────────────────────────────────────────
    if args.save:
        slug = profile.get("name", args.name).lower().replace(" ", "_").replace("-", "_")
        out_path = OUTPUT_DIR / f"{slug}_{player_id}.json"
        result = {"profile": profile, "season_stats": stats}
        out_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[저장] {out_path}")


if __name__ == "__main__":
    main()
