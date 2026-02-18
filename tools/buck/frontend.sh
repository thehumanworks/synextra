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
  npm run dev --host
  ;;
*)
  echo "unknown frontend action: $1" >&2
  exit 2
  ;;
esac
