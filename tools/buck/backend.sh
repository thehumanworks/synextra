#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SYNEXTRA_REPO_ROOT:-$PWD}"
if [[ ! -d "${REPO_ROOT}/backend" && -d "${SCRIPT_DIR}/../../backend" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi
if [[ ! -d "${REPO_ROOT}/backend" && -n "${BUCK_PROJECT_ROOT:-}" && -d "${BUCK_PROJECT_ROOT}/backend" ]]; then
  REPO_ROOT="${BUCK_PROJECT_ROOT}"
fi
BACKEND_DIR="${REPO_ROOT}/backend"

if [[ ! -d "${BACKEND_DIR}" ]]; then
  echo "backend module not found: ${BACKEND_DIR}" >&2
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <install|lint|test|typecheck|dev>" >&2
  exit 2
fi

cd "${BACKEND_DIR}"

case "$1" in
  install)
    uv sync --dev
    ;;
  lint)
    uv run ruff check .
    uv run ruff format --check .
    ;;
  test)
    uv run pytest
    ;;
  typecheck)
    uv run mypy
    ;;
  dev)
    uv run uvicorn synextra_backend.app:app --reload
    ;;
  *)
    echo "unknown backend action: $1" >&2
    exit 2
    ;;
esac
