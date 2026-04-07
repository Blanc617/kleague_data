"""
kleague.com 공식 사이트 크롤러.
차단 리스크: 높음 → 503/403 연속 3회 시 자동으로 비활성화됩니다.
"""

from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup
from loguru import logger

from crawlers.base.base_crawler import BaseCrawler
from crawlers.config.settings import SOURCE_CONFIGS
from crawlers.config.teams import K1_TEAMS, K2_TEAMS, TeamMeta


class KleagueCrawler(BaseCrawler):
    """
    kleague.com에서 공식 경기 결과, 팀 순위, 선수 기록 수집.

    차단 대응:
    - 요청 간 2~4초 랜덤 딜레이
    - Referer: https://www.kleague.com 헤더
    - 503/403 연속 3회 → is_available = False
    """

    BASE_URL = "https://www.kleague.com"

    LEAGUE_IDS = {"K1": "1", "K2": "2"}

    # 실제 AJAX API 엔드포인트
    SCHEDULE_API    = "https://www.kleague.com/getScheduleList.do"
    RECORD_API      = "https://www.kleague.com/record/teamRank.do"
    MATCH_EVENT_API = "https://www.kleague.com/api/ddf/match/matchInfo.do"
    MATCH_PAGE_URL  = "https://www.kleague.com/match.do"

    def __init__(self, raw_cache_dir: Path) -> None:
        super().__init__(SOURCE_CONFIGS["kleague"], raw_cache_dir)
        self._failure_count = 0
        self._max_failures = 3
        self._available = True
        self._extra_headers = {
            "Referer": "https://www.kleague.com/",
        }

    def is_available(self) -> bool:
        if not self._available:
            return False
        ok = self.http.health_check(self.BASE_URL)
        if not ok:
            self._failure_count += 1
            if self._failure_count >= self._max_failures:
                self._available = False
                logger.warning("[Kleague] 접근 불가로 비활성화됨")
        return ok

    # ── BaseCrawler 추상 메서드 구현 ──────────────────

    def crawl_players(self, league: Literal["K1", "K2"]) -> list[dict]:
        """
        팀별 선수 명단 페이지 순회하며 수집.
        URL: /record/team.do?leagueId={id}&teamId={team_code}&year={year}
        """
        logger.info(f"[Kleague] 선수 명단 수집: {league}")
        teams = K1_TEAMS if league == "K1" else K2_TEAMS
        league_id = self.LEAGUE_IDS[league]
        all_players = []

        for team in teams:
            url = (
                f"{self.RECORD_URL}"
                f"?leagueId={league_id}&teamId={team.kleague_team_id}&year=2025"
            )
            try:
                html = self._get_html(url, extra_headers=self._extra_headers)
                players = self._parse_player_list(html, team, league)
                all_players.extend(players)
                logger.info(f"  └─ {team.name_ko}: {len(players)}명")
            except Exception as e:
                self._record_failure()
                logger.warning(f"[Kleague] 선수 수집 실패: {team.name_ko} | {e}")

        return all_players

    def crawl_player_stats(
        self, player_id: str, seasons: list[int]
    ) -> list[dict]:
        """
        선수 개인 기록 페이지 수집.
        URL: /stats/playerStat.do?season={year}&leagueId={id}
        """
        results = []
        for season in seasons:
            for league_id in self.LEAGUE_IDS.values():
                url = (
                    f"{self.RECORD_URL}"
                    f"?year={season}&leagueId={league_id}"
                )
                try:
                    html = self._get_html(url, extra_headers=self._extra_headers)
                    stats = self._parse_player_stats_page(html, player_id, season)
                    results.extend(stats)
                except Exception as e:
                    self._record_failure()
                    logger.warning(f"[Kleague] 기록 수집 실패: {player_id} {season} | {e}")

        return results

    def crawl_team_results(self, team_name: str, season: int) -> list[dict]:
        """
        팀 경기 결과 수집.
        POST /getScheduleList.do — month 파라미터 필수 → 월별 루프.
        """
        team = self._find_team(team_name)
        if not team:
            logger.warning(f"[Kleague] 팀 메타 없음: {team_name}")
            return []

        league_id = self.LEAGUE_IDS.get("K1") if team in K1_TEAMS else self.LEAGUE_IDS.get("K2")
        all_results = []
        seen_game_ids = set()

        for month in range(1, 13):
            payload = {
                "leagueId": league_id,
                "year": str(season),
                "month": f"{month:02d}",
            }
            try:
                data = self._post_json(self.SCHEDULE_API, payload)
                monthly = self._parse_schedule_json(data, team.kleague_team_id, season)
                # 해당 팀 경기만 필터링 + 중복 제거
                for match in monthly:
                    gid = match.get("game_id")
                    if gid and gid in seen_game_ids:
                        continue
                    if (match.get("home_team_id") == team.kleague_team_id or
                            match.get("away_team_id") == team.kleague_team_id):
                        all_results.append(match)
                        if gid:
                            seen_game_ids.add(gid)
            except Exception as e:
                self._record_failure()
                logger.debug(f"[Kleague] {team_name} {season}/{month:02d} 실패: {e}")

        return all_results

    def crawl_match_events(
        self,
        game_id: int,
        year: int = 2025,
        meet_seq: int = 1,
        home_team: str = "",
        away_team: str = "",
    ) -> dict:
        """
        특정 경기의 이벤트(득점, 도움, 경고, 퇴장) 수집.
        POST /api/ddf/match/matchInfo.do — form data: year, meetSeq, gameId
        반환: {"game_id": ..., "events": [...]}
        """
        try:
            # 세션 쿠키 갱신 (JSESSIONID 필요)
            self._ensure_match_session(game_id, year, meet_seq)
            data = self._post_form(
                self.MATCH_EVENT_API,
                {"year": str(year), "meetSeq": str(meet_seq), "gameId": str(game_id)},
            )
            return self._parse_match_events(data, game_id, home_team=home_team, away_team=away_team)
        except Exception as e:
            logger.warning(f"[Kleague] 경기 이벤트 수집 실패: game_id={game_id} | {e}")
            return {"game_id": game_id, "events": []}

    def crawl_all_match_events(
        self, game_ids: list[int], delay: float = 1.5
    ) -> list[dict]:
        """여러 경기 이벤트 일괄 수집."""
        import time
        results = []
        for i, gid in enumerate(game_ids, 1):
            logger.info(f"[Kleague] 이벤트 수집 {i}/{len(game_ids)}: game_id={gid}")
            result = self.crawl_match_events(gid)
            if result.get("events"):
                results.append(result)
            time.sleep(delay)
        logger.info(f"[Kleague] 이벤트 수집 완료: {len(results)}/{len(game_ids)}경기")
        return results

    def crawl_standings(self, league: Literal["K1", "K2"], season: int) -> list[dict]:
        """리그 순위/팀 기록 수집. POST /record/teamRank.do"""
        league_id = self.LEAGUE_IDS[league]
        payload = {"leagueId": league_id, "year": str(season)}

        try:
            data = self._post_json(self.RECORD_API, payload)
            return self._parse_standings_json(data, league, season)
        except Exception as e:
            self._record_failure()
            logger.error(f"[Kleague] 순위 수집 실패: {league} {season} | {e}")
            return []

    # ── 파싱 메서드 ───────────────────────────────────

    def _parse_player_list(
        self, html: str, team: TeamMeta, league: str
    ) -> list[dict]:
        """선수 목록 테이블 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        players = []

        # kleague.com 실제 선택자는 배포 후 확인 필요
        rows = soup.select("table.player-list tbody tr, table.tbl-list tbody tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 4:
                continue

            try:
                jersey = cols[0].get_text(strip=True)
                position = cols[1].get_text(strip=True)
                name = cols[2].get_text(strip=True)
                nationality = cols[3].get_text(strip=True) if len(cols) > 3 else ""
                birth = cols[4].get_text(strip=True) if len(cols) > 4 else ""

                if not name:
                    continue

                players.append({
                    "name_ko": name,
                    "team": team.name_ko,
                    "league": league,
                    "jersey_number": jersey,
                    "position": position,
                    "nationality": nationality,
                    "birth_text": birth,
                    "source": "kleague",
                })
            except Exception:
                continue

        return players

    def _parse_player_stats_page(
        self, html: str, player_id: str, season: int
    ) -> list[dict]:
        """선수 기록 통계 페이지 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        rows = soup.select("table.tbl-stat tbody tr, table tbody tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 6:
                continue

            try:
                name = cols[0].get_text(strip=True)
                # player_id와 이름 매칭은 후처리(dedup)에서 수행
                results.append({
                    "player_name": name,
                    "season": season,
                    "appearances": self._safe_int(cols[2].get_text(strip=True)),
                    "goals": self._safe_int(cols[3].get_text(strip=True)),
                    "assists": self._safe_int(cols[4].get_text(strip=True)),
                    "yellow_cards": self._safe_int(cols[5].get_text(strip=True)),
                    "red_cards": self._safe_int(cols[6].get_text(strip=True)) if len(cols) > 6 else 0,
                    "source": "kleague",
                })
            except Exception:
                continue

        return results

    def _parse_match_results(
        self, html: str, team_name: str, season: int
    ) -> list[dict]:
        """경기 결과 페이지 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        rows = soup.select("table.tbl-schedule tbody tr, ul.list-schedule li")
        for row in rows:
            cols = row.find_all("td") or row.find_all("span")
            if len(cols) < 5:
                continue

            try:
                date = cols[0].get_text(strip=True)
                home = cols[2].get_text(strip=True)
                score = cols[3].get_text(strip=True)
                away = cols[4].get_text(strip=True)
                venue = cols[5].get_text(strip=True) if len(cols) > 5 else ""

                # 스코어 파싱 (예: "2:1" 또는 "2-1")
                home_score, away_score = self._parse_score(score)

                results.append({
                    "season": season,
                    "date": date,
                    "home_team": home,
                    "away_team": away,
                    "home_score": home_score,
                    "away_score": away_score,
                    "venue": venue,
                    "source": "kleague",
                })
            except Exception:
                continue

        return results

    def _parse_standings(
        self, html: str, league: str, season: int
    ) -> list[dict]:
        """리그 순위 테이블 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        standings = []

        rows = soup.select("table.tbl-ranking tbody tr")
        for i, row in enumerate(rows, 1):
            cols = row.find_all("td")
            if len(cols) < 8:
                continue

            try:
                standings.append({
                    "rank": i,
                    "team": cols[1].get_text(strip=True),
                    "played": self._safe_int(cols[2].get_text(strip=True)),
                    "wins": self._safe_int(cols[3].get_text(strip=True)),
                    "draws": self._safe_int(cols[4].get_text(strip=True)),
                    "losses": self._safe_int(cols[5].get_text(strip=True)),
                    "goals_for": self._safe_int(cols[6].get_text(strip=True)),
                    "goals_against": self._safe_int(cols[7].get_text(strip=True)),
                    "points": self._safe_int(cols[8].get_text(strip=True)) if len(cols) > 8 else 0,
                    "season": season,
                    "league": league,
                    "source": "kleague",
                })
            except Exception:
                continue

        return standings

    # ── 유틸리티 ──────────────────────────────────────

    def _ensure_match_session(self, game_id: int, year: int, meet_seq: int) -> None:
        """matchInfo.do 호출 전 JSESSIONID 쿠키가 있는지 확인하고 없으면 갱신."""
        if not self.http.session.cookies.get("JSESSIONID"):
            url = (
                f"{self.MATCH_PAGE_URL}"
                f"?year={year}&leagueId=1&gameId={game_id}&meetSeq={meet_seq}"
            )
            try:
                self.http.session.get(url, headers=self._extra_headers, timeout=self.config.timeout)
            except Exception:
                pass  # 세션 갱신 실패해도 진행

    def _post_form(self, url: str, payload: dict) -> dict | list:
        """Form-data POST 요청. /api/ddf/ 엔드포인트 전용."""
        import time, random
        time.sleep(random.uniform(
            self.config.min_delay, self.config.max_delay
        ))
        resp = self.http.session.post(
            url,
            data=payload,
            headers={
                **self.http._build_headers(self._extra_headers),
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _post_json(self, url: str, payload: dict) -> dict | list:
        """JSON POST 요청. kleague AJAX API 전용."""
        import time, random
        time.sleep(random.uniform(
            self.config.min_delay, self.config.max_delay
        ))
        resp = self.http.session.post(
            url,
            json=payload,
            headers={
                **self.http._build_headers(self._extra_headers),
                "Content-Type": "application/json",
                "X-Requested-With": "XMLHttpRequest",
            },
            timeout=self.config.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def _parse_schedule_json(
        self, data: dict | list, team_id: str, season: int
    ) -> list[dict]:
        """
        /getScheduleList.do 응답 파싱.
        실제 응답 구조: {"resultCode":"200","data":{"scheduleList":[...]}}
        """
        if isinstance(data, dict) and data.get("resultCode") != "200":
            return []

        items = []
        if isinstance(data, dict):
            items = data.get("data", {}).get("scheduleList", [])

        results = []
        for item in items:
            try:
                results.append({
                    "game_id": item.get("gameId"),
                    "season": item.get("year", season),
                    "round": item.get("roundId", ""),
                    "date": item.get("gameDate", ""),
                    "time": item.get("gameTime", ""),
                    "competition": item.get("meetName", ""),
                    "home_team": item.get("homeTeamName", ""),
                    "home_team_id": item.get("homeTeam", ""),
                    "away_team": item.get("awayTeamName", ""),
                    "away_team_id": item.get("awayTeam", ""),
                    "home_score": item.get("homeGoal"),
                    "away_score": item.get("awayGoal"),
                    "venue": item.get("fieldNameFull", item.get("fieldName", "")),
                    "attendance": item.get("audienceQty"),
                    "finished": item.get("endYn") == "Y",
                    "broadcast": item.get("broadcastName", ""),
                    "source": "kleague",
                })
            except Exception:
                continue

        return results

    def _parse_standings_json(
        self, data: dict | list, league: str, season: int
    ) -> list[dict]:
        """
        /record/teamRank.do 응답 파싱.
        실제 응답 구조: {"resultCode":"200","data":{"teamRank":[...]}}
        """
        if isinstance(data, dict) and data.get("resultCode") != "200":
            logger.warning(f"[Kleague] 순위 API 오류: {data.get('resultMsg')}")
            return []

        items = []
        if isinstance(data, dict):
            inner = data.get("data", {})
            items = inner.get("teamRank", [])

        standings = []
        for item in items:
            try:
                standings.append({
                    "rank": item.get("rank", 0),
                    "team": item.get("teamName", ""),
                    "team_id": item.get("teamId", ""),
                    "played": self._safe_int(str(item.get("gameCount", 0))),
                    "wins": self._safe_int(str(item.get("winCnt", 0))),
                    "draws": self._safe_int(str(item.get("tieCnt", 0))),
                    "losses": self._safe_int(str(item.get("lossCnt", 0))),
                    "goals_for": self._safe_int(str(item.get("gainGoal", 0))),
                    "goals_against": self._safe_int(str(item.get("lossGoal", 0))),
                    "goal_diff": self._safe_int(str(item.get("gapCnt", 0))),
                    "points": self._safe_int(str(item.get("gainPoint", 0))),
                    "recent_5": [item.get(f"game0{i}", " ").strip() for i in range(1, 6)],
                    "season": season,
                    "league": league,
                    "source": "kleague",
                })
            except Exception:
                continue

        return standings

    def _parse_match_events(
        self,
        data: dict | list,
        game_id: int,
        home_team: str = "",
        away_team: str = "",
    ) -> dict:
        """
        /api/ddf/match/matchInfo.do 응답 파싱.
        응답 구조:
          data.homeScorer / data.awayScorer: [{name, isOwnGoal, time(분)}]
          data.firstHalf / data.secondHalf: [{eventName, playerName, teamName, timeMin, homeOrAway, ...}]
          data.homeLineup / data.awayLineup: [{playerName, positionName, backNumber, ...}]
          data.homeSubstitute / data.awaySubstitute: 교체 선수 목록
        골은 scorer 리스트에서(팀명은 home_team/away_team으로 직접 부여),
        카드/교체는 타임라인(timeMin + 후반은 +45)에서 추출.
        """
        if isinstance(data, dict) and data.get("resultCode") != "200":
            logger.debug(f"[Kleague] 이벤트 API 오류 game_id={game_id}: {data.get('resultMsg')}")
            return {"game_id": game_id, "events": [], "lineups": {}, "substitutions": []}

        if not isinstance(data, dict):
            return {"game_id": game_id, "events": [], "lineups": {}, "substitutions": []}

        inner = data.get("data", {})
        if not inner:
            return {"game_id": game_id, "events": [], "lineups": {}, "substitutions": []}

        events: list[dict] = []

        # ── 골 이벤트 (homeScorer / awayScorer) ──────────
        for side, team_name in (("homeScorer", home_team), ("awayScorer", away_team)):
            for scorer in inner.get(side, []) or []:
                name = (scorer.get("name") or "").strip()
                if not name:
                    continue
                minute = int(scorer.get("time") or 0)
                event_type = "own_goal" if scorer.get("isOwnGoal") else "goal"
                events.append({
                    "minute": minute,
                    "type": event_type,
                    "player": name,
                    "team": team_name,
                })

        # ── 타임라인 (firstHalf + secondHalf) ───────────
        ASSIST_NAMES     = {"도움", "assist"}
        YELLOW_NAMES     = {"경고", "yellow card"}
        RED_NAMES        = {"퇴장", "직접 퇴장", "red card"}
        YELLOW_RED_NAMES = {"경고 퇴장", "경고퇴장", "두 번째 경고"}
        # 교체 이벤트 이름 (교체아웃=off, 교체인=on)
        SUB_OFF_NAMES    = {"교체아웃", "교체 아웃", "교체나감", "substitution out"}
        SUB_ON_NAMES     = {"교체인", "교체 인", "교체들어옴", "substitution in"}
        SUB_GENERIC      = {"교체", "선수교체", "substitution"}

        # halfType 기준 minute 오프셋
        HALF_OFFSET = {1: 0, 2: 45, 3: 90, 4: 105}

        assist_by_game_minute: dict[int, str] = {}
        card_events: list[dict] = []
        sub_off_by_minute: dict[tuple, str] = {}   # (team, minute) → player_off
        sub_on_by_minute: dict[tuple, str] = {}    # (team, minute) → player_on
        generic_subs: list[dict] = []              # 방향 불명 교체 이벤트

        for item in (inner.get("firstHalf") or []) + (inner.get("secondHalf") or []) + \
                    (inner.get("EfirstHalf") or []) + (inner.get("EsecondHalf") or []):
            raw_name = (item.get("eventName") or "").strip()
            raw_lower = raw_name.lower()
            player = (item.get("playerName") or "").strip()
            team = (item.get("teamName") or "").strip()
            half_type = int(item.get("halfType") or 1)
            time_min = int(item.get("timeMin") or 0)
            game_minute = HALF_OFFSET.get(half_type, 0) + time_min

            if raw_name in ASSIST_NAMES:
                if player:
                    assist_by_game_minute[game_minute] = player
            elif raw_name in YELLOW_NAMES and player:
                card_events.append({"minute": game_minute, "type": "yellow_card", "team": team, "player": player})
            elif raw_name in RED_NAMES and player:
                card_events.append({"minute": game_minute, "type": "red_card", "team": team, "player": player})
            elif raw_name in YELLOW_RED_NAMES and player:
                card_events.append({"minute": game_minute, "type": "yellow_red", "team": team, "player": player})
            elif raw_name in SUB_OFF_NAMES and player:
                sub_off_by_minute[(team, game_minute)] = player
            elif raw_name in SUB_ON_NAMES and player:
                sub_on_by_minute[(team, game_minute)] = player
            elif raw_name in SUB_GENERIC and player:
                generic_subs.append({"minute": game_minute, "team": team, "player": player, "raw": raw_name})

        # 골 이벤트에 어시스트 정보 추가
        for e in events:
            if e["type"] == "goal":
                assist = assist_by_game_minute.get(e["minute"])
                if assist:
                    e["assist"] = assist

        events.extend(card_events)
        events.sort(key=lambda e: e["minute"])

        # ── 교체 정보 조합 ───────────────────────────────
        substitutions: list[dict] = []

        # 방향 구분된 교체 (off/on 매핑)
        all_keys = set(sub_off_by_minute.keys()) | set(sub_on_by_minute.keys())
        for key in sorted(all_keys, key=lambda k: k[1]):
            team_s, minute_s = key
            substitutions.append({
                "minute":     minute_s,
                "team":       team_s,
                "player_off": sub_off_by_minute.get(key, ""),
                "player_on":  sub_on_by_minute.get(key, ""),
            })

        # 방향 불명 교체: 같은 (팀, 분)에 짝지어진 게 있으면 off/on 추론
        unmatched_generic: list[dict] = []
        for g in generic_subs:
            key = (g["team"], g["minute"])
            already_handled = any(s["minute"] == g["minute"] and s["team"] == g["team"] for s in substitutions)
            if not already_handled:
                unmatched_generic.append(g)

        # 같은 팀+분에 2개씩 묶여 있으면 첫 번째=off, 두 번째=on으로 처리
        seen_generic: dict[tuple, list] = {}
        for g in unmatched_generic:
            key = (g["team"], g["minute"])
            seen_generic.setdefault(key, []).append(g["player"])
        for (team_g, min_g), players in seen_generic.items():
            if len(players) >= 2:
                substitutions.append({"minute": min_g, "team": team_g, "player_off": players[0], "player_on": players[1]})
            else:
                # 방향 불명 단일 교체 → substitution 이벤트로 저장 (off/on 미상)
                substitutions.append({"minute": min_g, "team": team_g, "player_off": players[0], "player_on": ""})

        substitutions.sort(key=lambda s: s["minute"])

        # ── 라인업 파싱 ───────────────────────────────────
        # kleague.com API는 homeLineup/awayLineup 또는 homePlayer/awayPlayer 등 다양한 키를 사용
        lineups: dict[str, dict] = {}
        LINEUP_KEY_CANDIDATES = [
            ("homeLineup", "awayLineup"),
            ("homePlayer", "awayPlayer"),
            ("homeSquad", "awaySquad"),
            ("homeStarting", "awayStarting"),
        ]
        for home_key, away_key in LINEUP_KEY_CANDIDATES:
            home_raw = inner.get(home_key)
            away_raw = inner.get(away_key)
            if home_raw or away_raw:
                lineups["home"] = self._parse_lineup_list(home_raw or [], home_team)
                lineups["away"] = self._parse_lineup_list(away_raw or [], away_team)
                break

        # 교체 벤치 선수 (선발 아님)
        BENCH_KEY_CANDIDATES = [
            ("homeSubstitute", "awaySubstitute"),
            ("homeBench", "awayBench"),
            ("homeReserve", "awayReserve"),
        ]
        for home_key, away_key in BENCH_KEY_CANDIDATES:
            home_bench = inner.get(home_key)
            away_bench = inner.get(away_key)
            if home_bench or away_bench:
                if "home" in lineups:
                    lineups["home"]["bench"] = self._parse_lineup_list(home_bench or [], home_team).get("starters", [])
                if "away" in lineups:
                    lineups["away"]["bench"] = self._parse_lineup_list(away_bench or [], away_team).get("starters", [])
                break

        return {
            "game_id":      game_id,
            "events":       events,
            "lineups":      lineups,
            "substitutions": substitutions,
        }

    def _parse_lineup_list(self, players: list, team_name: str) -> dict:
        """라인업 선수 목록 파싱. 공통 키 패턴 처리."""
        starters = []
        for p in (players or []):
            if not isinstance(p, dict):
                continue
            name = (
                p.get("playerName") or p.get("name") or p.get("player_name") or ""
            ).strip()
            if not name:
                continue
            starters.append({
                "player":   name,
                "team":     team_name,
                "position": (p.get("positionName") or p.get("position") or "").strip(),
                "jersey":   p.get("backNumber") or p.get("jerseyNumber") or p.get("back_number"),
            })
        return {"starters": starters, "bench": []}

    def _record_failure(self) -> None:
        self._failure_count += 1
        if self._failure_count >= self._max_failures:
            self._available = False
            logger.warning("[Kleague] 연속 실패 → 비활성화")

    def _find_team(self, team_name: str) -> TeamMeta | None:
        for t in K1_TEAMS + K2_TEAMS:
            if t.name_ko == team_name or t.short_name == team_name:
                return t
        return None

    def _parse_score(self, score_text: str) -> tuple[int, int]:
        """"2:1" / "2-1" 형태의 스코어 파싱."""
        for sep in (":", "-"):
            if sep in score_text:
                parts = score_text.split(sep)
                if len(parts) == 2:
                    return self._safe_int(parts[0]), self._safe_int(parts[1])
        return 0, 0

    def _safe_int(self, text: str) -> int:
        cleaned = text.strip().replace("-", "0")
        return int(cleaned) if cleaned.isdigit() else 0
