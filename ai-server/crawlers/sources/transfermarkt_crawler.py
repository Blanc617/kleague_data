"""
Transfermarkt 크롤러.
선수 시장가치, 이적 이력, 상세 프로필 수집에 특화됩니다.
차단 리스크: 중간 (UA 로테이션 + 딜레이로 대응).
"""

from pathlib import Path
from typing import Literal

from bs4 import BeautifulSoup
from loguru import logger

from crawlers.base.base_crawler import BaseCrawler
from crawlers.config.settings import SOURCE_CONFIGS
from crawlers.config.teams import K1_TEAMS, K2_TEAMS, TeamMeta


class TransfermarktCrawler(BaseCrawler):
    """
    Transfermarkt에서 선수 시장가치, 이적 이력, 부상 기록 수집.

    차단 대응:
    - fake_useragent로 매 요청마다 UA 로테이션
    - 요청 간 3~6초 딜레이
    - Accept-Language: ko-KR 헤더
    - requests.Session 유지 (쿠키 자동 처리)
    """

    BASE_URL = "https://www.transfermarkt.com"

    # K리그 리그 코드
    LEAGUE_CODES = {"K1": "RSL", "K2": "RSL2"}

    def __init__(self, raw_cache_dir: Path) -> None:
        super().__init__(SOURCE_CONFIGS["transfermarkt"], raw_cache_dir)
        self._extra_headers = {
            "Referer": "https://www.transfermarkt.com/",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        }

    def is_available(self) -> bool:
        return self.http.health_check(self.BASE_URL)

    # ── BaseCrawler 추상 메서드 구현 ──────────────────

    def crawl_players(self, league: Literal["K1", "K2"]) -> list[dict]:
        """
        K리그1 또는 K리그2 전체 선수 명단 수집.
        팀 페이지(/kader/)를 순회하며 선수 목록을 추출합니다.
        """
        logger.info(f"[Transfermarkt] 선수 명단 수집 시작: {league}")
        teams = K1_TEAMS if league == "K1" else K2_TEAMS
        all_players = []

        for team in teams:
            logger.info(f"  └─ {team.name_ko}")
            players = self._crawl_team_squad(team)
            all_players.extend(players)
            logger.info(f"     수집: {len(players)}명")

        logger.info(f"[Transfermarkt] {league} 총 {len(all_players)}명 수집 완료")
        return all_players

    def crawl_player_stats(
        self, player_id: str, seasons: list[int]
    ) -> list[dict]:
        """
        선수 ID로 시즌별 개인 기록 수집.
        player_id 형식: "{tm_player_id}_{player_slug}"
        """
        parts = player_id.split("_", 1)
        if len(parts) < 2:
            logger.warning(f"[Transfermarkt] 잘못된 player_id: {player_id}")
            return []

        tm_id, slug = parts[0], parts[1]
        url = f"{self.BASE_URL}/{slug}/leistungsdatendetails/spieler/{tm_id}"

        try:
            html = self._get_html(url, extra_headers=self._extra_headers)
            return self._parse_player_stats(html, player_id, seasons)
        except Exception as e:
            logger.error(f"[Transfermarkt] 기록 수집 실패: {player_id} | {e}")
            return []

    def crawl_team_results(self, team_name: str, season: int) -> list[dict]:
        """
        팀 경기 결과 수집 (Transfermarkt은 상세 결과보다 통계 위주).
        kleague.com 차단 시 폴백으로 사용됩니다.
        """
        team = self._find_team(team_name)
        if not team:
            logger.warning(f"[Transfermarkt] 팀 메타 없음: {team_name}")
            return []

        url = (
            f"{self.BASE_URL}/{team.transfermarkt_slug}"
            f"/spielplandatum/verein/{team.transfermarkt_id}"
            f"/saison_id/{season}"
        )

        try:
            html = self._get_html(url, extra_headers=self._extra_headers)
            return self._parse_match_results(html, team_name, season)
        except Exception as e:
            logger.error(f"[Transfermarkt] 경기 결과 수집 실패: {team_name} {season} | {e}")
            return []

    # ── Transfermarkt 전용 메서드 ─────────────────────

    def crawl_transfer_history(self, tm_player_id: str, slug: str) -> list[dict]:
        """선수 이적 이력 수집."""
        url = f"{self.BASE_URL}/{slug}/transfers/spieler/{tm_player_id}"

        try:
            html = self._get_html(url, extra_headers=self._extra_headers)
            return self._parse_transfer_history(html)
        except Exception as e:
            logger.error(f"[Transfermarkt] 이적 이력 수집 실패: {tm_player_id} | {e}")
            return []

    # ── 파싱 메서드 ───────────────────────────────────

    def _crawl_team_squad(self, team: TeamMeta) -> list[dict]:
        """팀 선수단 페이지(/kader/) 파싱."""
        url = (
            f"{self.BASE_URL}/{team.transfermarkt_slug}"
            f"/kader/verein/{team.transfermarkt_id}"
        )

        try:
            html = self._get_html(url, extra_headers=self._extra_headers)
            return self._parse_squad_table(html, team)
        except Exception as e:
            logger.error(f"[Transfermarkt] 선수단 수집 실패: {team.name_ko} | {e}")
            return []

    def _parse_squad_table(self, html: str, team: TeamMeta) -> list[dict]:
        """선수단 테이블 HTML 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        players = []

        # Transfermarkt 선수 행: <tr class="odd">/<tr class="even">
        rows = soup.select("table.items tbody tr")

        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            try:
                # 등번호
                jersey = cols[0].get_text(strip=True) or ""

                # 선수 이름 + TM ID (링크에서 추출)
                name_td = row.select_one("td.hauptlink a")
                if not name_td:
                    continue
                name = name_td.get_text(strip=True)
                href = name_td.get("href", "")
                tm_id = href.split("/")[-1] if href else ""
                slug = href.split("/")[1] if len(href.split("/")) > 1 else ""

                # 포지션
                pos_td = row.select_one("td.posrela table td")
                position = pos_td.get_text(strip=True) if pos_td else ""

                # 생년월일 / 나이
                birth_td = cols[2] if len(cols) > 2 else None
                birth_text = birth_td.get_text(strip=True) if birth_td else ""

                # 국적 (국기 이미지 alt 텍스트)
                nationality_img = row.select_one("td.zentriert img.flaggenrahmen")
                nationality = (
                    nationality_img.get("title", "") if nationality_img else ""
                )

                # 신장
                height_td = cols[5] if len(cols) > 5 else None
                height = height_td.get_text(strip=True) if height_td else ""

                # 시장가치
                value_td = row.select_one("td.rechts.hauptlink")
                market_value_raw = value_td.get_text(strip=True) if value_td else ""

                players.append({
                    "player_id": f"{tm_id}_{slug}" if tm_id else "",
                    "name_ko": name,
                    "name_en": name,
                    "team": team.name_ko,
                    "league": "K1" if team in K1_TEAMS else "K2",
                    "jersey_number": jersey,
                    "position": position,
                    "nationality": nationality,
                    "birth_text": birth_text,
                    "height_raw": height,
                    "market_value_raw": market_value_raw,
                    "transfermarkt_id": tm_id,
                    "transfermarkt_slug": slug,
                    "source": "transfermarkt",
                })
            except Exception as e:
                logger.debug(f"행 파싱 오류 (무시): {e}")
                continue

        return players

    def _parse_player_stats(
        self, html: str, player_id: str, seasons: list[int]
    ) -> list[dict]:
        """선수 기록 페이지 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        rows = soup.select("table.items tbody tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 8:
                continue

            try:
                season_text = cols[0].get_text(strip=True)
                # 시즌 연도 추출 (예: "24/25" → 2024)
                season_year = self._parse_season_year(season_text)
                if season_year not in seasons:
                    continue

                results.append({
                    "player_id": player_id,
                    "season": season_year,
                    "competition": cols[1].get_text(strip=True),
                    "appearances": self._safe_int(cols[3].get_text(strip=True)),
                    "goals": self._safe_int(cols[4].get_text(strip=True)),
                    "assists": self._safe_int(cols[5].get_text(strip=True)),
                    "yellow_cards": self._safe_int(cols[6].get_text(strip=True)),
                    "red_cards": self._safe_int(cols[7].get_text(strip=True)),
                    "source": "transfermarkt",
                })
            except Exception as e:
                logger.debug(f"기록 파싱 오류 (무시): {e}")
                continue

        return results

    def _parse_match_results(
        self, html: str, team_name: str, season: int
    ) -> list[dict]:
        """팀 경기 일정/결과 페이지 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        results = []

        rows = soup.select("table.items tbody tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 7:
                continue

            try:
                date_text = cols[1].get_text(strip=True)
                home_team = cols[3].get_text(strip=True)
                away_team = cols[5].get_text(strip=True)
                score_td = cols[6].get_text(strip=True)

                results.append({
                    "season": season,
                    "date": date_text,
                    "home_team": home_team,
                    "away_team": away_team,
                    "score": score_td,
                    "source": "transfermarkt",
                })
            except Exception:
                continue

        return results

    def _parse_transfer_history(self, html: str) -> list[dict]:
        """이적 이력 페이지 파싱."""
        soup = BeautifulSoup(html, "html.parser")
        transfers = []

        rows = soup.select("div#yw1 table.items tbody tr")
        for row in rows:
            cols = row.find_all("td")
            if len(cols) < 5:
                continue

            try:
                transfers.append({
                    "season": cols[0].get_text(strip=True),
                    "date": cols[1].get_text(strip=True),
                    "from_club": cols[2].get_text(strip=True),
                    "to_club": cols[4].get_text(strip=True),
                    "fee": cols[5].get_text(strip=True) if len(cols) > 5 else "",
                    "source": "transfermarkt",
                })
            except Exception:
                continue

        return transfers

    # ── 유틸리티 ──────────────────────────────────────

    def _find_team(self, team_name: str) -> TeamMeta | None:
        for t in K1_TEAMS + K2_TEAMS:
            if t.name_ko == team_name or t.short_name == team_name:
                return t
        return None

    def _parse_season_year(self, text: str) -> int:
        """
        "24/25" → 2024, "2024" → 2024 형태로 변환.
        """
        text = text.strip()
        if "/" in text:
            parts = text.split("/")
            year_part = parts[0].strip()
            if len(year_part) == 2:
                return 2000 + int(year_part)
            return int(year_part)
        if len(text) == 4 and text.isdigit():
            return int(text)
        return 0

    def _safe_int(self, text: str) -> int:
        """숫자가 아닌 텍스트 안전 변환."""
        cleaned = text.strip().replace("-", "0").replace(".", "")
        return int(cleaned) if cleaned.isdigit() else 0
