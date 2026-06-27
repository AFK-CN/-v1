#!/usr/bin/env bash
set -uo pipefail

ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
QUEUE="$ROOT/90_Temp/scratch/video_learning/queues/jianghushuo_all_directions_download.json"
LOG_FILE="${LOG_FILE:-$ROOT/00_System/runtime/logs/video_learning/jianghushuo_all_directions_download_20260618.log}"
STATUS_FILE="${STATUS_FILE:-${LOG_FILE%.log}.status.json}"
PID_FILE="${PID_FILE:-${LOG_FILE%.log}.pid}"

mkdir -p "$(dirname "$LOG_FILE")"
printf '%s\n' "$$" >"$PID_FILE"

write_status() {
  local status="$1"
  local completed="$2"
  local failed="$3"
  local current_source_id="${4:-}"
  printf '{"status":"%s","completed":%s,"failed":%s,"current_source_id":"%s","updated_at":"%s"}\n' \
    "$status" "$completed" "$failed" "$current_source_id" "$(date '+%Y-%m-%dT%H:%M:%S')" >"$STATUS_FILE"
}

update_item() {
  local source_id="$1"
  local status="$2"
  local temp_file
  temp_file="$(mktemp)"
  jq --arg id "$source_id" --arg status "$status" --arg updated "$(date '+%Y-%m-%dT%H:%M:%S')" \
    '(.items[] | select(.source_id == $id)) += {status: $status, updated_at: $updated}' \
    "$QUEUE" >"$temp_file" && mv "$temp_file" "$QUEUE"
}

completed=0
failed=0
write_status "running" "$completed" "$failed"
cd "$ROOT"

WORKLIST="$(mktemp)"
trap 'rm -f "$WORKLIST"' EXIT
jq -r '.items[] | select(.status == "pending" or .status == "failed") | .source_id' "$QUEUE" >"$WORKLIST"

while IFS= read -r source_id; do
  artifact_dir="$ROOT/00_System/runtime/cache/video_learning/video_artifacts/douyin_${source_id}"
  if [[ -s "$artifact_dir/source.mp4" && -s "$artifact_dir/transcript.srt" ]]; then
    update_item "$source_id" "complete_reused"
    completed=$((completed + 1))
    write_status "running" "$completed" "$failed"
    continue
  fi

  printf '\n=== %s %s ===\n' "$(date '+%Y-%m-%dT%H:%M:%S')" "$source_id" >>"$LOG_FILE"
  update_item "$source_id" "running"
  write_status "running" "$completed" "$failed" "$source_id"
  "$ROOT/.venv/bin/python" -m tools.video_learning learn --root "$ROOT" \
    --source-ids "$source_id" --analyze-video --video-limit 1 < /dev/null >>"$LOG_FILE" 2>&1 &
  child_pid="$!"
  while kill -0 "$child_pid" >/dev/null 2>&1; do
    write_status "running" "$completed" "$failed" "$source_id"
    sleep 15
  done
  wait "$child_pid" || true

  if [[ -s "$artifact_dir/source.mp4" && -s "$artifact_dir/transcript.srt" ]]; then
    update_item "$source_id" "completed"
    completed=$((completed + 1))
  else
    update_item "$source_id" "failed"
    failed=$((failed + 1))
  fi
  write_status "running" "$completed" "$failed"
done <"$WORKLIST"

if [[ "$failed" -gt 0 ]]; then
  write_status "completed_with_failures" "$completed" "$failed"
else
  write_status "completed" "$completed" "$failed"
fi
