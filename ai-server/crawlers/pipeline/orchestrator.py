"""
전체 데이터 수집 파이프라인 오케스트레이터.
소스 가용성 체크 → 우선순위 기반 크롤러 선택 → 수집 → 저장.
하나의 소스 실패가 전체를 중단시키지 않습니다.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from crawlers.base.base_crawler import BaseCrawler
from crawlers.config.settings import TARGET_SEASONS
from crawlers.config.teams import ALL_TEAMS, DERBY_FIXTURES, K1_TEAMS, K2_TEAMS
from crawlers.sources.kleague_crawler import KleagueCrawler
from crawlers.sources.naver_sports_crawler import NaverSportsCrawler
from crawlers.sources.transfermarkt_crawler import TransfermarktCrawler
from crawlers.sources.wikipedia_crawler import WikipediaCrawler


@dataclass
class CrawlReport:
    started_at: str
    finished_at: str = ""
    phases: dict[str, dict] = field(default_factory=dict)
    total_records: int = 0
    total_failures: int = 0
    saved_files: list[str] = field(default_factory=list)


class CrawlOrchestrator:
    """
    Day 1 전체 데이터 수집 파이프라인.

    실행 전략:
    1. 소스 가용성 사전 체크
    2. 소스별 우선순위에 따라 크롤러 선택
    3. 수집 → 저장
    4. 부분 실패 허용
    """

    # 데이터 타입별 소스 우선순위
    SOURCE_PRIORITY = {
        "players":       ["kleague", "transfermarkt", "wikipedia"],
        "player_stats":  ["kleague", "transfermarkt"],
        "team_results":  ["kleague", "wikipedia"],
        "derby_records": ["wikipedia"],
        "articles":      ["naver"],
        "standings":     ["kleague"],
    }

    def __init__(self, base_dir: Path, dry_run: bool = False) -> None:
        self.base_dir = base_dir
        self.dry_run = dry_run
        self.raw_dir = base_dir / "data" / "raw"
        self.processed_dir = base_dir / "data" / "processed"

        # 크롤러 인스턴스
        self.crawlers: dict[str, BaseCrawler] = {
            "kleague": KleagueCrawler(self.raw_dir / "kleague"),
            "transfermarkt": TransfermarktCrawler(self.raw_dir / "transfermarkt"),
            "wikipedia": WikipediaCrawler(self.raw_dir / "wikipedia"),
            "naver": NaverSportsCrawler(self.raw_dir / "naver"),
        }

    def run(
        self,
        leagues: list[Literal["K1", "K2"]] | None = None,
        seasons: list[int] | None = None,
        phases: list[str] | None = None,
    ) -> CrawlReport:
        """
        전체 수집 파이프라인 실행.

        Args:
            leagues: 수집할 리그 목록. None이면 K1, K2 모두.
            seasons: 수집할 시즌 목록. None이면 TARGET_SEASONS.
            phases: 실행할 페이즈 목록. None이면 전체.
        """
        leagues = leagues or ["K1", "K2"]
        seasons = seasons or TARGET_SEASONS
        phases = phases or ["players", "player_stats", "team_results", "derby", "articles", "standings"]

        report = CrawlReport(started_at=datetime.now().isoformat())
        logger.info("=" * 60)
        logger.info("K리그 데이터 수집 시작")
        logger.info(f"  리그: {leagues} | 시즌: {seasons}")
        logger.info(f"  페이즈: {phases}")
        if self.dry_run:
            logger.warning("  [DRY RUN 모드 — 파일 저장 안 함]")
        logger.info("=" * 60)

        # Phase 0: 소스 가용성 체크
        available = self._check_availability()
        logger.info(f"소스 가용성: {available}")

        # Phase 1: 선수 명단
        if "players" in phases:
            self._run_players_phase(leagues, available, report)

        # Phase 2: 개인 기록
        if "player_stats" in phases:
            self._run_player_stats_phase(leagues, seasons, available, report)

        # Phase 3: 팀 경기 결과
        if "team_results" in phases:
            self._run_team_results_phase(leagues, seasons, available, report)

        # Phase 4: 더비 전적
        if "derby" in phases:
            self._run_derby_phase(available, report)

        # Phase 5: 인터뷰 기사
        if "articles" in phases:
            self._run_articles_phase(available, report)

        # Phase 6: 리그 순위
        if "standings" in phases:
            self._run_standings_phase(leagues, seasons, available, report)

        report.finished_at = datetime.now().isoformat()
        self._save_report(report)

        logger.info("=" * 60)
        logger.info(f"수집 완료 | 총 {report.total_records}건 | 실패 {report.total_failures}건")
        logger.info(f"소요 시간: {report.started_at} → {report.finished_at}")
        logger.info("=" * 60)

        return report

    # ── Phase 실행 메서드 ──────────────────────────────

    def _run_players_phase(
        self,
        leagues: list[str],
        available: dict[str, bool],
        report: CrawlReport,
    ) -> None:
        logger.info("\n[Phase 1] 선수 명단 수집")
        for league in leagues:
            crawler = self._select_crawler("players", available)
            if not crawler:
                logger.error(f"[Phase 1] 가용 크롤러 없음: {league}")
                report.total_failures += 1
                continue

            try:
                players = crawler.crawl_players(league)
                out_path = self.processed_dir / "players" / f"{league.lower()}_players.json"
                count = self._save(players, out_path, report)
                report.phases[f"players_{league}"] = {"count": count, "source": type(crawler).__name__}
            except Exception as e:
                logger.error(f"[Phase 1] 실패: {league} | {e}")
                report.total_failures += 1

    def _run_player_stats_phase(
        self,
        leagues: list[str],
        seasons: list[int],
        available: dict[str, bool],
        report: CrawlReport,
    ) -> None:
        logger.info("\n[Phase 2] 선수 개인 기록 수집")
        crawler = self._select_crawler("player_stats", available)
        if not crawler:
            logger.error("[Phase 2] 가용 크롤러 없음")
            report.total_failures += 1
            return

        for season in seasons:
            all_stats = []
            teams = []
            for league in leagues:
                teams += K1_TEAMS if league == "K1" else K2_TEAMS

            # 팀별 선수 기록 수집 (kleague는 전체 통계 페이지 사용)
            try:
                if isinstance(crawler, KleagueCrawler):
                    for league in leagues:
                        league_id = KleagueCrawler.LEAGUE_IDS[league]
                        stats = crawler.crawl_player_stats("all", [season])
                        all_stats.extend(stats)
                elif isinstance(crawler, TransfermarktCrawler):
                    # Transfermarkt은 개별 선수 ID가 필요 → 명단 파일에서 읽음
                    all_stats = self._crawl_stats_from_roster(
                        crawler, leagues, season
                    )
            except Exception as e:
                logger.error(f"[Phase 2] 실패: season={season} | {e}")
                report.total_failures += 1
                continue

            out_path = self.processed_dir / "stats" / f"player_stats_{season}.json"
            count = self._save(all_stats, out_path, report)
            report.phases[f"stats_{season}"] = {"count": count, "source": type(crawler).__name__}

    def _run_team_results_phase(
        self,
        leagues: list[str],
        seasons: list[int],
        available: dict[str, bool],
        report: CrawlReport,
    ) -> None:
        logger.info("\n[Phase 3] 팀 경기 결과 수집")
        crawler = self._select_crawler("team_results", available)
        if not crawler:
            logger.error("[Phase 3] 가용 크롤러 없음")
            report.total_failures += 1
            return

        for league in leagues:
            teams = K1_TEAMS if league == "K1" else K2_TEAMS
            out_path = self.processed_dir / "teams" / f"{league.lower()}_team_results.json"

            # 기존 데이터 로드 (덮어쓰기 방지 — 새로 크롤링한 시즌만 교체)
            existing_by_key: dict[tuple, dict] = {}
            if out_path.exists():
                try:
                    import json as _json
                    existing = _json.loads(out_path.read_text(encoding="utf-8"))
                    for r in existing:
                        key = (r.get("season"), r.get("game_id"))
                        existing_by_key[key] = r
                except Exception:
                    pass

            for team in teams:
                for season in seasons:
                    try:
                        results = crawler.crawl_team_results(team.name_ko, season)
                        for r in results:
                            key = (r.get("season"), r.get("game_id"))
                            existing_by_key[key] = r
                        logger.info(f"  └─ {team.name_ko} {season}: {len(results)}경기")
                    except Exception as e:
                        logger.warning(f"  └─ {team.name_ko} {season} 실패: {e}")
                        report.total_failures += 1

            all_results = sorted(
                existing_by_key.values(),
                key=lambda r: (r.get("season", 0), r.get("date", "")),
            )
            count = self._save(list(all_results), out_path, report)
            report.phases[f"results_{league}"] = {"count": count}

    def _run_derby_phase(
        self,
        available: dict[str, bool],
        report: CrawlReport,
    ) -> None:
        logger.info("\n[Phase 4] 더비 전적 수집")
        crawler = self._select_crawler("derby_records", available)
        if not crawler or not isinstance(crawler, WikipediaCrawler):
            logger.error("[Phase 4] Wikipedia 크롤러 필요")
            report.total_failures += 1
            return

        for derby in DERBY_FIXTURES:
            try:
                data = crawler.crawl_derby_records(derby)
                name_slug = derby.name.replace(" ", "_")
                out_path = self.processed_dir / "derby" / f"{name_slug}.json"
                self._save([data], out_path, report)
                report.phases[f"derby_{derby.name}"] = {"matches": data.get("total_matches", 0)}
            except Exception as e:
                logger.error(f"[Phase 4] 더비 수집 실패: {derby.name} | {e}")
                report.total_failures += 1

    def _run_articles_phase(
        self,
        available: dict[str, bool],
        report: CrawlReport,
    ) -> None:
        logger.info("\n[Phase 5] 인터뷰 기사 수집")
        if not available.get("naver"):
            logger.warning("[Phase 5] Naver 비가용 → 기사 수집 건너뜀")
            return

        crawler: NaverSportsCrawler = self.crawlers["naver"]
        all_articles = []

        # 각 팀 주요 선수 이름으로 검색 (팀당 최대 3명)
        # 실제 주요 선수 목록은 선수 명단 수집 후 확보 가능
        # 여기서는 팀 이름으로 뉴스 수집
        for team in ALL_TEAMS[:10]:  # 빠른 데모용: 10팀만
            try:
                articles = crawler.crawl_team_news(team.name_ko, days_back=60)
                all_articles.extend(articles)
                logger.info(f"  └─ {team.name_ko}: {len(articles)}건")
            except Exception as e:
                logger.warning(f"  └─ {team.name_ko} 기사 수집 실패: {e}")

        out_path = self.processed_dir / "articles" / "team_news.json"
        count = self._save(all_articles, out_path, report)
        report.phases["articles"] = {"count": count}

    def _run_standings_phase(
        self,
        leagues: list[str],
        seasons: list[int],
        available: dict[str, bool],
        report: CrawlReport,
    ) -> None:
        logger.info("\n[Phase 6] 리그 순위 수집")
        if not available.get("kleague"):
            logger.warning("[Phase 6] Kleague 비가용 → 순위 수집 건너뜀")
            return

        crawler: KleagueCrawler = self.crawlers["kleague"]
        all_standings = []

        for league in leagues:
            for season in seasons:
                try:
                    standings = crawler.crawl_standings(league, season)
                    all_standings.extend(standings)
                    logger.info(f"  └─ {league} {season}: {len(standings)}팀")
                except Exception as e:
                    logger.warning(f"  └─ {league} {season} 순위 실패: {e}")

        out_path = self.processed_dir / "teams" / "standings.json"
        self._save(all_standings, out_path, report)

    # ── 유틸리티 ──────────────────────────────────────

    def _check_availability(self) -> dict[str, bool]:
        """각 소스 헬스체크."""
        logger.info("\n[Phase 0] 소스 가용성 체크")
        result = {}
        for name, crawler in self.crawlers.items():
            ok = crawler.is_available()
            result[name] = ok
            status = "✓" if ok else "✗"
            logger.info(f"  {status} {name}")
        return result

    def _select_crawler(
        self, data_type: str, available: dict[str, bool]
    ) -> BaseCrawler | None:
        """SOURCE_PRIORITY 기준으로 가용한 첫 번째 크롤러 반환."""
        for source in self.SOURCE_PRIORITY.get(data_type, []):
            if available.get(source):
                return self.crawlers[source]
        return None

    def _crawl_stats_from_roster(
        self,
        crawler: TransfermarktCrawler,
        leagues: list[str],
        season: int,
    ) -> list[dict]:
        """선수 명단 파일에서 player_id를 읽어 기록 수집."""
        all_stats = []
        for league in leagues:
            roster_path = self.processed_dir / "players" / f"{league.lower()}_players.json"
            if not roster_path.exists():
                logger.warning(f"명단 파일 없음: {roster_path}")
                continue

            players = json.loads(roster_path.read_text(encoding="utf-8"))
            for p in players:
                pid = p.get("player_id", "")
                if not pid:
                    continue
                stats = crawler.crawl_player_stats(pid, [season])
                all_stats.extend(stats)

        return all_stats

    def _save(
        self,
        data: list[dict],
        path: Path,
        report: CrawlReport,
    ) -> int:
        """JSON 파일 저장. dry_run이면 저장 없이 카운트만 반환."""
        count = len(data)
        report.total_records += count

        if self.dry_run:
            logger.info(f"  [DRY RUN] {path.name}: {count}건")
            return count

        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        report.saved_files.append(str(path))
        logger.info(f"  저장: {path.name} ({count}건)")
        return count

    def _save_report(self, report: CrawlReport) -> None:
        """수집 보고서 저장."""
        report_path = self.base_dir / "logs" / f"crawl_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)

        report_data = {
            "started_at": report.started_at,
            "finished_at": report.finished_at,
            "total_records": report.total_records,
            "total_failures": report.total_failures,
            "phases": report.phases,
            "saved_files": report.saved_files,
        }
        report_path.write_text(
            json.dumps(report_data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"보고서 저장: {report_path.name}")
