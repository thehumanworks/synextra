#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SYNEXTRA_REPO_ROOT:-$PWD}"
if [[ ! -d "${REPO_ROOT}/cli" && -d "${SCRIPT_DIR}/../../cli" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi
if [[ ! -d "${REPO_ROOT}/cli" && -n "${BUCK_PROJECT_ROOT:-}" && -d "${BUCK_PROJECT_ROOT}/cli" ]]; then
  REPO_ROOT="${BUCK_PROJECT_ROOT}"
fi
CLI_DIR="${REPO_ROOT}/cli"

if [[ ! -d "${CLI_DIR}" ]]; then
  echo "cli module not found: ${CLI_DIR}" >&2
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <install|lint|test|typecheck>" >&2
  exit 2
fi

cd "${CLI_DIR}"

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
    echo "unknown cli action: $1" >&2
    exit 2
    ;;
esac
