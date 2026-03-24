#!/usr/bin/env bash
# Session start: check backend health and report pending episodes.
set -euo pipefail

BACKEND_URL="${AINEWSRADIO_BACKEND_URL:-http://localhost:8000}"

# Health check
HEALTH=$(curl -s --connect-timeout 3 "${BACKEND_URL}/api/health" 2>/dev/null || echo '{"status":"unreachable"}')
HEALTH_STATUS=$(echo "$HEALTH" | jq -r '.status // "unreachable"')

if [ "$HEALTH_STATUS" != "ok" ]; then
  echo "WARNING: Backend not reachable (status: ${HEALTH_STATUS}). Start with: docker compose up -d"
  exit 0
fi

# Check for episodes needing attention
EPISODES=$(curl -s --connect-timeout 5 "${BACKEND_URL}/api/episodes" 2>/dev/null || echo '[]')
TOTAL=$(echo "$EPISODES" | jq 'if type == "array" then length else 0 end')

PENDING=0
RUNNING=0
for row in $(echo "$EPISODES" | jq -r '.[]? | @base64' 2>/dev/null); do
  EP=$(echo "$row" | base64 -d)
  EP_ID=$(echo "$EP" | jq -r '.id')
  EP_STATUS=$(echo "$EP" | jq -r '.status')

  if [ "$EP_STATUS" = "in_progress" ]; then
    DETAIL=$(curl -s --connect-timeout 3 "${BACKEND_URL}/api/episodes/${EP_ID}" 2>/dev/null || echo '{}')
    P=$(echo "$DETAIL" | jq '[.pipeline_steps[]? | select(.status == "needs_approval")] | length' 2>/dev/null || echo 0)
    R=$(echo "$DETAIL" | jq '[.pipeline_steps[]? | select(.status == "running")] | length' 2>/dev/null || echo 0)
    PENDING=$((PENDING + P))
    RUNNING=$((RUNNING + R))
  fi
done

OUTPUT="Backend: OK | Episodes: ${TOTAL}"
[ "$PENDING" -gt 0 ] && OUTPUT="${OUTPUT} | Pending approvals: ${PENDING}"
[ "$RUNNING" -gt 0 ] && OUTPUT="${OUTPUT} | Running steps: ${RUNNING}"
echo "$OUTPUT"
