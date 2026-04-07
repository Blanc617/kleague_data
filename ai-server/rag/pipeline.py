"""
LCEL 기반 전체 RAG 쿼리 파이프라인.
캐시 체크 → Hybrid Search → 프롬프트 구성 → GPT-4o-mini → 답변.

사용 예:
    pipeline = RAGPipeline()
    answer = pipeline.query("전북이 이긴 최근 3경기 알려줘")
    # 스트리밍: pipeline.stream("...")
"""

import os
from typing import Iterator

from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_core.documents import Document
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough
from langchain_openai import ChatOpenAI
from loguru import logger

from rag.cache import RAGCache
from rag.vector_store import VectorStoreManager


# ── 프롬프트 템플릿 ────────────────────────────────

SYSTEM_PROMPT = """당신은 K리그 전문 해설 보조 AI입니다.
주어진 경기 데이터를 바탕으로 해설자에게 간결하고 유용한 인사이트를 제공합니다.

규칙:
- 반드시 아래 [경기 데이터] 안의 내용만 사용합니다.
- 데이터에 없는 내용은 "제공된 데이터에서 확인 불가"로 답합니다. 절대 추측하지 않습니다.
- 승률·평균득점 등 통계는 제공된 경기 목록을 직접 계산해 답합니다.
- 숫자(득점, 날짜, 라운드)는 정확히 인용합니다.
- 경기 결과가 부분적으로만 있으면 "제공된 N경기 기준"임을 명시합니다.

출력 형식:
- 경기 결과 목록은 반드시 마크다운 표(| 구분자)로 정리합니다.
- 표 컬럼: 날짜 | 라운드 | 홈팀(H) | 스코어 | 원정팀(A) | 경기장
- 표 아래에 간단한 요약(전적, 승률 등)을 1~3줄로 추가합니다."""

HUMAN_PROMPT = """[경기 데이터]
{context}

[질문]
{question}"""

PROMPT = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", HUMAN_PROMPT),
])


def _format_docs(docs: list[Document]) -> str:
    """검색된 Document 목록을 프롬프트용 텍스트로 변환합니다."""
    if not docs:
        return "관련 데이터 없음"
    return "\n\n".join(f"[{i+1}] {doc.page_content}" for i, doc in enumerate(docs))


class RAGPipeline:
    """
    K리그 해설 보조 RAG 파이프라인.

    초기화 시 Supabase 연결이 필요합니다.
    환경변수: SUPABASE_URL, SUPABASE_SERVICE_KEY, OPENAI_API_KEY, REDIS_URL
    """

    def __init__(
        self,
        retriever: EnsembleRetriever | None = None,
        cache: RAGCache | None = None,
        model: str = "gpt-4o-mini",
        temperature: float = 0.3,
    ) -> None:
        self._retriever = retriever
        self._cache = cache or RAGCache()
        self._llm = ChatOpenAI(
            model=model,
            temperature=temperature,
            streaming=True,
            openai_api_key=os.environ["OPENAI_API_KEY"],
        )
        self._chain = self._build_chain()

    def _build_chain(self):
        """LCEL 체인 구성."""
        return (
            {
                "context": self._retriever | _format_docs,
                "question": RunnablePassthrough(),
            }
            | PROMPT
            | self._llm
            | StrOutputParser()
        )

    def query(self, question: str) -> str:
        """
        동기 쿼리. 캐시 히트 시 즉시 반환.

        Args:
            question: 해설자의 자연어 질문.

        Returns:
            AI 답변 문자열.
        """
        # 캐시 체크
        cached = self._cache.get(question)
        if cached:
            logger.info(f"캐시 히트: {question[:30]}...")
            return cached

        logger.info(f"RAG 쿼리: {question[:50]}...")
        answer = self._chain.invoke(question)

        # 캐시 저장
        self._cache.set(question, answer)
        return answer

    def stream(self, question: str) -> Iterator[str]:
        """
        SSE 스트리밍 쿼리. 캐시 히트 시 전체 텍스트를 단번에 yield.

        Args:
            question: 해설자의 자연어 질문.

        Yields:
            토큰 단위 문자열 조각.
        """
        cached = self._cache.get(question)
        if cached:
            logger.info(f"캐시 히트 (스트림): {question[:30]}...")
            yield cached
            return

        logger.info(f"RAG 스트림: {question[:50]}...")
        full_answer = ""
        for chunk in self._chain.stream(question):
            full_answer += chunk
            yield chunk

        self._cache.set(question, full_answer)

    def get_source_docs(self, question: str) -> list[Document]:
        """검색된 소스 Document를 반환합니다 (디버깅·출처 표시용)."""
        if self._retriever is None:
            return []
        return self._retriever.invoke(question)


def build_pipeline(
    documents: list[Document] | None = None,
    model: str = "gpt-4o-mini",
) -> RAGPipeline:
    """
    RAGPipeline 팩토리 함수.
    VectorStoreManager와 HybridRetriever를 연결해 완성된 파이프라인을 반환합니다.

    Args:
        documents: BM25 인덱스용 전체 Document 목록. None이면 벡터 검색만 사용.
        model: 사용할 OpenAI 모델명.
    """
    from rag.retriever import HybridRetriever

    vsm = VectorStoreManager()
    store = vsm.get_store()

    if documents:
        hybrid = HybridRetriever(store, documents)
        retriever = hybrid.build()
    else:
        # BM25 없이 벡터만 사용 (documents 없을 때 폴백)
        retriever = store.as_retriever(search_kwargs={"k": 5})
        logger.warning("documents 없음 → 벡터 검색만 사용 (BM25 비활성)")

    return RAGPipeline(retriever=retriever, model=model)
