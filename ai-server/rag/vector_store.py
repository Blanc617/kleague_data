"""
Supabase pgvector 인제스트 및 검색 클라이언트.
supabase-py 2.x 직접 사용 (langchain_community.SupabaseVectorStore 미사용).
OpenAI text-embedding-3-small (1536차원) 임베딩을 사용합니다.
"""

import os
import time
from typing import Any

from langchain_core.documents import Document
from langchain_core.embeddings import Embeddings
from langchain_core.retrievers import BaseRetriever
from langchain_core.vectorstores import VectorStore
from langchain_openai import OpenAIEmbeddings
from loguru import logger
from supabase import Client, create_client
from tenacity import retry, stop_after_attempt, wait_exponential


class SupabaseVectorStoreCustom(VectorStore):
    """
    supabase-py 2.x 기반 커스텀 벡터 스토어.
    langchain_community.SupabaseVectorStore의 2.x 비호환 문제를 우회합니다.
    """

    def __init__(
        self,
        client: Client,
        embeddings: Embeddings,
        table_name: str = "match_documents",
        query_name: str = "match_documents",
    ) -> None:
        self._client = client
        self._embeddings = embeddings
        self._table_name = table_name
        self._query_name = query_name

    # ── VectorStore 추상 메서드 구현 ──────────────────

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict] | None = None,
        **kwargs: Any,
    ) -> list[str]:
        """텍스트 목록을 임베딩해 Supabase에 저장합니다."""
        vectors = self._embeddings.embed_documents(texts)
        rows = []
        for i, (text, vector) in enumerate(zip(texts, vectors)):
            meta = metadatas[i] if metadatas else {}
            rows.append({
                "content":  text,
                "embedding": vector,
                "metadata":  meta,
                "source":    meta.get("source", ""),
                "doc_type":  meta.get("doc_type", ""),
                "team":      meta.get("team", ""),
            })

        result = self._client.table(self._table_name).insert(rows).execute()
        return [str(r.get("id", "")) for r in (result.data or [])]

    def similarity_search(
        self,
        query: str,
        k: int = 5,
        **kwargs: Any,
    ) -> list[Document]:
        """쿼리와 가장 유사한 Document k개를 반환합니다."""
        vector = self._embeddings.embed_query(query)
        return self.similarity_search_by_vector(vector, k=k, **kwargs)

    def similarity_search_by_vector(
        self,
        embedding: list[float],
        k: int = 5,
        filter: dict | None = None,
        **kwargs: Any,
    ) -> list[Document]:
        """벡터로 유사도 검색합니다 (supabase 2.x RPC 직접 호출)."""
        params: dict = {
            "query_embedding": embedding,
            "match_count": k,
        }
        if filter:
            params["filter"] = filter

        result = self._client.rpc(self._query_name, params).execute()
        docs = []
        for row in (result.data or []):
            docs.append(Document(
                page_content=row["content"],
                metadata=row.get("metadata", {}),
            ))
        return docs

    @classmethod
    def from_texts(
        cls,
        texts: list[str],
        embedding: Embeddings,
        metadatas: list[dict] | None = None,
        **kwargs: Any,
    ) -> "SupabaseVectorStoreCustom":
        raise NotImplementedError("from_texts 대신 VectorStoreManager.ingest()를 사용하세요.")

    def as_retriever(self, **kwargs: Any) -> BaseRetriever:
        search_kwargs = kwargs.get("search_kwargs", {})
        k = search_kwargs.get("k", 5)
        return _SupabaseRetriever(store=self, k=k)


class _SupabaseRetriever(BaseRetriever):
    """SupabaseVectorStoreCustom을 위한 Retriever 어댑터."""

    store: SupabaseVectorStoreCustom
    k: int = 5

    class Config:
        arbitrary_types_allowed = True

    def _get_relevant_documents(self, query: str, **kwargs) -> list[Document]:
        return self.store.similarity_search(query, k=self.k)


class VectorStoreManager:
    """
    Supabase pgvector 인제스트 및 연결 팩토리.

    환경변수:
        SUPABASE_URL          — Supabase 프로젝트 URL
        SUPABASE_SERVICE_KEY  — service_role 키 (인제스트용, anon 키 불가)
        OPENAI_API_KEY        — OpenAI API 키
    """

    TABLE_NAME = "match_documents"
    QUERY_NAME = "match_documents"
    EMBEDDING_MODEL = "text-embedding-3-small"
    BATCH_SIZE = 100

    def __init__(self) -> None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_KEY"]
        self._supabase = create_client(url, key)
        self._embeddings = OpenAIEmbeddings(
            model=self.EMBEDDING_MODEL,
            openai_api_key=os.environ["OPENAI_API_KEY"],
        )

    def get_store(self) -> SupabaseVectorStoreCustom:
        """벡터 스토어 클라이언트 반환 (런타임 쿼리용)."""
        return SupabaseVectorStoreCustom(
            client=self._supabase,
            embeddings=self._embeddings,
            table_name=self.TABLE_NAME,
            query_name=self.QUERY_NAME,
        )

    def ingest(
        self,
        documents: list[Document],
        clear_existing: bool = False,
    ) -> int:
        """Document 목록을 Supabase에 인제스트합니다."""
        if clear_existing:
            logger.warning("기존 데이터 삭제 중...")
            self._clear_table()

        total = len(documents)
        logger.info(f"인제스트 시작: {total}개 Document")

        ingested = 0
        for i in range(0, total, self.BATCH_SIZE):
            batch = documents[i: i + self.BATCH_SIZE]
            batch_num = i // self.BATCH_SIZE + 1
            total_batches = (total + self.BATCH_SIZE - 1) // self.BATCH_SIZE

            logger.info(f"  배치 {batch_num}/{total_batches} ({len(batch)}개)...")
            self._ingest_batch(batch)
            ingested += len(batch)

            if i + self.BATCH_SIZE < total:
                time.sleep(0.5)

        logger.info(f"인제스트 완료: {ingested}/{total}개")
        return ingested

    def count(self) -> int:
        """현재 테이블의 Document 수를 반환합니다."""
        resp = self._supabase.table(self.TABLE_NAME).select("id", count="exact").execute()
        return resp.count or 0

    # ── 내부 메서드 ──────────────────────────────────

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True,
    )
    def _ingest_batch(self, batch: list[Document]) -> None:
        texts = [doc.page_content for doc in batch]
        metadatas = [doc.metadata for doc in batch]
        store = self.get_store()
        store.add_texts(texts, metadatas=metadatas)

    def _clear_table(self) -> None:
        self._supabase.table(self.TABLE_NAME).delete().neq("id", 0).execute()
        logger.info(f"테이블 '{self.TABLE_NAME}' 초기화 완료")
