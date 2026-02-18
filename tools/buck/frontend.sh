#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="${SYNEXTRA_REPO_ROOT:-$PWD}"
if [[ ! -d "${REPO_ROOT}/frontend" && -d "${SCRIPT_DIR}/../../frontend" ]]; then
  REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
fi
if [[ ! -d "${REPO_ROOT}/frontend" && -n "${BUCK_PROJECT_ROOT:-}" && -d "${BUCK_PROJECT_ROOT}/frontend" ]]; then
  REPO_ROOT="${BUCK_PROJECT_ROOT}"
fi
FRONTEND_DIR="${REPO_ROOT}/frontend"

if [[ ! -d "${FRONTEND_DIR}" ]]; then
  echo "frontend module not found: ${FRONTEND_DIR}" >&2
  exit 1
fi

if [[ $# -ne 1 ]]; then
  echo "usage: $0 <install|lint|test|typecheck|build|dev>" >&2
  exit 2
fi

cd "${FRONTEND_DIR}"

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
  local frontend_port="${PORT:-3000}"
  local launcher_pid="${PPID}"
  local known_port_pids
  local frontend_pid=0
  local frontend_pgid=""

  known_port_pids="$(get_listening_pids "${frontend_port}")"

  cleanup_dev() {
    local status="${1:-0}"

    trap - INT TERM EXIT

    if [[ "${frontend_pid}" -gt 0 ]]; then
      if [[ -n "${frontend_pgid}" ]]; then
        kill -TERM -- "-${frontend_pgid}" 2>/dev/null || true
      else
        kill -TERM "${frontend_pid}" 2>/dev/null || true
      fi

      sleep 1

      if [[ -n "${frontend_pgid}" ]]; then
        if kill -0 -- "-${frontend_pgid}" 2>/dev/null; then
          kill -KILL -- "-${frontend_pgid}" 2>/dev/null || true
        fi
      else
        if kill -0 "${frontend_pid}" 2>/dev/null; then
          kill -KILL "${frontend_pid}" 2>/dev/null || true
        fi
      fi

      wait "${frontend_pid}" 2>/dev/null || true
    fi

    kill_new_listeners "${frontend_port}" "${known_port_pids}" TERM
    kill_new_listeners "${frontend_port}" "${known_port_pids}" KILL

    exit "${status}"
  }

  trap 'cleanup_dev 130' INT TERM
  trap 'cleanup_dev $?' EXIT

  if command -v setsid >/dev/null 2>&1; then
    setsid npm run dev --host &
    frontend_pid=$!
    frontend_pgid="${frontend_pid}"
  else
    npm run dev --host &
    frontend_pid=$!
  fi

  while true; do
    if ! kill -0 "${frontend_pid}" 2>/dev/null; then
      set +e
      wait "${frontend_pid}"
      local status=$?
      set -e

      frontend_pid=0
      frontend_pgid=""

      return "${status}"
    fi

    if ! kill -0 "${launcher_pid}" 2>/dev/null; then
      echo "frontend launcher process ${launcher_pid} exited; stopping dev server" >&2
      cleanup_dev 1
    fi

    sleep 1
  done
}

has_npm_script() {
  node -e 'const fs=require("fs");const p=JSON.parse(fs.readFileSync("package.json","utf8"));process.exit(p.scripts&&p.scripts[process.argv[1]]?0:1)' "$1"
}

case "$1" in
install)
  npm install
  ;;
lint)
  npm run lint
  ;;
test)
  if has_npm_script test; then
    npm run test
  else
    echo "frontend test script is not defined in package.json" >&2
    exit 2
  fi
  ;;
typecheck)
  if has_npm_script typecheck; then
    npm run typecheck
  else
    echo "frontend typecheck script is not defined in package.json" >&2
    exit 2
  fi
  ;;
build)
  npm run build
  ;;
dev)
  run_dev_server
  ;;
*)
  echo "unknown frontend action: $1" >&2
  exit 2
  ;;
esac
