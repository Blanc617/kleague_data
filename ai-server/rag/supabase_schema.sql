-- K리그 AI 해설 도구 — Supabase pgvector 스키마
-- Supabase SQL Editor에서 실행하거나 run_ingest.py --init-db 로 자동 실행

-- 1. pgvector 확장 활성화
create extension if not exists vector;

-- 2. 문서 테이블 생성
create table if not exists match_documents (
    id          bigserial primary key,
    content     text        not null,               -- 자연어 텍스트 (임베딩 대상)
    embedding   vector(1536),                       -- text-embedding-3-small 차원
    metadata    jsonb       not null default '{}',  -- game_id, season, team 등
    source      text,                               -- 'kleague' | 'wikipedia' | 'naver'
    doc_type    text,                               -- 'match_result' | 'article' | 'derby'
    team        text,                               -- 필터링용 팀 이름
    created_at  timestamptz default now()
);

-- 3. HNSW 인덱스 (cosine 유사도 기반 ANN 검색)
create index if not exists match_documents_embedding_hnsw_idx
    on match_documents
    using hnsw (embedding vector_cosine_ops)
    with (m = 16, ef_construction = 64);

-- 4. 메타데이터 필터링 인덱스
create index if not exists match_documents_season_idx
    on match_documents ((metadata->>'season'));

create index if not exists match_documents_team_idx
    on match_documents (team);

create index if not exists match_documents_doc_type_idx
    on match_documents (doc_type);

-- 5. LangChain SupabaseVectorStore가 호출하는 표준 RPC 함수
--    시그니처를 변경하면 LangChain에서 인식 불가 → 그대로 유지
create or replace function match_documents(
    query_embedding vector(1536),
    match_count     int     default 5,
    filter          jsonb   default '{}'
)
returns table (
    id          bigint,
    content     text,
    metadata    jsonb,
    similarity  float
)
language plpgsql
as $$
#variable_conflict use_column
begin
    return query
    select
        id,
        content,
        metadata,
        1 - (match_documents.embedding <=> query_embedding) as similarity
    from match_documents
    where
        case
            when filter = '{}'::jsonb then true
            else metadata @> filter
        end
    order by match_documents.embedding <=> query_embedding
    limit match_count;
end;
$$;

-- 실행 확인용 쿼리
-- select count(*) from match_documents;
