#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SYNEXTRA_REPO_ROOT:-$PWD}"
if [[ ! -d "${REPO_ROOT}/sdk" && -d "${SCRIPT_DIR}/../../sdk" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi
if [[ ! -d "${REPO_ROOT}/sdk" && -n "${BUCK_PROJECT_ROOT:-}" && -d "${BUCK_PROJECT_ROOT}/sdk" ]]; then
  REPO_ROOT="${BUCK_PROJECT_ROOT}"
fi
SDK_DIR="${REPO_ROOT}/sdk"

if [[ ! -d "${SDK_DIR}" ]]; then
  echo "sdk module not found: ${SDK_DIR}" >&2
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <install|lint|test|typecheck>" >&2
  exit 2
fi

cd "${SDK_DIR}"

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
  *)
    echo "unknown sdk action: $1" >&2
    exit 2
    ;;
esac
