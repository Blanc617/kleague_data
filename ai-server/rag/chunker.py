"""
LangChain RecursiveCharacterTextSplitter 기반 텍스트 청킹.
경기 결과 텍스트는 짧기 때문에 대부분 청킹 없이 통과됩니다.
추후 선수 데이터·기사 데이터 추가를 위해 표준화해 둡니다.
"""

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from loguru import logger


class MatchDocumentChunker:
    """
    Document 청킹기.

    - chunk_size=500: 한국어 기준 약 250 토큰. text-embedding-3-small의 최적 입력 범위.
    - chunk_overlap=50: 청크 경계에서 문맥 손실 방지.
    - 경기 결과 텍스트(80~150자)는 chunk_size를 초과하지 않으므로 그대로 통과.
    """

    DEFAULT_CHUNK_SIZE = 500
    DEFAULT_CHUNK_OVERLAP = 50

    def __init__(
        self,
        chunk_size: int = DEFAULT_CHUNK_SIZE,
        chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
    ) -> None:
        self._splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
            keep_separator=True,
            length_function=len,
        )

    def chunk(self, documents: list[Document]) -> list[Document]:
        """Document 목록을 청킹합니다. 원본 metadata를 보존합니다."""
        result: list[Document] = []

        for doc in documents:
            chunks = self._splitter.split_documents([doc])
            # 청크 인덱스 메타데이터 추가
            for i, chunk in enumerate(chunks):
                chunk.metadata["chunk_index"] = i
                chunk.metadata["total_chunks"] = len(chunks)
                result.append(chunk)

        skipped = sum(1 for d in documents if len(d.page_content) <= self.DEFAULT_CHUNK_SIZE)
        logger.info(
            f"청킹 완료: {len(documents)}개 → {len(result)}개 "
            f"({skipped}개는 청킹 없이 통과)"
        )
        return result
