#!/usr/bin/env bash
# Poll pipeline step completion after run_step is called.
set -euo pipefail

INPUT=$(cat)
EPISODE_ID=$(echo "$INPUT" | jq -r '.tool_input.episode_id // empty')
STEP_NAME=$(echo "$INPUT" | jq -r '.tool_input.step_name // empty')

if [ -z "$EPISODE_ID" ] || [ -z "$STEP_NAME" ]; then
  exit 0
fi

BACKEND_URL="${AINEWSRADIO_BACKEND_URL:-http://localhost:8000}"
MAX_ATTEMPTS=40
ATTEMPT=0

while [ $ATTEMPT -lt $MAX_ATTEMPTS ]; do
  sleep 15
  ATTEMPT=$((ATTEMPT + 1))

  RESPONSE=$(curl -s --connect-timeout 5 "${BACKEND_URL}/api/episodes/${EPISODE_ID}" 2>/dev/null || echo '{}')
  STATUS=$(echo "$RESPONSE" | jq -r ".pipeline_steps[]? | select(.step_name == \"${STEP_NAME}\") | .status" 2>/dev/null || echo "unknown")

  case "$STATUS" in
    needs_approval)
      echo "Step '${STEP_NAME}' for episode #${EPISODE_ID} completed and needs approval."
      exit 0
      ;;
    pending)
      echo "Step '${STEP_NAME}' for episode #${EPISODE_ID} failed (reset to pending). Check get_episode_status for errors."
      exit 0
      ;;
    running)
      ;;
    approved|rejected)
      echo "Step '${STEP_NAME}' for episode #${EPISODE_ID} is already ${STATUS}."
      exit 0
      ;;
  esac
done

echo "Step '${STEP_NAME}' for episode #${EPISODE_ID} still running after 10 minutes. Check manually."
