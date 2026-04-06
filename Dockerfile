# ---- 1단계: 의존성 설치 (캐시 레이어) ----
FROM python:3.12-slim AS deps

# uv 설치
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# 파이썬 최적화 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV UV_LINK_MODE=copy

# 의존성 파일 복사
COPY pyproject.toml uv.lock ./

# 프로덕션 의존성만 설치 (dev, worker 그룹 제외) 및 불필요한 파일 즉시 삭제
RUN uv sync --frozen --no-dev --no-group worker --no-install-project \
    && find /app/.venv -type d -name "__pycache__" -exec rm -rf {} + \
    && rm -rf /root/.cache/uv

# ---- 2단계: 애플리케이션 이미지 ----
FROM python:3.12-slim AS runtime

WORKDIR /app

# 파이썬 최적화 설정
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# 1단계에서 설치된 가상환경만 복사
COPY --from=deps /app/.venv /app/.venv
ENV PATH="/app/.venv/bin:$PATH"

# 실행에 필요한 최소한의 코드만 복사
COPY main.py ./
COPY app/ ./app/

# Railway PORT 설정 (기본값 8000)
ENV PORT=8000
EXPOSE ${PORT}

# uvicorn 실행
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT}"]
