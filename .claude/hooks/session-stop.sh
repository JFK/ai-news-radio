#!/usr/bin/env bash
# Before session ends, check for pending work.
set -euo pipefail

BACKEND_URL="${AINEWSRADIO_BACKEND_URL:-http://localhost:8000}"

EPISODES=$(curl -s --connect-timeout 3 "${BACKEND_URL}/api/episodes" 2>/dev/null || echo '[]')

AWAITING=""
for row in $(echo "$EPISODES" | jq -r '.[]? | @base64' 2>/dev/null); do
  EP=$(echo "$row" | base64 -d)
  EP_ID=$(echo "$EP" | jq -r '.id')
  EP_TITLE=$(echo "$EP" | jq -r '.title')
  EP_STATUS=$(echo "$EP" | jq -r '.status')

  if [ "$EP_STATUS" = "in_progress" ]; then
    DETAIL=$(curl -s --connect-timeout 3 "${BACKEND_URL}/api/episodes/${EP_ID}" 2>/dev/null || echo '{}')
    PENDING_STEPS=$(echo "$DETAIL" | jq -r '[.pipeline_steps[]? | select(.status == "needs_approval") | .step_name] | join(", ")' 2>/dev/null || true)
    if [ -n "$PENDING_STEPS" ]; then
      AWAITING="${AWAITING}\n  #${EP_ID} ${EP_TITLE}: ${PENDING_STEPS} awaiting approval"
    fi
  fi
done

if [ -n "$AWAITING" ]; then
  echo -e "Reminder — episodes with pending approvals:${AWAITING}"
fi
