#!/bin/bash
# 스크립트가 어느 위치에서 실행되든 상관없이 프로젝트 루트를 기준으로 동작하도록 설정
cd "$(dirname "$0")/.."

# 의존성 완벽 동기화 (uv.lock 기준)
uv sync

# 서버 실행 (uv run으로 환경 격리 및 실행)
uv run fastapi dev main.py --port 7000
