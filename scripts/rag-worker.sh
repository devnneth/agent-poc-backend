#!/bin/bash

set -euo pipefail

cd "$(dirname "$0")/.."

WATCH_INTERVAL_SECONDS=1
WATCH_TARGETS=(
  "app"
  "scripts"
  "pyproject.toml"
  "uv.lock"
)
declare -a WORKER_ARGS=()
if [[ $# -gt 0 ]]; then
  WORKER_ARGS=("$@")
fi

child_pid=""


# 워커 종료 시 자식 프로세스도 함께 정리합니다.
cleanup() {
  if [[ -n "${child_pid}" ]] && kill -0 "${child_pid}" 2>/dev/null; then
    kill "${child_pid}" 2>/dev/null || true
    wait "${child_pid}" 2>/dev/null || true
  fi
}


# 감시 대상 파일들의 수정 시각을 하나의 해시로 계산합니다.
snapshot_files() {
  .venv/bin/python - <<'PY'
from __future__ import annotations

import hashlib
from pathlib import Path

watch_targets = [
  Path("app"),
  Path("scripts"),
  Path("pyproject.toml"),
  Path("uv.lock"),
]
watch_suffixes = {".py", ".toml", ".yaml", ".yml", ".json", ".sh"}

entries: list[str] = []
for target in watch_targets:
  if not target.exists():
    continue

  if target.is_file():
    stat = target.stat()
    entries.append(f"{target}:{stat.st_mtime_ns}:{stat.st_size}")
    continue

  for path in sorted(path for path in target.rglob("*") if path.is_file() and path.suffix in watch_suffixes):
    stat = path.stat()
    entries.append(f"{path}:{stat.st_mtime_ns}:{stat.st_size}")

print(hashlib.sha256("\n".join(entries).encode("utf-8")).hexdigest())
PY
}


# 의존성과 가상환경을 먼저 맞춘 뒤 워커를 시작합니다.
start_worker() {
  uv sync
  if [[ ${#WORKER_ARGS[@]} -gt 0 ]]; then
    uv run python -m app.workers.rag_worker_main "${WORKER_ARGS[@]}" &
  else
    uv run python -m app.workers.rag_worker_main &
  fi
  child_pid=$!
}


trap cleanup EXIT INT TERM

start_worker
last_snapshot="$(snapshot_files)"

while true; do
  sleep "${WATCH_INTERVAL_SECONDS}"

  current_snapshot="$(snapshot_files)"
  if [[ "${current_snapshot}" != "${last_snapshot}" ]]; then
    echo "[rag_worker] 코드 변경을 감지했습니다. 워커를 재시작합니다."
    cleanup
    start_worker
    last_snapshot="${current_snapshot}"
    continue
  fi

  if ! kill -0 "${child_pid}" 2>/dev/null; then
    wait "${child_pid}"
    exit $?
  fi
done
