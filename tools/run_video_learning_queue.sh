#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
VIDEO_LIMIT="${VIDEO_LIMIT:-34}"
LOG_FILE="${LOG_FILE:-$ROOT/14_KB_System/logs/video_learning/jianghushuo_top10x12_download_20260617.log}"
STATUS_FILE="${STATUS_FILE:-${LOG_FILE%.log}.status.json}"
PID_FILE="${PID_FILE:-${LOG_FILE%.log}.pid}"

mkdir -p "$(dirname "$LOG_FILE")"
: > "$LOG_FILE"
printf '%s\n' "$$" >"$PID_FILE"

write_status() {
  local status="$1"
  local exit_code="${2:-}"
  local updated_at
  updated_at="$(date '+%Y-%m-%dT%H:%M:%S')"
  {
    printf '{\n'
    printf '  "status": "%s",\n' "$status"
    printf '  "updated_at": "%s"' "$updated_at"
    if [[ -n "$exit_code" ]]; then
      printf ',\n  "exit_code": %s\n' "$exit_code"
    else
      printf '\n'
    fi
    printf '}\n'
  } >"$STATUS_FILE"
}

finish() {
  local exit_code=$?
  if [[ "$exit_code" -eq 0 ]]; then
    write_status "completed" "$exit_code"
  else
    write_status "failed" "$exit_code"
  fi
  exit "$exit_code"
}

trap finish EXIT
write_status "running"

heartbeat() {
  while true; do
    sleep 60
    write_status "running"
  done
}

heartbeat &
HEARTBEAT_PID="$!"

stop_heartbeat() {
  if [[ -n "${HEARTBEAT_PID:-}" ]]; then
    kill "$HEARTBEAT_PID" >/dev/null 2>&1 || true
  fi
}

trap 'stop_heartbeat; finish' EXIT

run_step() {
  printf '\n=== %s ===\n' "$*" >>"$LOG_FILE"
  "$@" >>"$LOG_FILE" 2>&1
}

cd "$ROOT"
run_step .venv/bin/python -m tools.video_learning learn --root . --analyze-video --video-limit "$VIDEO_LIMIT"
run_step .venv/bin/python -m tools.video_learning status --root .
