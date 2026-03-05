"""Utility functions for pipeline steps."""

import json
import re


def parse_json_response(content: str) -> dict:
    """Extract JSON from an AI response.

    Tries in order:
    1. Direct JSON parse
    2. Extract from markdown code fences (```json ... ```)
    3. Find first {...} block in the text

    Raises:
        ValueError: If no valid JSON can be extracted.
    """
    # 1. Direct parse
    try:
        return json.loads(content)
    except (json.JSONDecodeError, TypeError):
        pass

    # 2. Markdown code fence
    fence_match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", content, re.DOTALL)
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # 3. First {...} block (handle nested braces)
    brace_match = re.search(r"\{", content)
    if brace_match:
        start = brace_match.start()
        depth = 0
        for i in range(start, len(content)):
            if content[i] == "{":
                depth += 1
            elif content[i] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        return json.loads(content[start : i + 1])
                    except json.JSONDecodeError:
                        break

    raise ValueError(f"Could not extract JSON from AI response: {content[:200]}")
