#!/usr/bin/env bash
# After approving a step, suggest the next pipeline step.
set -euo pipefail

INPUT=$(cat)
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_output // empty')
EPISODE_ID=$(echo "$INPUT" | jq -r '.tool_input.episode_id // empty')

if echo "$TOOL_OUTPUT" | grep -q "Next step:"; then
  NEXT_STEP=$(echo "$TOOL_OUTPUT" | grep -oP "step_name='\\K[^']+" || true)
  if [ -n "$NEXT_STEP" ] && [ -n "$EPISODE_ID" ]; then
    echo "Next step available: ${NEXT_STEP} for episode #${EPISODE_ID}. Ask the user if they want to proceed."
  fi
fi
