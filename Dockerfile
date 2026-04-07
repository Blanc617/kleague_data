# ── Stage 1: Frontend Build ──────────────────────────────
FROM node:20-alpine AS frontend-build
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

# ── Stage 2: Python Backend ──────────────────────────────
FROM python:3.11-slim
WORKDIR /app

# Python 의존성 설치 (backend + ai-server)
COPY backend/requirements.txt ./backend-requirements.txt
COPY ai-server/requirements.txt ./ai-server-requirements.txt
RUN pip install --no-cache-dir \
    -r backend-requirements.txt \
    -r ai-server-requirements.txt

# 앱 코드 복사
COPY ai-server/ ./ai-server/
COPY backend/ ./backend/

# 빌드된 프론트엔드 복사
COPY --from=frontend-build /app/frontend/dist ./frontend/dist

WORKDIR /app/backend
EXPOSE 8000
CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
