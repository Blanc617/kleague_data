"""
k1_team_results.json의 스코어를 기반으로 현실적인 경기 이벤트 데이터를 생성합니다.
실제 kleague.com 크롤링 전 즉시 사용 가능한 샘플 데이터를 만듭니다.

실행:
    python generate_match_events.py
"""

import json
import random
from pathlib import Path

ROOT = Path(__file__).parent

# 팀별 선수 풀 (포지션별로 구분)
TEAM_SCORERS: dict[str, list[str]] = {
    "전북": ["구스타보", "이승기", "이진현", "이용", "홍정호", "김진수", "한교원", "박진섭", "류재문", "바로우", "신세계"],
    "울산": ["레오나르도", "엄원상", "이청용", "이범영", "설영우", "김기희", "아마노", "황일수", "고명진", "스탄코비치"],
    "서울": ["팔로세비치", "나상호", "기성용", "오스마르", "박주영", "황현수", "윤종규", "이상민", "주세종", "베리", "안현범"],
    "포항": ["하미메", "무릴로", "이명주", "신광훈", "임상협", "박찬용", "김광석", "완델손", "나성은", "이호재"],
    "인천": ["스테판", "오베르단", "문선민", "김정환", "김도혁", "이명주", "조용형", "박동진", "엄지성", "무고사"],
    "대전": ["제카", "박용우", "임채민", "김민준", "이상헌", "황재훈", "박수일", "마사", "안데르손", "임선영"],
    "광주": ["엄지성", "조재완", "이기혁", "박규현", "허율", "두현석", "최민서", "최준혁", "하창래", "이순민"],
    "강원": ["양현준", "안태현", "임민혁", "이현식", "황문기", "박시후", "정승용", "김대원", "윤빛가람", "서민우"],
    "제주": ["주민규", "이창민", "안현범", "구자철", "유리조", "이동희", "김봉수", "유인수", "이순민", "박진포"],
    "대구": ["세징야", "권창훈", "박상혁", "황순민", "정치인", "조현우", "홍정운", "케이타", "황재환", "박병현"],
    "수원FC": ["아코수아", "파비우", "가브리엘", "김건희", "이용래", "오현규", "이재권", "라스", "정재희", "김주찬"],
    "김천": ["임재익", "이재원", "이호인", "박민규", "한승규", "최원권", "이진용", "오재혁", "박재우", "문창진"],
    "안양": ["다닐로", "박상혁", "이강인", "서재원", "박영준", "최병찬", "박민서", "황인범", "조상준", "유리"],
}

TEAM_CARD_PLAYERS: dict[str, list[str]] = {
    "전북":   ["홍정호", "김진수", "이용", "류재문", "신세계"],
    "울산":   ["레오나르도", "이범영", "설영우", "스탄코비치"],
    "서울":   ["오스마르", "팔로세비치", "윤종규", "주세종"],
    "포항":   ["하미메", "무릴로", "박찬용", "임상협"],
    "인천":   ["오베르단", "김정환", "조용형", "박동진"],
    "대전":   ["임채민", "박용우", "황재훈", "안데르손"],
    "광주":   ["이기혁", "박규현", "하창래", "최준혁"],
    "강원":   ["임민혁", "안태현", "정승용", "박시후"],
    "제주":   ["안현범", "이창민", "김봉수", "유리조"],
    "대구":   ["세징야", "권창훈", "정치인", "케이타"],
    "수원FC": ["파비우", "아코수아", "이용래", "라스"],
    "김천":   ["이재원", "임재익", "한승규", "오재혁"],
    "안양":   ["다닐로", "서재원", "박영준", "조상준"],
}


def pick_scorer(team: str, used: dict[str, int]) -> str:
    pool = TEAM_SCORERS.get(team, ["외국인선수"])
    weights = [max(1, 4 - used.get(p, 0)) for p in pool]
    chosen = random.choices(pool, weights=weights, k=1)[0]
    used[chosen] = used.get(chosen, 0) + 1
    return chosen


def pick_assister(team: str, scorer: str) -> str | None:
    if random.random() > 0.65:
        return None
    pool = [p for p in TEAM_SCORERS.get(team, []) if p != scorer]
    return random.choice(pool) if pool else None


def pick_card_player(team: str) -> str:
    pool = TEAM_CARD_PLAYERS.get(team, TEAM_SCORERS.get(team, ["선수"]))
    return random.choice(pool)


def generate_events(game: dict, global_scorer_count: dict) -> list[dict]:
    events = []
    home = game["home_team"]
    away = game["away_team"]
    home_goals = game["home_score"] or 0
    away_goals = game["away_score"] or 0
    total_goals = home_goals + away_goals

    available_minutes = list(range(1, 91))
    minutes = sorted(random.sample(available_minutes, min(total_goals, len(available_minutes))))
    home_minutes = sorted(random.sample(minutes, home_goals)) if home_goals <= len(minutes) else minutes[:home_goals]
    away_minutes = sorted([m for m in minutes if m not in home_minutes])[:away_goals]

    for minute in home_minutes:
        scorer = pick_scorer(home, global_scorer_count)
        assister = pick_assister(home, scorer)
        event: dict = {"minute": minute, "type": "goal", "team": home, "player": scorer}
        if assister:
            event["assist"] = assister
        events.append(event)

    for minute in away_minutes:
        scorer = pick_scorer(away, global_scorer_count)
        assister = pick_assister(away, scorer)
        event = {"minute": minute, "type": "goal", "team": away, "player": scorer}
        if assister:
            event["assist"] = assister
        events.append(event)

    # 자책골 (경기당 약 3% 확률)
    if total_goals > 0 and random.random() < 0.03:
        og_team = random.choice([home, away])
        og_player = pick_card_player(og_team)
        og_minute = random.randint(10, 85)
        events.append({"minute": og_minute, "type": "own_goal", "team": og_team, "player": og_player})

    # 경고 (경기당 평균 3~5개)
    num_yellows = random.randint(2, 6)
    yellow_minutes = sorted(random.sample(range(5, 90), min(num_yellows, 85)))
    yellow_players: dict[str, str] = {}
    for minute in yellow_minutes:
        team = random.choice([home, away])
        player = pick_card_player(team)
        key = f"{team}:{player}"
        if key in yellow_players:
            # 같은 선수가 이미 경고 → 퇴장 처리
            events.append({"minute": minute, "type": "yellow_red", "team": team, "player": player})
        else:
            yellow_players[key] = team
            events.append({"minute": minute, "type": "yellow_card", "team": team, "player": player})

    # 직접 퇴장 (경기당 약 5% 확률)
    if random.random() < 0.05:
        team = random.choice([home, away])
        player = pick_card_player(team)
        minute = random.randint(30, 90)
        events.append({"minute": minute, "type": "red_card", "team": team, "player": player})

    events.sort(key=lambda e: e["minute"])
    return events


def aggregate_player_stats(events_by_game: list[dict]) -> list[dict]:
    """경기 이벤트에서 선수별 시즌 누적 통계를 집계합니다."""
    stats: dict[tuple, dict] = {}

    for game in events_by_game:
        home = game["home_team"]
        away = game["away_team"]
        teams_in_game = {home, away}

        # 이 경기에 등장한 선수 추적 (출장수용)
        appeared: dict[tuple, bool] = {}

        for e in game.get("events", []):
            team = e.get("team", "")
            player = e.get("player", "")
            if not player or not team:
                continue

            key = (team, player)
            if key not in stats:
                stats[key] = {
                    "team": team,
                    "player_name": player,
                    "appearances": 0,
                    "goals": 0,
                    "assists": 0,
                    "own_goals": 0,
                    "yellow_cards": 0,
                    "red_cards": 0,
                }

            if key not in appeared:
                appeared[key] = True
                stats[key]["appearances"] += 1

            etype = e.get("type", "")
            if etype == "goal":
                stats[key]["goals"] += 1
                assist_player = e.get("assist")
                if assist_player:
                    akey = (team, assist_player)
                    if akey not in stats:
                        stats[akey] = {
                            "team": team,
                            "player_name": assist_player,
                            "appearances": 0,
                            "goals": 0,
                            "assists": 0,
                            "own_goals": 0,
                            "yellow_cards": 0,
                            "red_cards": 0,
                        }
                    if akey not in appeared:
                        appeared[akey] = True
                        stats[akey]["appearances"] += 1
                    stats[akey]["assists"] += 1
            elif etype == "own_goal":
                stats[key]["own_goals"] += 1
            elif etype == "yellow_card":
                stats[key]["yellow_cards"] += 1
            elif etype in ("red_card", "yellow_red"):
                stats[key]["red_cards"] += 1

    result = sorted(stats.values(), key=lambda p: (-p["goals"], -p["assists"]))
    return result


def main():
    random.seed(42)

    results_path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    if not results_path.exists():
        print("k1_team_results.json 없음")
        return

    # 실제 크롤링 데이터 덮어쓰기 방지
    out_path = ROOT / "data" / "processed" / "matches" / "match_events_2025.json"
    if out_path.exists():
        existing = json.loads(out_path.read_text(encoding="utf-8"))
        if existing.get("source") != "generated":
            print(
                f"[중단] {out_path.name} 에 실제 크롤링 데이터가 있습니다 "
                f"(source={existing.get('source')!r}).\n"
                "가짜 데이터로 덮어쓰려면 파일을 수동으로 삭제하거나 "
                "source 값을 'generated'으로 변경하세요."
            )
            return

    records = json.loads(results_path.read_text(encoding="utf-8"))

    seen: set = set()
    unique = []
    for r in records:
        gid = r.get("game_id")
        if gid and gid not in seen and r.get("finished"):
            seen.add(gid)
            unique.append(r)

    unique.sort(key=lambda r: (r.get("date", ""), r.get("game_id", 0)))
    print(f"총 {len(unique)}경기 이벤트 생성 중...")

    global_scorer_count: dict[str, int] = {}
    events_by_game = []

    for game in unique:
        events = generate_events(game, global_scorer_count)
        events_by_game.append({
            "game_id":    game["game_id"],
            "date":       game["date"],
            "home_team":  game["home_team"],
            "away_team":  game["away_team"],
            "home_score": game["home_score"],
            "away_score": game["away_score"],
            "events":     events,
        })

    # match_events 저장
    out_path = ROOT / "data" / "processed" / "matches" / "match_events_2025.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "season": 2025,
        "league": "K1",
        "source": "generated",
        "total_games": len(events_by_game),
        "events_by_game": events_by_game,
    }
    out_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    total_events = sum(len(g["events"]) for g in events_by_game)
    print(f"match_events 저장 완료: {out_path}")
    print(f"총 {total_events}개 이벤트 ({len(events_by_game)}경기)")

    # player_stats 집계 및 저장
    player_stats = aggregate_player_stats(events_by_game)
    stats_path = ROOT / "data" / "processed" / "players" / "player_stats_2025.json"
    stats_path.parent.mkdir(parents=True, exist_ok=True)
    stats_payload = {
        "season": 2025,
        "league": "K1",
        "source": "aggregated_from_events",
        "total_players": len(player_stats),
        "players": player_stats,
    }
    stats_path.write_text(json.dumps(stats_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"player_stats 저장 완료: {stats_path}")
    print(f"총 {len(player_stats)}명 선수 기록")

    # 상위 득점자 출력
    print("\n[상위 10 득점자]")
    for p in player_stats[:10]:
        print(f"  {p['team']} {p['player_name']}: {p['goals']}골 {p['assists']}도움 황카{p['yellow_cards']}")


if __name__ == "__main__":
    main()
