"""
FotMob 비공개 JSON API 크롤러.
라인업(선발/교체/포지션), 경기 이벤트 수집에 특화됩니다.

주요 엔드포인트:
  - /api/leagues?id=187        K리그1 시즌 경기 목록 + FotMob match ID
  - /api/matchDetails?matchId= 경기 상세 (라인업·이벤트·스코어)

FotMob match ID는 kleague game_id와 다르므로 날짜+팀명으로 매핑합니다.
"""

import json
import re
import time
from pathlib import Path
from typing import Literal

import requests
from loguru import logger

from crawlers.config.settings import SourceConfig

# FotMob K리그1 리그 ID
FOTMOB_K1_ID = 187

# FotMob 팀명 → 프로젝트 short_name 매핑
TEAM_NAME_MAP: dict[str, str] = {
    # 영문 FotMob 팀명 → 한글 short_name
    "Jeonbuk Hyundai Motors": "전북",
    "Jeonbuk": "전북",
    "Ulsan HD": "울산",
    "Ulsan": "울산",
    "FC Seoul": "서울",
    "Seoul": "서울",
    "Suwon Samsung Bluewings": "수원",
    "Suwon": "수원",
    "Suwon FC": "수원FC",
    "Pohang Steelers": "포항",
    "Pohang": "포항",
    "Incheon United": "인천",
    "Incheon": "인천",
    "Jeju United": "제주",
    "Jeju": "제주",
    "Daejeon Citizen": "대전",
    "Daejeon": "대전",
    "Gwangju FC": "광주",
    "Gwangju": "광주",
    "Gimcheon Sangmu": "김천",
    "Gimcheon": "김천",
    "Daegu FC": "대구",
    "Daegu": "대구",
    "Gangwon FC": "강원",
    "Gangwon": "강원",
    "Anyang": "안양",
    "FC Anyang": "안양",
    "Seongnam FC": "성남",
    "Seongnam": "성남",
    "Busan IPark": "부산",
    "Busan": "부산",
    "Jeonnam Dragons": "전남",
    "Jeonnam": "전남",
    "Chungnam Asan": "충남아산",
    "Seoul E-Land": "서울이랜드",
    "Bucheon FC 1995": "부천",
    "Gyeongnam FC": "경남",
}

# FotMob 포지션 코드 → 표준 포지션
POSITION_MAP: dict[str | int, str] = {
    # 포지션 문자열
    "G": "GK", "GK": "GK", "Goalkeeper": "GK",
    "D": "DF", "DF": "DF", "Defender": "DF",
    "M": "MF", "MF": "MF", "Midfielder": "MF",
    "F": "FW", "FW": "FW", "Forward": "FW", "Attacker": "FW",
    # 포지션 숫자 코드 (FotMob 내부)
    100: "GK",
    200: "DF", 201: "DF", 202: "DF",
    300: "MF", 301: "MF", 302: "MF", 303: "MF",
    400: "FW", 401: "FW", 402: "FW",
}


def _normalize_team(raw: str) -> str:
    """FotMob 팀명 → 프로젝트 short_name. 매핑 없으면 원문 반환."""
    if not raw:
        return raw
    # 직접 매핑
    if raw in TEAM_NAME_MAP:
        return TEAM_NAME_MAP[raw]
    # 부분 매핑 (포함 여부)
    for key, val in TEAM_NAME_MAP.items():
        if key.lower() in raw.lower() or raw.lower() in key.lower():
            return val
    return raw


def _normalize_position(raw) -> str:
    """FotMob 포지션 → GK/DF/MF/FW."""
    if raw is None:
        return ""
    if isinstance(raw, int):
        return POSITION_MAP.get(raw, "")
    if isinstance(raw, str):
        return POSITION_MAP.get(raw.strip(), raw.strip().upper()[:2])
    return ""


class FotmobCrawler:
    """
    FotMob 비공개 API에서 K리그 라인업 데이터를 수집합니다.

    인증 불필요. Referer + Accept 헤더로 브라우저 흉내.
    요청 간 1~3초 딜레이 적용.
    """

    BASE_URL = "https://www.fotmob.com"
    LEAGUES_API   = f"{BASE_URL}/api/leagues"
    MATCH_API     = f"{BASE_URL}/api/matchDetails"

    def __init__(self, raw_cache_dir: Path) -> None:
        self.raw_cache_dir = raw_cache_dir
        self.raw_cache_dir.mkdir(parents=True, exist_ok=True)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "Referer": "https://www.fotmob.com/",
            "Origin": "https://www.fotmob.com",
        })

    def is_available(self) -> bool:
        try:
            resp = self.session.get(self.BASE_URL, timeout=10)
            return resp.status_code < 400
        except Exception:
            return False

    # ── 공개 메서드 ───────────────────────────────────

    def fetch_available_seasons(self) -> dict[int, str]:
        """
        FotMob K리그1의 사용 가능한 시즌 목록 조회.
        반환: {연도(int): selectedSeason값(str)}
        예: {2025: "61765", 2024: "58765", ...}
        """
        cache_path = self.raw_cache_dir / "fotmob_available_seasons.json"
        if cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        try:
            resp = self._get(self.LEAGUES_API, params={"id": FOTMOB_K1_ID, "ccode3": "KOR"})
            data = resp.json()
        except Exception as e:
            logger.error(f"[FotMob] 시즌 목록 조회 실패: {e}")
            return {}

        seasons: dict[int, str] = {}

        # allAvailableSeasons 또는 seasons 필드에서 시즌 목록 추출
        available = (
            data.get("allAvailableSeasons")
            or data.get("seasons")
            or data.get("tabs", {}).get("seasons")
            or []
        )

        for s in available:
            if not isinstance(s, dict):
                continue
            season_id = str(s.get("id") or s.get("seasonId") or "")
            # 연도 추출: "2025", "2024/2025" 등
            year_raw = str(s.get("year") or s.get("name") or s.get("season") or "")
            # "2024/2025" → 2025, "2025" → 2025
            years_in_name = re.findall(r"\d{4}", year_raw)
            if years_in_name and season_id:
                year = int(years_in_name[-1])  # 마지막 연도 사용
                seasons[year] = season_id

        if seasons:
            cache_path.write_text(json.dumps(seasons, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"[FotMob] 사용 가능한 시즌: {sorted(seasons.keys())}")

        return seasons

    def fetch_season_matches(self, season: int) -> list[dict]:
        """
        K리그1 시즌 전체 경기 목록 반환.
        반환: [{"fotmob_id": int, "date": "YYYY-MM-DD",
                "home": str, "away": str, "finished": bool}]
        """
        cache_path = self.raw_cache_dir / f"fotmob_season_{season}.json"
        if cache_path.exists():
            logger.debug(f"[FotMob] 캐시 사용: {cache_path}")
            return json.loads(cache_path.read_text(encoding="utf-8"))

        # 시즌 ID 조회 후 selectedSeason 파라미터로 요청
        available = self.fetch_available_seasons()
        season_id = available.get(season)

        params: dict = {"id": FOTMOB_K1_ID, "ccode3": "KOR"}
        if season_id:
            params["selectedSeason"] = season_id
            logger.debug(f"[FotMob] {season}시즌 ID: {season_id}")
        else:
            logger.warning(f"[FotMob] {season}시즌 ID 없음 — year 파라미터로 시도")
            params["season"] = str(season)

        try:
            resp = self._get(self.LEAGUES_API, params=params)
            data = resp.json()
            matches = self._parse_season_matches(data)
            cache_path.write_text(json.dumps(matches, ensure_ascii=False, indent=2), encoding="utf-8")
            logger.info(f"[FotMob] 시즌 경기 목록: {len(matches)}경기 ({season})")
            return matches
        except Exception as e:
            logger.error(f"[FotMob] 시즌 경기 목록 수집 실패: {e}")
            return []

    def fetch_match_goal_types(self, fotmob_id: int) -> list[dict]:
        """
        경기 골 이벤트 + 득점 유형 반환.
        matchDetails 캐시 파일을 재사용하므로 추가 API 호출 없음.

        반환: [{"minute": int, "team": str, "player": str,
                "goal_type": "open_play"|"penalty"|"free_kick"|"corner"|"own_goal"}]
        """
        cache_path = self.raw_cache_dir / f"fotmob_match_{fotmob_id}.json"
        if cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            try:
                resp = self._get(self.MATCH_API, params={"matchId": str(fotmob_id)})
                raw = resp.json()
                cache_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"[FotMob] 경기 상세 수집 실패: fotmob_id={fotmob_id} | {e}")
                return []

        return self._parse_goal_events(raw)

    def fetch_match_lineup(self, fotmob_id: int) -> dict:
        """
        경기 상세 정보 → 라인업 + 교체 반환.
        반환: {
            "fotmob_id": int,
            "lineups": {
                "home": {"starters": [...], "bench": [...]},
                "away": {"starters": [...], "bench": [...]}
            },
            "substitutions": [{"minute": int, "team": str,
                               "player_off": str, "player_on": str}]
        }
        """
        cache_path = self.raw_cache_dir / f"fotmob_match_{fotmob_id}.json"
        if cache_path.exists():
            raw = json.loads(cache_path.read_text(encoding="utf-8"))
        else:
            try:
                resp = self._get(self.MATCH_API, params={"matchId": str(fotmob_id)})
                raw = resp.json()
                cache_path.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
            except Exception as e:
                logger.warning(f"[FotMob] 경기 상세 수집 실패: fotmob_id={fotmob_id} | {e}")
                return {"fotmob_id": fotmob_id, "lineups": {}, "substitutions": []}

        return self._parse_lineup(raw, fotmob_id)

    # ── 파싱 메서드 ───────────────────────────────────

    def _parse_goal_events(self, data: dict) -> list[dict]:
        """matchDetails API 응답 → 골 이벤트 + 득점 유형."""
        goals: list[dict] = []

        events_root = (
            data.get("content", {}).get("matchFacts", {}).get("events", {})
            or data.get("content", {}).get("events", {})
            or {}
        )
        events_list = events_root.get("events") or []

        for ev in events_list:
            if not isinstance(ev, dict):
                continue

            ev_type = str(ev.get("type") or "").lower()
            if "goal" not in ev_type:
                continue

            is_own_goal = "own" in ev_type or bool(ev.get("isOwnGoal"))

            # 득점 유형: subEventName 필드로 구분
            sub = str(ev.get("subEventName") or "").strip().lower()
            if is_own_goal:
                goal_type = "own_goal"
            elif "penalty" in sub:
                goal_type = "penalty"
            elif "free" in sub:
                goal_type = "free_kick"
            elif "corner" in sub:
                goal_type = "corner"
            else:
                goal_type = "open_play"

            # 분 추출: time.minute 또는 time 숫자 또는 minute 필드
            time_val = ev.get("time") or {}
            if isinstance(time_val, dict):
                minute = int(time_val.get("minute") or time_val.get("min") or 0)
            else:
                minute = int(time_val or ev.get("minute") or 0)

            # 선수/팀명
            player_raw = ev.get("player") or ev.get("playerName") or {}
            if isinstance(player_raw, dict):
                player = (
                    player_raw.get("name", {}).get("fullName")
                    or player_raw.get("name", {}).get("lastName")
                    or player_raw.get("fullName")
                    or ""
                )
            else:
                player = str(player_raw)

            team = _normalize_team(str(ev.get("teamName") or ev.get("team") or ""))

            goals.append({
                "minute":    minute,
                "team":      team,
                "player":    str(player).strip(),
                "goal_type": goal_type,
            })

        goals.sort(key=lambda g: g["minute"])
        return goals

    def _parse_season_matches(self, data: dict) -> list[dict]:
        """leagues API 응답 → 경기 목록."""
        matches = []

        # FotMob leagues API 응답 구조: data.matches.allMatches 또는 data.allMatches
        all_matches = (
            data.get("matches", {}).get("allMatches")
            or data.get("allMatches")
            or []
        )

        for m in all_matches:
            try:
                fotmob_id = m.get("id")
                if not fotmob_id:
                    continue

                # 날짜: "2025-02-15T10:00:00.000Z" 또는 "20250215"
                status = m.get("status", {})
                date_raw = (
                    status.get("utcTime")
                    or m.get("time", {}).get("utcTime")
                    or m.get("utcTime")
                    or ""
                )
                date_str = self._parse_date(str(date_raw))

                home = _normalize_team(
                    m.get("home", {}).get("name") or m.get("homeTeam", {}).get("name", "")
                )
                away = _normalize_team(
                    m.get("away", {}).get("name") or m.get("awayTeam", {}).get("name", "")
                )
                finished = status.get("finished", False) or status.get("started", False)

                matches.append({
                    "fotmob_id": int(fotmob_id),
                    "date": date_str,
                    "home": home,
                    "away": away,
                    "finished": bool(finished),
                })
            except Exception as e:
                logger.debug(f"[FotMob] 경기 파싱 오류: {e}")
                continue

        return matches

    def _parse_lineup(self, data: dict, fotmob_id: int) -> dict:
        """matchDetails API 응답 → 라인업 + 교체."""
        lineups: dict = {}
        substitutions: list[dict] = []

        # ── 라인업 파싱 ───────────────────────────────
        # 구조 후보 1: data.lineup.lineup[0/1]
        # 구조 후보 2: data.content.lineup
        lineup_root = (
            data.get("lineup")
            or data.get("content", {}).get("lineup")
            or {}
        )

        lineup_list = lineup_root.get("lineup") or []

        # 홈/어웨이 팀 이름 (general.homeTeam / general.awayTeam)
        general = data.get("general", {})
        home_name = _normalize_team(
            general.get("homeTeam", {}).get("name", "")
            or general.get("homeTeamName", "")
        )
        away_name = _normalize_team(
            general.get("awayTeam", {}).get("name", "")
            or general.get("awayTeamName", "")
        )

        for i, team_lu in enumerate(lineup_list[:2]):
            side = "home" if i == 0 else "away"
            team_name = home_name if side == "home" else away_name

            starters, bench = [], []

            # players 필드: [[row0_players], [row1_players], ...] 또는 flat list
            players_raw = team_lu.get("players") or []

            # flat하게 변환
            flat: list[dict] = []
            for row in players_raw:
                if isinstance(row, list):
                    flat.extend(row)
                elif isinstance(row, dict):
                    flat.append(row)

            for p in flat:
                if not isinstance(p, dict):
                    continue
                name = (
                    p.get("name", {}).get("fullName")
                    or p.get("name", {}).get("lastName")
                    or p.get("name")
                    or p.get("playerName")
                    or ""
                )
                if isinstance(name, dict):
                    name = name.get("fullName") or name.get("lastName") or ""
                name = str(name).strip()
                if not name:
                    continue

                pos_raw = (
                    p.get("positionId")
                    or p.get("role")
                    or p.get("position")
                    or ""
                )
                position = _normalize_position(pos_raw)
                jersey = p.get("shirt") or p.get("jerseyNumber") or p.get("shirtNumber")

                entry = {
                    "player": name,
                    "team":   team_name,
                    "position": position,
                    "jersey": jersey,
                }

                is_starter = p.get("isHomeTeam") is not None  # 모든 선수가 포함됨
                # FotMob: usedPlayerIds 또는 lineup[].players에 선발/벤치 구분 있음
                role = str(p.get("role") or "").lower()
                if "sub" in role or p.get("isSub") or p.get("isSubstitute"):
                    bench.append(entry)
                else:
                    starters.append(entry)

            # 선발 없으면 전원 선발로 처리 (첫 11명)
            if not starters and flat:
                all_entries = []
                for p in flat:
                    if not isinstance(p, dict):
                        continue
                    name = (
                        p.get("name", {}).get("fullName")
                        or p.get("name", {}).get("lastName")
                        or p.get("name") or p.get("playerName") or ""
                    )
                    if isinstance(name, dict):
                        name = name.get("fullName") or name.get("lastName") or ""
                    name = str(name).strip()
                    if not name:
                        continue
                    pos_raw = p.get("positionId") or p.get("role") or p.get("position") or ""
                    position = _normalize_position(pos_raw)
                    jersey = p.get("shirt") or p.get("jerseyNumber")
                    all_entries.append({"player": name, "team": team_name,
                                        "position": position, "jersey": jersey})
                starters = all_entries[:11]
                bench    = all_entries[11:]

            if starters or bench:
                lineups[side] = {"starters": starters, "bench": bench}

        # ── 교체 파싱 ─────────────────────────────────
        # content.events.substitutions 또는 content.matchFacts.events
        events_root = (
            data.get("content", {}).get("matchFacts", {}).get("events", {})
            or data.get("content", {}).get("events", {})
            or {}
        )
        events_list = events_root.get("events") or events_root.get("substitutions") or []

        for ev in events_list:
            if not isinstance(ev, dict):
                continue
            ev_type = str(ev.get("type") or "").lower()
            if "sub" not in ev_type:
                continue
            try:
                minute = int(ev.get("time") or ev.get("minute") or 0)
                team   = _normalize_team(ev.get("teamName") or ev.get("team") or "")
                player_off = (
                    ev.get("swap", {}).get("playerOut", {}).get("name", {}).get("fullName")
                    or ev.get("playerOut") or ev.get("playerOff") or ""
                )
                player_on  = (
                    ev.get("swap", {}).get("playerIn", {}).get("name", {}).get("fullName")
                    or ev.get("playerIn") or ev.get("playerOn") or ""
                )
                if isinstance(player_off, dict):
                    player_off = player_off.get("fullName") or ""
                if isinstance(player_on, dict):
                    player_on  = player_on.get("fullName") or ""
                substitutions.append({
                    "minute":     minute,
                    "team":       team,
                    "player_off": str(player_off).strip(),
                    "player_on":  str(player_on).strip(),
                })
            except Exception:
                continue

        substitutions.sort(key=lambda s: s["minute"])

        return {
            "fotmob_id":     fotmob_id,
            "lineups":       lineups,
            "substitutions": substitutions,
        }

    # ── 내부 유틸 ─────────────────────────────────────

    def _get(self, url: str, params: dict | None = None) -> requests.Response:
        import random
        time.sleep(random.uniform(1.0, 2.5))
        resp = self.session.get(url, params=params, timeout=15)
        resp.raise_for_status()
        return resp

    @staticmethod
    def _parse_date(raw: str) -> str:
        """ISO 날짜 문자열 → YYYY.MM.DD."""
        if not raw:
            return ""
        m = re.search(r"(\d{4})-(\d{2})-(\d{2})", raw)
        if m:
            return f"{m.group(1)}.{m.group(2)}.{m.group(3)}"
        m2 = re.search(r"(\d{4})(\d{2})(\d{2})", raw)
        if m2:
            return f"{m2.group(1)}.{m2.group(2)}.{m2.group(3)}"
        return raw
