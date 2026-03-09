"""MCP tool definitions for AI News Radio."""

from mcp.types import Tool, ToolAnnotations

STEP_NAMES = ["collection", "factcheck", "analysis", "script", "voice", "video", "publish"]


def get_tool_definitions() -> list[Tool]:
    """Return all MCP tool definitions."""
    return [
        # ---- Episode Lifecycle ----
        Tool(
            name="create_episode",
            description="Create a new episode with 7 pipeline steps initialized (all pending). Returns the episode with its pipeline steps.",
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Episode title"},
                },
                "required": ["title"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        Tool(
            name="create_episode_from_articles",
            description=(
                "Create an episode with pre-selected articles. "
                "The collection step is auto-approved. Use after search_news to pass curated articles."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Episode title"},
                    "articles": {
                        "type": "array",
                        "description": "List of news articles",
                        "items": {
                            "type": "object",
                            "properties": {
                                "title": {"type": "string", "description": "Article headline"},
                                "summary": {"type": "string", "description": "Article summary (optional)"},
                                "source_url": {"type": "string", "description": "Article URL"},
                                "source_name": {"type": "string", "description": "Source name (e.g. NHK, 熊本日日新聞)"},
                            },
                            "required": ["title", "source_url", "source_name"],
                        },
                        "minItems": 1,
                    },
                },
                "required": ["title", "articles"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        Tool(
            name="list_episodes",
            description="List all episodes with their current status and pipeline step summary.",
            inputSchema={"type": "object", "properties": {}},
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        # ---- Pipeline Operations ----
        Tool(
            name="get_episode_status",
            description=(
                "Get comprehensive episode status: pipeline steps with their statuses, "
                "and news items with fact-check scores and script status."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                },
                "required": ["episode_id"],
            },
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        Tool(
            name="run_step",
            description=(
                "Execute a pipeline step (runs in background). Returns immediately. "
                "Use get_episode_status to poll for completion. "
                "Steps must run in order: collection → factcheck → analysis → script → voice → video → publish. "
                "Previous step must be approved before running the next."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                    "step_name": {
                        "type": "string",
                        "enum": STEP_NAMES,
                        "description": "Pipeline step to execute",
                    },
                    "queries": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Search queries for collection step (optional, uses default if omitted)",
                    },
                },
                "required": ["episode_id", "step_name"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        Tool(
            name="approve_step",
            description="Approve a completed pipeline step (status must be needs_approval). Allows the next step to proceed.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                    "step_name": {
                        "type": "string",
                        "enum": STEP_NAMES,
                        "description": "Pipeline step to approve",
                    },
                },
                "required": ["episode_id", "step_name"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        Tool(
            name="reject_step",
            description="Reject a completed pipeline step (status must be needs_approval). The step can be re-run after rejection.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                    "step_name": {
                        "type": "string",
                        "enum": STEP_NAMES,
                        "description": "Pipeline step to reject",
                    },
                    "reason": {"type": "string", "description": "Rejection reason"},
                },
                "required": ["episode_id", "step_name", "reason"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        Tool(
            name="get_step_detail",
            description="Get detailed input/output data for a specific pipeline step. Useful for reviewing step results before approval.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                    "step_name": {
                        "type": "string",
                        "enum": STEP_NAMES,
                        "description": "Pipeline step name",
                    },
                },
                "required": ["episode_id", "step_name"],
            },
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        # ---- Research ----
        Tool(
            name="search_news",
            description=(
                "Search for news articles using Brave Search. "
                "Returns titles, URLs, descriptions, and age. "
                "Use the results to select articles for create_episode_from_articles."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search query (supports Japanese)"},
                    "count": {
                        "type": "integer",
                        "description": "Number of results (default: 10, max: 20)",
                        "default": 10,
                    },
                    "freshness": {
                        "type": "string",
                        "enum": ["pd", "pw", "pm"],
                        "description": "Time filter: pd=past day, pw=past week, pm=past month",
                    },
                },
                "required": ["query"],
            },
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        # ---- Observability ----
        Tool(
            name="get_cost_stats",
            description="Get API cost statistics aggregated by provider and pipeline step.",
            inputSchema={
                "type": "object",
                "properties": {
                    "from_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                    "to_date": {"type": "string", "description": "End date (YYYY-MM-DD)"},
                    "episode_id": {"type": "integer", "description": "Filter by episode ID"},
                },
            },
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        Tool(
            name="health_check",
            description="Check if the AI News Radio backend is running and responsive.",
            inputSchema={"type": "object", "properties": {}},
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
    ]
