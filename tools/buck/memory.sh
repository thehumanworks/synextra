#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_NAME="$HOME/projects/synextra-main"

# Accept as arguments `sessions` or `messages`
# - `sessions` needs no additional arguments
# - `messages` needs a session ID
# - `last-messages` looks up the most recent session and fetches its messages
if [[ $# -lt 1 ]]; then
  echo "usage: $0 <sessions|messages|last-messages> [session_id]" >&2
  exit 2
fi

get_latest_session_id() {
  local sessions_output="$1"
  local session_id

  session_id="$(printf '%s\n' "$sessions_output" | tail -n +2 | awk '
    /"session_id"[[:space:]]*:/ {
      gsub(/^.*"session_id"[[:space:]]*:[[:space:]]*"/, "")
      gsub(/".*$/, "")
      print
      exit
    }
  ')"

  if [[ -z "$session_id" ]]; then
    session_id="$(printf '%s\n' "$sessions_output" | tail -n +2 | \
      grep -m1 -oE "[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")"
  fi

  printf '%s' "$session_id"
}

case "$1" in
sessions)
  mmr sessions --limit 10 --project "${PROJECT_NAME}" --pretty --source=codex
  ;;
messages)
  if [[ $# -lt 2 ]]; then
    echo "usage: $0 messages <session_id>" >&2
    exit 2
  fi
  SESSION_ID="${2}"
  mmr messages --session="${SESSION_ID}" --pretty --source=codex
  ;;
last-messages)
  SESSIONS_OUTPUT="$(mmr sessions --limit 1 --project "${PROJECT_NAME}" --pretty --source=codex)"
  SESSION_ID="$(get_latest_session_id "$SESSIONS_OUTPUT")"
  if [[ -z "$SESSION_ID" ]]; then
    echo "no sessions found" >&2
    exit 1
  fi
  mmr messages --session="${SESSION_ID}" --pretty --source=codex
  ;;
*)
  echo "unknown memory action: $1" >&2
  exit 2
  ;;
esac
