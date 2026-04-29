# ⚽ K-League AI 해설 보조 어시스턴트

> **중계 중에 30초 걸리던 선수·팀 데이터 조회를 2~3초로.**

K리그 방송 해설진을 위한 AI 해설 보조 서비스입니다.  
자연어로 질문하면 2010~2026년 K리그 경기 데이터를 기반으로 즉시 답변을 스트리밍합니다.  
하이브리드 검색(BM25 + 벡터) + RAG 파이프라인으로 LLM 환각 없이 정확한 경기 데이터를 제공합니다.

---

## 📌 프로젝트 개요

| 항목 | 내용 |
|------|------|
| 서비스명 | K-League AI 해설 어시스턴트 |
| 목적 | 생방송 중 해설진의 선수/팀 통계 즉시 조회 지원 |
| 주요 고객 | 스포티비, 쿠팡플레이, 티빙 스포츠 중계팀 |
| 데이터 범위 | K리그1 (12팀) + K리그2, 2010~2026시즌 |
| 기술 접근 | Query Classification → 정형 쿼리는 직접 JSON 조회, 서술형은 RAG |

**해결하는 문제**: 생방송 중 PD가 서류를 뒤지며 30초 이상 소요되던 선수·팀 기록 조회를 AI가 2~3초 안에 답변

---

## 🛠 기술 스택

### Frontend
| 기술 | 버전 | 용도 |
|------|------|------|
| React | 19.2.4 | UI 라이브러리 |
| TypeScript | 5 | 정적 타입 |
| Vite | 8.0.1 | 번들러 |
| TailwindCSS | 4.2.2 | 스타일링 |
| React Router DOM | 7.13.2 | 클라이언트 라우팅 |

### Backend
| 기술 | 버전 | 용도 |
|------|------|------|
| FastAPI | ≥0.115.0 | REST API + SSE 스트리밍 |
| Uvicorn | ≥0.30.0 | ASGI 서버 |
| Pydantic | ≥2.0.0 | 데이터 검증 |
| httpx | ≥0.27.0 | 비동기 HTTP 클라이언트 |

### AI / RAG
| 기술 | 용도 |
|------|------|
| OpenAI GPT-4o-mini | 스트리밍 답변 생성, 선수 비교 요약 |
| OpenAI text-embedding-3-small | 문서 임베딩 (1536차원) |
| LangChain ≥0.3.0 | LCEL RAG 파이프라인 |
| Supabase pgvector | 벡터 검색 (HNSW 인덱스, cosine) |
| rank-bm25 | 키워드 기반 BM25 검색 |
| Redis | 쿼리 결과 캐싱 |

### 데이터 수집
| 기술 | 용도 |
|------|------|
| BeautifulSoup4 4.12.3 | HTML 파싱 |
| requests / httpx | HTTP 크롤링 |
| tenacity | 재시도 로직 |
| Loguru | 구조화 로깅 |

### 배포
| 기술 | 용도 |
|------|------|
| Docker (멀티스테이지) | Node.js 빌드 → Python 서빙 |
| Railway / Render | 백엔드 호스팅 |
| Supabase | 벡터 DB + 스토리지 |

---

## 🏗 시스템 아키텍처

### 전체 구조

```
[브라우저]
    │  HTTP / SSE
    ▼
[FastAPI 백엔드]
    │
    ├─── Query Classifier (Regex)
    │         │
    │    정형 쿼리 ──► MatchDataEngine (직접 JSON 조회)
    │         │              └─ 환각 없이 정확한 구조화 데이터 반환
    │         │
    │    서술 쿼리 ──► RAG Pipeline (LangChain LCEL)
    │                      ├─ HybridRetriever
    │                      │    ├─ BM25 (30%) — 날짜·팀명 키워드
    │                      │    └─ pgvector (70%) — 시맨틱 검색
    │                      ├─ ChatPromptTemplate
    │                      └─ GPT-4o-mini (streaming)
    │
    ├─── Redis Cache (동일 질문 즉시 반환)
    │
    └─── Supabase pgvector ◄── OpenAI Embeddings (1536-dim)
```

### 데이터 파이프라인

```
[크롤러]
    ├─ kleague.com (공식)
    ├─ Transfermarkt (이적·시장가치)
    ├─ Wikipedia (역사·기록)
    └─ Naver Sports (기사)
         │
         ▼
[ai-server/data/processed/]
    ├─ matches/match_events_{year}.json
    ├─ matches/match_stats_{year}.json
    ├─ players/player_stats_{year}.json
    ├─ players/player_minutes_{year}.json
    ├─ teams/k1_team_results.json
    └─ derby/{슈퍼매치,클래식}.json
         │
         ▼
[run_ingest.py] → Supabase pgvector (match_documents)
```

### 디렉토리 구조

```
soccer_commentary/
├── frontend/                   # React + TypeScript SPA
│   └── src/
│       ├── pages/              # ChatPage, StatsPage, SchedulePage, StandingsPage
│       ├── components/         # AppLayout, ChatMessage, TeamLogo, SeasonSelector
│       ├── hooks/              # useFavorites
│       ├── api.ts              # SSE 스트리밍 클라이언트
│       └── types.ts            # TypeScript 인터페이스
│
├── backend/                    # FastAPI 서버
│   ├── main.py                 # 앱 초기화, CORS, SPA fallback
│   └── routers/
│       ├── query.py            # SSE 스트리밍 자연어 쿼리
│       ├── stats.py            # 팀 통계, 관중, 순위
│       ├── players.py          # 선수 검색·비교 (GPT-4o-mini)
│       └── schedule.py         # 경기 일정·결과·상세
│
├── ai-server/                  # 데이터 수집 & RAG 파이프라인
│   ├── crawlers/               # 멀티소스 크롤러
│   ├── rag/                    # RAG 파이프라인 (pipeline, retriever, vector_store)
│   ├── data_engine/            # 직접 JSON 쿼리 엔진
│   ├── data/processed/         # 전처리 완료 JSON 데이터
│   └── [40+ 유틸리티 스크립트]
│
├── Dockerfile                  # 멀티스테이지 빌드
└── render.yaml                 # Render.com 배포 설정
```

---

## ✨ 핵심 기능

### 1. 실시간 AI 채팅 (`/`)
- 자연어 질문 → SSE 토큰 스트리밍으로 즉시 답변
- 시즌 범위 필터 (단일 시즌 또는 2010~2026 전체)
- 출처 경기 인용 표시
- Redis 캐싱으로 동일 질문 즉시 재응답

**예시 질문**
```
"2024시즌 전반 15분 이전에 선제골 넣은 경기 알려줘"
"이강인 K리그 시절 커리어 통계"
"울산과 전북의 역대 맞대결 전적"
"2023 득점왕은 누구야?"
```

### 2. 선수 관리 (`/players`)
- 이름·팀·포지션으로 선수 검색
- 2010~2026 커리어 전체 통계
- **AI 비교 기능**: 두 선수 나란히 GPT-4o-mini 요약 비교
- 경기별 출전 시간 추적

### 3. 팀 통계 (`/stats`)
- 시즌별 승/무/패, 홈/원정 분리 성적
- 15분 단위 시간대별 득실점 분포
- 최근 N경기 폼 분석
- 관중 통계 및 순위

### 4. 순위표 (`/standings`)
- 실시간 리그 테이블 (K1 최종 라운드 A/B그룹 포함)
- 라운드별 순위 변동 타임라인

### 5. 경기 일정·결과 (`/schedule`)
- 2010~2026 전 시즌 일정 (페이지네이션)
- 경기 상세: 골·카드·교체 이벤트, 점유율·슈팅·코너킥 통계

### 6. RAG 파이프라인

**쿼리 분류 → 처리 경로 결정**

| 쿼리 유형 | 예시 | 처리 방식 |
|-----------|------|----------|
| EARLY_GOAL | "전반 15분 이전 선제골" | MatchDataEngine (JSON 직접 조회) |
| HEAD_TO_HEAD | "맞대결 전적" | MatchDataEngine |
| TOP_SCORERS | "득점왕" | MatchDataEngine |
| TEAM_STATS | "승률, 순위" | MatchDataEngine |
| NARRATIVE | 그 외 서술형 | RAG (BM25 + Vector + GPT-4o-mini) |

**하이브리드 검색 비율**
- BM25 30% — 날짜, 팀명, 라운드 번호 키워드 매칭
- pgvector 70% — 시맨틱 유사도 검색

---

## 🔌 주요 API

### Chat (SSE 스트리밍)

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/query` | POST | 자연어 질문 → SSE 토큰 스트리밍 |

```
Query Params: question (str), season (int), season_to (int, optional)
Response: text/event-stream — tokens, sources, done 이벤트
```

### 팀 통계

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/stats/teams` | GET | 시즌 내 팀 목록 |
| `/api/stats/{team}` | GET | 팀 시즌 통계 (승/무/패, 홈/원정) |
| `/api/stats/{team}/form` | GET | 최근 N경기 폼 (기본 20경기) |
| `/api/stats/{team}/goal-distribution` | GET | 15분 단위 득실점 분포 |
| `/api/attendance` | GET | 관중 통계 (팀별, 최다 경기, 평균) |
| `/api/standings` | GET | 리그 순위표 (A/B그룹 분리) |
| `/api/standings/timeline` | GET | 라운드별 순위 변동 |

### 선수

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/players` | GET | 선수 검색 (팀·포지션·최소 골·정렬 필터) |
| `/api/players/top` | GET | 득점 상위 N명 (기본 10명) |
| `/api/players/search` | GET | 이름 자동완성 |
| `/api/players/{name}/career` | GET | 커리어 통계 (2010~2026) |
| `/api/players/compare` | GET | 두 선수 AI 비교 (GPT-4o-mini 요약) |
| `/api/player-minutes/{player}` | GET | 선수 경기별 출전 시간 |
| `/api/team-minutes/{team}` | GET | 팀 로스터 출전 시간 요약 |

### 일정

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/api/schedule` | GET | 시즌 경기 일정 (날짜순, 페이지네이션) |
| `/api/schedule/{season}/{game_id}` | GET | 경기 상세 (이벤트 + 통계) |
| `/api/schedule/teams` | GET | 시즌 참가 팀 목록 |

### 기타

| 엔드포인트 | 메서드 | 설명 |
|-----------|--------|------|
| `/health` | GET | 헬스체크 |

---

## 🗄 데이터베이스 스키마

### Supabase pgvector — `match_documents`

```sql
CREATE TABLE match_documents (
    id          BIGSERIAL    PRIMARY KEY,
    content     TEXT         NOT NULL,           -- 자연어 경기 텍스트
    embedding   VECTOR(1536),                    -- text-embedding-3-small
    metadata    JSONB        NOT NULL DEFAULT '{}', -- game_id, season, team, date 등
    source      TEXT,                            -- 'kleague' | 'wikipedia' | 'naver'
    doc_type    TEXT,                            -- 'match_result' | 'article' | 'derby'
    team        TEXT,
    created_at  TIMESTAMPTZ  DEFAULT NOW()
);

-- 인덱스
CREATE INDEX ON match_documents USING hnsw (embedding vector_cosine_ops);
CREATE INDEX ON match_documents (team);
CREATE INDEX ON match_documents (doc_type);
```

**문서 예시** (1경기 → 홈팀 + 원정팀 2개 문서 생성):
```
"K리그 1라운드 경기. 포항이 서울월드컵경기장에서 대전을 상대로 홈 경기를 치러
2대1로 승리. 경기 날짜는 2025년 2월 15일이다. 골 이벤트: 최건주 31분..."
```

### JSON 데이터 파일 (로컬 파일시스템)

| 파일 경로 | 내용 |
|-----------|------|
| `data/processed/matches/match_events_{year}.json` | 골·카드·교체 이벤트 |
| `data/processed/matches/match_stats_{year}.json` | 점유율·슈팅·코너킥 |
| `data/processed/players/player_stats_{year}.json` | 선수별 골·도움·출전 |
| `data/processed/players/player_minutes_{year}.json` | 경기별 출전 시간 |
| `data/processed/teams/k1_team_results.json` | 전 시즌 경기 결과 |
| `data/processed/derby/슈퍼매치.json` | 서울 vs 수원삼성 맞대결 |
| `data/processed/derby/클래식.json` | 전북 vs 울산 클래식 |

---

## ⚙️ 환경 변수

**`backend/.env`**
```env
OPENAI_API_KEY=sk-...
SUPABASE_URL=https://<project>.supabase.co
SUPABASE_SERVICE_KEY=<service_role_key>
REDIS_URL=redis://...
ALLOWED_ORIGINS=http://localhost:3000,https://yourdomain.com
```

**`frontend/.env.local`**
```env
VITE_API_BASE_URL=http://localhost:8000
```

---

## 🚀 로컬 실행

### 사전 요구사항
- Python 3.11+
- Node.js 20+
- Supabase 프로젝트 (pgvector 확장 활성화)
- Redis 서버
- OpenAI API 키

### 백엔드

```bash
cd backend
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

### 프론트엔드

```bash
cd frontend
npm install
npm run dev
```

### 데이터 수집 & 벡터 인제스트

```bash
cd ai-server

# 크롤링
python run_crawlers.py

# Supabase에 벡터 인제스트
python run_ingest.py
```

### Docker (통합 빌드)

```bash
docker build -t kleague-ai .
docker run -p 8000:8000 --env-file backend/.env kleague-ai
```

### Supabase 설정

1. Supabase 프로젝트에서 pgvector 확장 활성화
2. `ai-server/rag/supabase_schema.sql` 실행
3. 환경 변수에 `SUPABASE_URL`, `SUPABASE_SERVICE_KEY` 입력

---

## 📄 라이선스

MIT
