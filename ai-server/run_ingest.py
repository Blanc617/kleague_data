"""
Day 2 인제스트 CLI 진입점.
수집된 JSON 데이터를 청킹 → 임베딩 → Supabase pgvector에 인덱싱합니다.

사용법:
    python run_ingest.py                          # 전체 인제스트
    python run_ingest.py --clear                  # 기존 데이터 삭제 후 재인제스트
    python run_ingest.py --dry-run                # 저장 없이 Document 수만 확인
    python run_ingest.py --init-db                # Supabase 스키마 SQL 출력
    python run_ingest.py --query "전북 최근 경기"  # RAG 쿼리 테스트
    python run_ingest.py --stats "전북"           # 팀 시즌 통계 직접 계산 (RAG 우회)
"""

import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv
from loguru import logger

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT))

load_dotenv(ROOT / ".env")


def cmd_ingest(clear: bool = False, dry_run: bool = False) -> None:
    """데이터 로드 → 청킹 → 인제스트."""
    from rag.chunker import MatchDocumentChunker
    from rag.document_loader import KLeagueDocumentLoader
    if not dry_run:
        from rag.vector_store import VectorStoreManager

    loader = KLeagueDocumentLoader()
    chunker = MatchDocumentChunker()
    all_docs = []

    k1_path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    if k1_path.exists():
        docs = loader.load_from_file(k1_path)
        all_docs.extend(docs)
        logger.info(f"K1 결과: {len(docs)}개 Document")
    else:
        logger.warning(f"K1 결과 파일 없음: {k1_path}")

    k2_path = ROOT / "data" / "processed" / "teams" / "k2_team_results.json"
    if k2_path.exists():
        docs = loader.load_from_file(k2_path)
        all_docs.extend(docs)
        logger.info(f"K2 결과: {len(docs)}개 Document")

    if not all_docs:
        logger.error("로드된 Document 없음. 먼저 크롤러를 실행하세요.")
        sys.exit(1)

    chunked = chunker.chunk(all_docs)
    logger.info(f"총 {len(chunked)}개 청크 준비 완료")

    if dry_run:
        logger.info("[DRY RUN] 인제스트 건너뜀")
        return

    vsm = VectorStoreManager()
    count = vsm.ingest(chunked, clear_existing=clear)
    total_in_db = vsm.count()
    logger.info(f"인제스트 완료: {count}개 추가, DB 전체 {total_in_db}개")


def cmd_init_db() -> None:
    """Supabase 스키마 SQL을 출력합니다."""
    sql_path = ROOT / "rag" / "supabase_schema.sql"
    print(sql_path.read_text(encoding="utf-8"))


def _detect_teams(question: str) -> list[str]:
    """질문에서 팀 키워드를 감지하고, JSON의 팀명과 매칭되는 단축명을 반환합니다."""
    from crawlers.config.teams import ALL_TEAMS
    found = []
    for team in ALL_TEAMS:
        if team.short_name in question or team.name_ko in question:
            if team.short_name not in found:
                found.append(team.short_name)
    return found


def _load_records(season: int | None = None) -> list[dict]:
    """k1_team_results.json을 로드합니다."""
    path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    if not path.exists():
        return []
    records = json.loads(path.read_text(encoding="utf-8"))
    if season:
        records = [r for r in records if r.get("season") == season]
    return records


def cmd_query(question: str) -> None:
    """
    쿼리 라우터.

    1단계 — QueryClassifier로 질문 유형 분류 (LLM 없이 regex)
    2단계 — 구조적 쿼리: MatchDataEngine으로 JSON 직접 조회 → 정확한 컨텍스트 생성
             서사형 쿼리: 기존 RAG 파이프라인 사용
    3단계 — LLM은 컨텍스트를 포맷/요약할 뿐, 데이터를 생성하지 않음

    이 구조를 통해 "FC서울 전반 15분 이전 득점 경기" 같은 사실형 질문에서
    할루시네이션이 발생하지 않습니다.
    """
    import os
    from langchain_core.output_parsers import StrOutputParser
    from langchain_core.prompts import ChatPromptTemplate
    from langchain_openai import ChatOpenAI
    from rag.pipeline import SYSTEM_PROMPT, HUMAN_PROMPT
    from data_engine.match_data_engine import MatchDataEngine
    from data_engine.query_classifier import QueryClassifier, QueryType
    from data_engine import result_formatter as fmt

    clf = QueryClassifier()
    classified = clf.classify(question)
    qtype = classified.query_type
    params = classified.params

    logger.info(f"질문 분류: {qtype.value}  params={params}")

    # ── 구조적 쿼리: JSON 직접 조회 ──────────────────────────────────────
    context: str | None = None

    if qtype == QueryType.EARLY_GOAL:
        engine = MatchDataEngine().load()
        team = params.get("team")
        max_minute = params.get("max_minute", 15)
        half = params.get("half", "전반")
        season = params.get("season")
        if not team:
            print("[오류] 팀 이름을 인식하지 못했습니다. 예: 'FC서울이 전반 15분 이전에 득점한 경기'")
            return
        results = engine.get_games_with_early_goal(team, max_minute, half, season)
        context = fmt.format_early_goal_results(results, team, max_minute, half)
        logger.info(f"구조적 쿼리: {team} {half} {max_minute}분 이전 득점 경기 {len(results)}건")

    elif qtype == QueryType.LATE_GOAL:
        engine = MatchDataEngine().load()
        team = params.get("team")
        min_minute = params.get("min_minute", 80)
        half = params.get("half", "후반")
        season = params.get("season")
        if not team:
            print("[오류] 팀 이름을 인식하지 못했습니다.")
            return
        # 후반 X분 이후 = minute >= 45 + min_minute (또는 전체 기준 min_minute)
        results_raw = engine.get_games_with_early_goal(team, 999, "전체", season)
        results = [
            r for r in results_raw
            if any(g.minute >= min_minute for g in r["goals"] if team in g.team)
        ]
        context = fmt.format_early_goal_results(results, team, min_minute, f"{half} {min_minute}분 이후")

    elif qtype == QueryType.HEAD_TO_HEAD:
        engine = MatchDataEngine().load()
        t1 = params.get("team1", "")
        t2 = params.get("team2", "")
        season = params.get("season")
        results = engine.get_head_to_head(t1, t2, season)
        context = fmt.format_head_to_head(results, t1, t2, season)

    elif qtype == QueryType.TEAM_STATS or qtype == QueryType.TEAM_RESULTS:
        engine = MatchDataEngine().load()
        team = params.get("team")
        season = params.get("season")
        if not team:
            # 팀 없으면 RAG로 fallback
            qtype = QueryType.NARRATIVE
        else:
            results = engine.get_team_results(team, season)
            context = fmt.format_team_results(results, team, season)

    elif qtype == QueryType.TOP_SCORERS:
        engine = MatchDataEngine().load()
        season = params.get("season")
        n = params.get("n", 10)
        stats = engine.get_top_scorers(season, n)
        context = fmt.format_top_scorers(stats, season)

    # ── 구조적 쿼리 결과가 있으면 LLM으로 포맷만 하고 반환 ───────────────
    if context is not None:
        prompt = ChatPromptTemplate.from_messages([
            ("system", SYSTEM_PROMPT),
            ("human", HUMAN_PROMPT),
        ])
        llm = ChatOpenAI(
            model="gpt-4o-mini",
            temperature=0.0,  # 포맷 전용 → 창의성 0
            streaming=True,
            openai_api_key=os.environ["OPENAI_API_KEY"],
        )
        chain = prompt | llm | StrOutputParser()
        logger.info("=" * 60)
        print("\n[답변]")
        for chunk in chain.stream({"context": context, "question": question}):
            print(chunk, end="", flush=True)
        print("\n")
        print(f"[데이터 출처: JSON 직접 조회 / 유형: {qtype.value}]")
        return

    # ── 서사형 쿼리: RAG 파이프라인 ─────────────────────────────────────
    logger.info("서사형 쿼리 → RAG 파이프라인 사용")

    # 팀 이름이 있으면 해당 팀 경기를 컨텍스트에 추가해 RAG 보강
    teams = _detect_teams(question)
    records = _load_records()

    if teams:
        seen_ids: set = set()
        unique_records = []
        for r in records:
            gid = r.get("game_id")
            if gid not in seen_ids:
                seen_ids.add(gid)
                unique_records.append(r)

        if len(teams) >= 2:
            t1, t2 = teams[0], teams[1]
            matched = [
                r for r in unique_records
                if (t1 in r.get("home_team", "") and t2 in r.get("away_team", ""))
                or (t2 in r.get("home_team", "") and t1 in r.get("away_team", ""))
            ]
        else:
            t = teams[0]
            matched = [
                r for r in unique_records
                if t in r.get("home_team", "") or t in r.get("away_team", "")
            ]

        matched.sort(key=lambda r: r.get("date", ""))

        if matched:
            lines = []
            for r in matched:
                lines.append(
                    f"{r['date']} {r.get('competition','K리그')} {r['round']}라운드: "
                    f"{r['home_team']} {r['home_score']}-{r['away_score']} {r['away_team']}"
                )
            rag_context = "\n".join(lines)
            logger.info(f"팀 감지: {teams} → {len(matched)}경기 컨텍스트 구성")

            prompt = ChatPromptTemplate.from_messages([
                ("system", SYSTEM_PROMPT),
                ("human", HUMAN_PROMPT),
            ])
            llm = ChatOpenAI(
                model="gpt-4o-mini",
                temperature=0.3,
                streaming=True,
                openai_api_key=os.environ["OPENAI_API_KEY"],
            )
            chain = prompt | llm | StrOutputParser()
            logger.info("=" * 60)
            print("\n[답변]")
            for chunk in chain.stream({"context": rag_context, "question": question}):
                print(chunk, end="", flush=True)
            print("\n")
            return

    # 팀 미감지 → 벡터 RAG
    from rag.document_loader import KLeagueDocumentLoader
    from rag.pipeline import build_pipeline

    k1_path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    documents = []
    if k1_path.exists():
        loader = KLeagueDocumentLoader()
        documents = loader.load_from_file(k1_path)

    pipeline = build_pipeline(documents=documents)
    logger.info(f"질문 (벡터 RAG): {question}")
    logger.info("=" * 60)
    print("\n[답변]")
    for chunk in pipeline.stream(question):
        print(chunk, end="", flush=True)
    print("\n")



def cmd_stats(team_keyword: str, season: int = 2025) -> None:
    """
    팀 통계를 로컬 JSON에서 직접 계산합니다 (RAG 우회).
    '승률' 같은 집계 질문에 사용하세요.
    """
    k1_path = ROOT / "data" / "processed" / "teams" / "k1_team_results.json"
    if not k1_path.exists():
        logger.error("데이터 파일 없음")
        return

    records = json.loads(k1_path.read_text(encoding="utf-8"))

    # game_id 중복 제거
    seen_ids: set = set()
    unique: list = []
    for r in records:
        gid = r.get("game_id")
        if gid not in seen_ids:
            seen_ids.add(gid)
            unique.append(r)

    # 시즌 필터
    records = [r for r in unique if r.get("season") == season]

    # 팀 키워드 매칭 (부분 일치)
    home_games = [r for r in records if team_keyword in r.get("home_team", "")]
    away_games = [r for r in records if team_keyword in r.get("away_team", "")]
    all_games  = home_games + away_games

    if not all_games:
        print(f"'{team_keyword}' 경기 없음 (시즌: {season})")
        return

    # 홈 통계
    h_win  = sum(1 for r in home_games if r["home_score"] > r["away_score"])
    h_draw = sum(1 for r in home_games if r["home_score"] == r["away_score"])
    h_lose = sum(1 for r in home_games if r["home_score"] < r["away_score"])
    h_gf   = sum(r["home_score"] for r in home_games)
    h_ga   = sum(r["away_score"] for r in home_games)

    # 원정 통계
    a_win  = sum(1 for r in away_games if r["away_score"] > r["home_score"])
    a_draw = sum(1 for r in away_games if r["away_score"] == r["home_score"])
    a_lose = sum(1 for r in away_games if r["away_score"] < r["home_score"])
    a_gf   = sum(r["away_score"] for r in away_games)
    a_ga   = sum(r["home_score"] for r in away_games)

    # 전체 통계
    total_w = h_win + a_win
    total_d = h_draw + a_draw
    total_l = h_lose + a_lose
    total_g = len(all_games)
    win_rate = total_w / total_g * 100 if total_g else 0

    print(f"\n{'='*50}")
    print(f"  {team_keyword}  |  {season} 시즌  |  총 {total_g}경기")
    print(f"{'='*50}")
    print(f"  전체   : {total_w}승 {total_d}무 {total_l}패  (승률 {win_rate:.1f}%)")
    print(f"  홈({len(home_games):2}경기): {h_win}승 {h_draw}무 {h_lose}패  득실 {h_gf}-{h_ga} ({h_gf-h_ga:+d})")
    print(f"  원정({len(away_games):2}경기): {a_win}승 {a_draw}무 {a_lose}패  득실 {a_gf}-{a_ga} ({a_gf-a_ga:+d})")
    print(f"{'='*50}")

    # 최근 5경기
    recent = sorted(all_games, key=lambda r: r.get("date", ""), reverse=True)[:5]
    print("\n  [최근 5경기]")
    for r in recent:
        is_home = team_keyword in r.get("home_team", "")
        opponent = r["away_team"] if is_home else r["home_team"]
        gf = r["home_score"] if is_home else r["away_score"]
        ga = r["away_score"] if is_home else r["home_score"]
        venue = "홈" if is_home else "원정"
        result = "승" if gf > ga else ("무" if gf == ga else "패")
        print(f"    {r['date']}  {venue} vs {opponent}  {gf}-{ga}  [{result}]")
    print()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="K리그 RAG 파이프라인 도구",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--clear",   action="store_true", help="기존 데이터 삭제 후 재인제스트")
    parser.add_argument("--dry-run", action="store_true", help="저장 없이 Document 수만 확인")
    parser.add_argument("--init-db", action="store_true", help="Supabase 스키마 SQL 출력")
    parser.add_argument("--query",   type=str,            help="RAG 쿼리 테스트")
    parser.add_argument("--stats",   type=str,            help="팀 통계 직접 계산 (예: --stats 전북)")
    parser.add_argument("--season",  type=int, default=2025, help="통계 시즌 (기본값: 2025)")

    args = parser.parse_args()

    logger.remove()
    logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}",
        colorize=True,
    )

    if args.init_db:
        cmd_init_db()
    elif args.query:
        cmd_query(args.query)
    elif args.stats:
        cmd_stats(args.stats, season=args.season)
    else:
        cmd_ingest(clear=args.clear, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
