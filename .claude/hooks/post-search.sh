#!/usr/bin/env bash
# After search_news, remind about episode creation.
set -euo pipefail

INPUT=$(cat)
TOOL_OUTPUT=$(echo "$INPUT" | jq -r '.tool_output // empty')

if echo "$TOOL_OUTPUT" | grep -q "results)"; then
  RESULT_COUNT=$(echo "$TOOL_OUTPUT" | grep -oP '\((\d+) results\)' | grep -oP '\d+' || true)
  if [ -n "$RESULT_COUNT" ] && [ "$RESULT_COUNT" -gt 0 ]; then
    echo "${RESULT_COUNT} results found. Ask the user which articles to include in an episode."
  fi
fi
