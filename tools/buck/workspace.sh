#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SYNEXTRA_REPO_ROOT:-$PWD}"
if [[ ! -d "${REPO_ROOT}/tools/buck" && -d "${SCRIPT_DIR}/../../tools/buck" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi
if [[ ! -d "${REPO_ROOT}/tools/buck" && -n "${BUCK_PROJECT_ROOT:-}" && -d "${BUCK_PROJECT_ROOT}/tools/buck" ]]; then
  REPO_ROOT="${BUCK_PROJECT_ROOT}"
fi
BACKEND_SCRIPT="${REPO_ROOT}/tools/buck/backend.sh"
FRONTEND_SCRIPT="${REPO_ROOT}/tools/buck/frontend.sh"

run_backend() {
  "${BACKEND_SCRIPT}" "$1"
}

run_frontend() {
  "${FRONTEND_SCRIPT}" "$1"
}

run_dev() {
  export SYNEXTRA_REPO_ROOT="${REPO_ROOT}"

  run_backend dev &
  local backend_pid=$!

  run_frontend dev &
  local frontend_pid=$!

  cleanup() {
    local status="${1:-0}"

    trap - INT TERM EXIT

    if kill -0 "${backend_pid}" 2>/dev/null; then
      kill "${backend_pid}" 2>/dev/null || true
    fi
    if kill -0 "${frontend_pid}" 2>/dev/null; then
      kill "${frontend_pid}" 2>/dev/null || true
    fi

    wait "${backend_pid}" 2>/dev/null || true
    wait "${frontend_pid}" 2>/dev/null || true

    exit "${status}"
  }

  trap 'cleanup 130' INT TERM
  trap 'cleanup 0' EXIT

  while true; do
    if ! kill -0 "${backend_pid}" 2>/dev/null; then
      local backend_status=0
      wait "${backend_pid}" || backend_status=$?
      echo "backend dev exited (${backend_status}), stopping frontend" >&2
      cleanup "${backend_status}"
    fi

    if ! kill -0 "${frontend_pid}" 2>/dev/null; then
      local frontend_status=0
      wait "${frontend_pid}" || frontend_status=$?
      echo "frontend dev exited (${frontend_status}), stopping backend" >&2
      cleanup "${frontend_status}"
    fi

    sleep 1
  done
}

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <install|lint|test|typecheck|build|check|dev>" >&2
  exit 2
fi

case "$1" in
  install)
    run_backend install
    run_frontend install
    ;;
  lint)
    run_backend lint
    run_frontend lint
    ;;
  test)
    run_backend test
    run_frontend test
    ;;
  typecheck)
    run_backend typecheck
    run_frontend typecheck
    ;;
  build)
    run_frontend build
    ;;
  check)
    run_backend lint
    run_backend test
    run_backend typecheck
    run_frontend lint
    run_frontend test
    run_frontend typecheck
    run_frontend build
    ;;
  dev)
    run_dev
    ;;
  *)
    echo "unknown workspace action: $1" >&2
    exit 2
    ;;
esac
