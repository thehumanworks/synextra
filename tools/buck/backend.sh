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

get_listening_pids() {
  local port="$1"

  if command -v lsof >/dev/null 2>&1; then
    lsof -tiTCP:"${port}" -sTCP:LISTEN 2>/dev/null || true
    return
  fi

  if command -v ss >/dev/null 2>&1; then
    ss -ltnp "sport = :${port}" 2>/dev/null \
      | awk -F '[=, ]+' 'NR > 1 {for (i = 1; i <= NF; i++) if ($i == "pid") print $(i + 1)}' \
      | sed '/^$/d' || true
  fi
}

pid_in_list() {
  local pid="$1"
  local pid_list="$2"

  if [[ -z "${pid_list}" ]]; then
    return 1
  fi

  printf '%s\n' "${pid_list}" | grep -Fxq -- "${pid}"
}

kill_new_listeners() {
  local port="$1"
  local known_pids="$2"
  local signal_name="${3:-TERM}"
  local current_pid
  local current_pids

  current_pids="$(get_listening_pids "${port}")"

  while IFS= read -r current_pid; do
    if [[ -z "${current_pid}" ]]; then
      continue
    fi
    if pid_in_list "${current_pid}" "${known_pids}"; then
      continue
    fi
    kill "-${signal_name}" "${current_pid}" 2>/dev/null || true
  done <<< "${current_pids}"
}

run_dev_server() {
  local backend_port="${SYNEXTRA_BACKEND_PORT:-8000}"
  local known_port_pids
  local backend_pid=0
  local backend_pgid=""

  known_port_pids="$(get_listening_pids "${backend_port}")"

  cleanup_dev() {
    local status="${1:-0}"

    trap - INT TERM EXIT

    if [[ "${backend_pid}" -gt 0 ]]; then
      if [[ -n "${backend_pgid}" ]]; then
        kill -TERM -- "-${backend_pgid}" 2>/dev/null || true
      else
        kill -TERM "${backend_pid}" 2>/dev/null || true
      fi

      sleep 1

      if [[ -n "${backend_pgid}" ]]; then
        kill -KILL -- "-${backend_pgid}" 2>/dev/null || true
      else
        kill -KILL "${backend_pid}" 2>/dev/null || true
      fi

      wait "${backend_pid}" 2>/dev/null || true
    fi

    kill_new_listeners "${backend_port}" "${known_port_pids}" TERM
    kill_new_listeners "${backend_port}" "${known_port_pids}" KILL

    exit "${status}"
  }

  trap 'cleanup_dev 130' INT TERM
  trap 'cleanup_dev $?' EXIT

  if command -v setsid >/dev/null 2>&1; then
    setsid uv run uvicorn synextra_backend.app:app --reload &
    backend_pid=$!
    backend_pgid="${backend_pid}"
  else
    uv run uvicorn synextra_backend.app:app --reload &
    backend_pid=$!
  fi

  wait "${backend_pid}"
}

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
    run_dev_server
    ;;
  *)
    echo "unknown backend action: $1" >&2
    exit 2
    ;;
esac
