#!/bin/bash
# 스크립트가 어느 위치에서 실행되든 상관없이 프로젝트 루트를 기준으로 동작하도록 설정
cd "$(dirname "$0")/.."

# 의존성 완벽 동기화
uv sync

# Ruff Check (Lint & Fix)
uv run ruff check --fix main.py app tests

# Ruff Format
uv run ruff format main.py app tests

# Pyright Check (Type Checking)
uv run pyright main.py app tests
