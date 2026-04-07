"""
K리그 AI 해설 보조 도구 — FastAPI 백엔드.
SSE 스트리밍으로 실시간 답변을 제공합니다.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

ROOT = Path(__file__).parent
load_dotenv(ROOT / ".env")

# ai-server 패키지 경로 추가
AI_SERVER = ROOT.parent / "ai-server"
sys.path.insert(0, str(AI_SERVER))

from routers import query, stats, players, schedule

app = FastAPI(title="K리그 AI 해설 보조 API", version="1.0.0")

_origins_env = os.getenv("ALLOWED_ORIGINS", "*")
_allowed_origins = [o.strip() for o in _origins_env.split(",")]

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(query.router, prefix="/api")
app.include_router(stats.router, prefix="/api")
app.include_router(players.router, prefix="/api")
app.include_router(schedule.router, prefix="/api")

# 프론트엔드 정적 파일 서빙
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    # 로고 파일 직접 서빙
    LOGOS_DIR = FRONTEND_DIST / "logos"
    if LOGOS_DIR.exists():
        app.mount("/logos", StaticFiles(directory=str(LOGOS_DIR)), name="logos")
    # 나머지 정적 에셋
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # SPA 폴백 — 모든 미처리 경로는 index.html 반환
    @app.get("/{full_path:path}")
    def spa_fallback(full_path: str):
        index = FRONTEND_DIST / "index.html"
        return FileResponse(str(index))
else:
    @app.get("/health")
    def health():
        return {"status": "ok"}
