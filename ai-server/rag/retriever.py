"""
Hybrid Search 리트리버.
BM25(30%) + Supabase 벡터(70%) EnsembleRetriever.

BM25: 날짜·팀명·라운드처럼 정확한 키워드 매칭에 강함.
벡터: "극적인 역전" "최근 부진" 처럼 의미 기반 검색에 강함.
두 리트리버를 앙상블해 두 강점을 모두 활용합니다.
"""

from langchain_classic.retrievers.ensemble import EnsembleRetriever
from langchain_community.retrievers import BM25Retriever
from rag.vector_store import SupabaseVectorStoreCustom as SupabaseVectorStore
from langchain_core.documents import Document
from loguru import logger


class HybridRetriever:
    """
    BM25 + 벡터 Hybrid Search 리트리버.

    사용 예:
        retriever = HybridRetriever(vector_store, all_docs).build()
        docs = retriever.invoke("전북이 이긴 최근 경기")
    """

    BM25_WEIGHT = 0.3
    VECTOR_WEIGHT = 0.7
    TOP_K = 15

    def __init__(
        self,
        vector_store: SupabaseVectorStore,
        documents: list[Document],
    ) -> None:
        self._vector_store = vector_store
        self._documents = documents
        self._retriever: EnsembleRetriever | None = None

    def build(self) -> EnsembleRetriever:
        """EnsembleRetriever를 생성합니다."""
        logger.info(f"Hybrid Retriever 초기화 (BM25 {int(self.BM25_WEIGHT*100)}% + 벡터 {int(self.VECTOR_WEIGHT*100)}%)")

        bm25 = BM25Retriever.from_documents(
            self._documents,
            k=self.TOP_K,
        )

        vector = self._vector_store.as_retriever(
            search_type="similarity",
            search_kwargs={"k": self.TOP_K},
        )

        self._retriever = EnsembleRetriever(
            retrievers=[bm25, vector],
            weights=[self.BM25_WEIGHT, self.VECTOR_WEIGHT],
        )
        logger.info(f"  BM25 인덱스: {len(self._documents)}개 Document")
        return self._retriever

    def build_with_filter(self, season: int | None = None, team: str | None = None) -> EnsembleRetriever:
        """메타데이터 필터가 적용된 벡터 리트리버와 앙상블합니다."""
        search_kwargs: dict = {"k": self.TOP_K}

        # Supabase 필터 (jsonb metadata 기반)
        filter_dict: dict = {}
        if season:
            filter_dict["season"] = str(season)
        if team:
            filter_dict["home_team"] = team  # home 또는 away 검색은 별도 처리 필요

        if filter_dict:
            search_kwargs["filter"] = filter_dict

        # BM25는 필터 미지원 → 전체 문서 대상으로 유지
        bm25 = BM25Retriever.from_documents(self._documents, k=self.TOP_K)

        vector = self._vector_store.as_retriever(
            search_type="similarity",
            search_kwargs=search_kwargs,
        )

        return EnsembleRetriever(
            retrievers=[bm25, vector],
            weights=[self.BM25_WEIGHT, self.VECTOR_WEIGHT],
        )

    def get_retriever(self) -> EnsembleRetriever:
        """캐시된 retriever 반환 (lazy init)."""
        if self._retriever is None:
            self._retriever = self.build()
        return self._retriever
