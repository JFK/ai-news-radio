"""MCP tool definitions for AI News Radio."""

from mcp.types import Tool, ToolAnnotations

STEP_NAMES = ["collection", "factcheck", "analysis", "script", "voice", "video"]


def get_tool_definitions() -> list[Tool]:
    """Return all MCP tool definitions."""
    return [
        # ---- Episode Lifecycle ----
        Tool(
            name="create_episode",
            description="Create a new episode with 6 pipeline steps initialized (all pending). Returns the episode with its pipeline steps.",
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
            name="delete_episode",
            description="Delete an episode and all related data (news items, pipeline steps, API usage, media files). Cannot delete if a step is running.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID to delete"},
                },
                "required": ["episode_id"],
            },
            annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False),
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
                "Steps must run in order: collection → factcheck → analysis → script → voice → video. "
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
                    "tts_model": {
                        "type": "string",
                        "description": "Override TTS model for voice step (e.g., gemini-2.5-flash-preview-tts, gemini-2.5-pro-preview-tts)",
                    },
                    "tts_voice": {
                        "type": "string",
                        "description": "Override TTS voice for voice step (e.g., Kore, Puck, Charon, Fenrir, Aoede, Leda, Orus, Zephyr)",
                    },
                    "video_targets": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": ["all", "images", "video", "metadata", "shorts"],
                        },
                        "description": "Partial re-run targets for video step. Options: all (full re-run, default), images (background/thumbnail/illustrations), video (frames+SRT+encode), metadata (YouTube metadata), shorts (short videos). First run must use 'all'.",
                    },
                },
                "required": ["episode_id", "step_name"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        Tool(
            name="approve_step",
            description=(
                "Approve a completed pipeline step (status must be needs_approval). "
                "Optionally exclude specific news items by passing their IDs. "
                "Excluded items will be skipped in subsequent steps."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                    "step_name": {
                        "type": "string",
                        "enum": STEP_NAMES,
                        "description": "Pipeline step to approve",
                    },
                    "excluded_item_ids": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "News item IDs to exclude from this step onwards (optional)",
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
        # ---- Script Editing ----
        Tool(
            name="edit_item_script",
            description="Edit the script text for a single news item. Script step must be needs_approval or approved. If voice step was approved, it will be reset to pending.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                    "news_item_id": {"type": "integer", "description": "News item ID"},
                    "script_text": {"type": "string", "description": "New script text"},
                },
                "required": ["episode_id", "news_item_id", "script_text"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        Tool(
            name="edit_episode_script",
            description="Edit the full episode script (opening + all news + transitions + ending). Script step must be needs_approval or approved. If voice step was approved, it will be reset to pending.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                    "episode_script": {"type": "string", "description": "New full episode script text"},
                },
                "required": ["episode_id", "episode_script"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        # ---- Pronunciation Dictionary ----
        Tool(
            name="add_reading",
            description="Add a pronunciation entry to the reading dictionary. Used for proper nouns that TTS mispronounces.",
            inputSchema={
                "type": "object",
                "properties": {
                    "surface": {"type": "string", "description": "Written form (e.g. 健軍)"},
                    "reading": {"type": "string", "description": "Reading in hiragana/katakana (e.g. けんぐん)"},
                    "priority": {
                        "type": "integer",
                        "description": "Priority (higher = matched first, default: 0). Use higher values for longer compound words.",
                        "default": 0,
                    },
                },
                "required": ["surface", "reading"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        Tool(
            name="list_readings",
            description="List all pronunciation dictionary entries.",
            inputSchema={"type": "object", "properties": {}},
            annotations=ToolAnnotations(readOnlyHint=True),
        ),
        Tool(
            name="delete_reading",
            description="Delete a pronunciation dictionary entry by ID.",
            inputSchema={
                "type": "object",
                "properties": {
                    "id": {"type": "integer", "description": "Dictionary entry ID"},
                },
                "required": ["id"],
            },
            annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False),
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
        # ---- Episode Status ----
        Tool(
            name="toggle_complete",
            description="Toggle episode status between in_progress and completed. Use this to mark an episode as done (e.g., after export) without running all pipeline steps, or to reopen a completed episode.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                },
                "required": ["episode_id"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
        # ---- Export ----
        Tool(
            name="export_to_drive",
            description="Export episode analysis results to Google Drive as NotebookLM source text. Analysis step must be approved. Google Drive must be enabled and authenticated.",
            inputSchema={
                "type": "object",
                "properties": {
                    "episode_id": {"type": "integer", "description": "Episode ID"},
                },
                "required": ["episode_id"],
            },
            annotations=ToolAnnotations(destructiveHint=False, readOnlyHint=False),
        ),
    ]
