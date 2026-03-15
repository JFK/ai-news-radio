"""MCP server implementation for AI News Radio."""

import json
import logging

from mcp.server import Server
from mcp.types import TextContent, Tool

from mcp_server.client import AINewsRadioClient, APIError
from mcp_server.tools import STEP_NAMES, get_tool_definitions

logger = logging.getLogger(__name__)

server = Server("ai-news-radio")
client = AINewsRadioClient()


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Return available tools."""
    return get_tool_definitions()


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch tool calls to handlers."""
    try:
        result = await _dispatch(name, arguments or {})
        return [TextContent(type="text", text=result)]
    except APIError as e:
        return [TextContent(type="text", text=f"Error: {e.detail}")]
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return [TextContent(type="text", text=f"Error: {e}")]


async def _dispatch(name: str, args: dict) -> str:
    """Route tool name to handler and return formatted text."""
    match name:
        case "health_check":
            return await _health_check()
        case "create_episode":
            return await _create_episode(args)
        case "create_episode_from_articles":
            return await _create_episode_from_articles(args)
        case "delete_episode":
            return await _delete_episode(args)
        case "list_episodes":
            return await _list_episodes()
        case "get_episode_status":
            return await _get_episode_status(args)
        case "run_step":
            return await _run_step(args)
        case "approve_step":
            return await _approve_step(args)
        case "reject_step":
            return await _reject_step(args)
        case "get_step_detail":
            return await _get_step_detail(args)
        case "edit_item_script":
            return await _edit_item_script(args)
        case "edit_episode_script":
            return await _edit_episode_script(args)
        case "add_reading":
            return await _add_reading(args)
        case "list_readings":
            return await _list_readings()
        case "delete_reading":
            return await _delete_reading(args)
        case "search_news":
            return await _search_news(args)
        case "get_cost_stats":
            return await _get_cost_stats(args)
        case "toggle_complete":
            return await _toggle_complete(args)
        case "export_to_drive":
            return await _export_to_drive(args)
        case _:
            return f"Unknown tool: {name}"


# ---- Handlers ----


async def _health_check() -> str:
    data = await client.health()
    return f"Backend status: {data.get('status', 'unknown')}"


async def _create_episode(args: dict) -> str:
    ep = await client.create_episode(args["title"])
    return _format_episode(ep)


async def _create_episode_from_articles(args: dict) -> str:
    ep = await client.create_episode_from_articles(args["title"], args["articles"])
    return _format_episode(ep)


async def _delete_episode(args: dict) -> str:
    episode_id = args["episode_id"]
    await client.delete_episode(episode_id)
    return f"Episode #{episode_id} deleted successfully."


async def _list_episodes() -> str:
    data = await client.list_episodes()
    episodes = data.get("episodes", [])
    if not episodes:
        return "No episodes found."

    lines = [f"Episodes ({data.get('total', len(episodes))} total):", ""]
    for ep in episodes:
        steps = ep.get("pipeline_steps", [])
        step_summary = _step_summary(steps)
        lines.append(f"  #{ep['id']} [{ep['status']}] {ep['title']}")
        lines.append(f"    Steps: {step_summary}")
        lines.append("")
    return "\n".join(lines)


async def _get_episode_status(args: dict) -> str:
    episode_id = args["episode_id"]
    ep = await client.get_episode(episode_id)
    news_items = await client.get_news_items(episode_id)

    lines = [
        f"Episode #{ep['id']}: {ep['title']}",
        f"Status: {ep['status']}",
        f"Created: {ep.get('created_at', 'N/A')}",
        "",
        "Pipeline Steps:",
    ]

    for step in ep.get("pipeline_steps", []):
        status = step["status"]
        icon = _status_icon(status)
        line = f"  {icon} {step['step_name']}: {status}"
        if step.get("started_at") and not step.get("completed_at"):
            line += " (running...)"
        elif step.get("completed_at"):
            line += f" (completed: {step['completed_at']})"
        if step.get("rejection_reason"):
            line += f" — reason: {step['rejection_reason']}"
        lines.append(line)

    if news_items:
        active = [i for i in news_items if not i.get("excluded")]
        excluded = [i for i in news_items if i.get("excluded")]
        lines.extend(["", f"News Items ({len(active)}):"])
        for item in active:
            fc = ""
            if item.get("fact_check_score") is not None:
                fc = f" [fact-check: {item['fact_check_score']}/5]"
            script = " [script: ready]" if item.get("script_text") else ""
            lines.append(f"  - {item['title']}{fc}{script}")
            lines.append(f"    {item['source_name']}: {item['source_url']}")
        if excluded:
            lines.extend(["", f"Excluded Items ({len(excluded)}):"])
            for item in excluded:
                step = item.get("excluded_at_step", "?")
                lines.append(f"  x {item['title']} (excluded at: {step})")
                lines.append(f"    {item['source_name']}: {item['source_url']}")

    return "\n".join(lines)


async def _run_step(args: dict) -> str:
    episode_id = args["episode_id"]
    step_name = args["step_name"]
    queries = args.get("queries")

    step = await client.run_step(episode_id, step_name, queries)

    lines = [
        f"Step '{step_name}' started for episode #{episode_id}.",
        f"Status: {step['status']}",
        "",
        "The step is running in the background.",
        "Use get_episode_status to check for completion.",
    ]
    return "\n".join(lines)


async def _approve_step(args: dict) -> str:
    episode_id = args["episode_id"]
    step_name = args["step_name"]
    excluded_item_ids = args.get("excluded_item_ids")

    step_id = await client.resolve_step_id(episode_id, step_name)
    step = await client.approve_step(step_id, excluded_item_ids)

    next_step = _next_step(step_name)
    lines = [f"Step '{step_name}' approved for episode #{episode_id}."]
    if excluded_item_ids:
        lines.append(f"Excluded {len(excluded_item_ids)} item(s): {excluded_item_ids}")
    if next_step:
        lines.append(f"Next step: run_step with step_name='{next_step}'")
    else:
        lines.append("This was the final step. Episode pipeline is complete.")
    return "\n".join(lines)


async def _reject_step(args: dict) -> str:
    episode_id = args["episode_id"]
    step_name = args["step_name"]
    reason = args["reason"]

    step_id = await client.resolve_step_id(episode_id, step_name)
    await client.reject_step(step_id, reason)

    return f"Step '{step_name}' rejected for episode #{episode_id}.\nReason: {reason}\nYou can re-run this step with run_step."


async def _get_step_detail(args: dict) -> str:
    episode_id = args["episode_id"]
    step_name = args["step_name"]

    steps = await client.get_steps(episode_id)
    step = None
    for s in steps:
        if s["step_name"] == step_name:
            step = s
            break

    if not step:
        return f"Step '{step_name}' not found for episode #{episode_id}."

    lines = [
        f"Step: {step_name} (Episode #{episode_id})",
        f"Status: {step['status']}",
        f"Started: {step.get('started_at', 'N/A')}",
        f"Completed: {step.get('completed_at', 'N/A')}",
    ]

    if step.get("input_data"):
        lines.extend(["", "Input Data:", json.dumps(step["input_data"], ensure_ascii=False, indent=2)])

    if step.get("output_data"):
        lines.extend(["", "Output Data:", json.dumps(step["output_data"], ensure_ascii=False, indent=2)])

    if step.get("rejection_reason"):
        lines.extend(["", f"Rejection Reason: {step['rejection_reason']}"])

    return "\n".join(lines)


async def _edit_item_script(args: dict) -> str:
    result = await client.edit_item_script(args["episode_id"], args["news_item_id"], args["script_text"])
    return (
        f"Script updated for news item #{result['news_item_id']}.\n"
        f"Length: {result['old_length']} → {result['new_length']} chars"
    )


async def _edit_episode_script(args: dict) -> str:
    result = await client.edit_episode_script(args["episode_id"], args["episode_script"])
    return f"Episode script updated.\nLength: {result['old_length']} → {result['new_length']} chars"


async def _add_reading(args: dict) -> str:
    entry = await client.add_reading(args["surface"], args["reading"], args.get("priority", 0))
    return f"Added: {entry['surface']} → {entry['reading']} (id: {entry['id']}, priority: {entry['priority']})"


async def _list_readings() -> str:
    entries = await client.list_readings()
    if not entries:
        return "No pronunciation dictionary entries."

    lines = [f"Pronunciation Dictionary ({len(entries)} entries):", ""]
    for e in entries:
        lines.append(f"  [{e['id']}] {e['surface']} → {e['reading']} (priority: {e['priority']})")
    return "\n".join(lines)


async def _delete_reading(args: dict) -> str:
    entry_id = args["id"]
    await client.delete_reading(entry_id)
    return f"Deleted dictionary entry #{entry_id}."


async def _search_news(args: dict) -> str:
    query = args["query"]
    count = args.get("count", 10)
    freshness = args.get("freshness")

    results = await client.search_news(query, count, freshness)

    if not results:
        return f"No results found for '{query}'."

    lines = [f"Search results for '{query}' ({len(results)} results):", ""]
    for i, r in enumerate(results, 1):
        lines.append(f"{i}. {r['title']}")
        lines.append(f"   URL: {r['url']}")
        if r.get("description"):
            lines.append(f"   {r['description']}")
        if r.get("age"):
            lines.append(f"   Age: {r['age']}")
        lines.append("")

    lines.append("Use create_episode_from_articles to create an episode with selected articles.")
    return "\n".join(lines)


async def _toggle_complete(args: dict) -> str:
    ep = await client.toggle_complete(args["episode_id"])
    return f"Episode #{ep['id']} status changed to: {ep['status']}"


async def _export_to_drive(args: dict) -> str:
    result = await client.export_to_drive(args["episode_id"])
    return (
        f"Exported episode #{result['episode_id']} analysis to Google Drive.\n"
        f"File URL: {result['drive_file_url']}\n"
        f"Source text length: {result['source_text_length']} chars"
    )


async def _get_cost_stats(args: dict) -> str:
    episode_id = args.get("episode_id")

    if episode_id:
        data = await client.get_episode_cost(episode_id)
        lines = [
            f"Cost Stats for Episode #{episode_id}:",
            f"Total: ${data['total_cost_usd']:.4f} ({data['total_requests']} requests)",
        ]
    else:
        data = await client.get_cost_stats(args.get("from_date"), args.get("to_date"))
        lines = [
            "Cost Stats:",
            f"Total: ${data['total_cost_usd']:.4f} ({data['total_requests']} requests)",
        ]

    if data.get("by_provider"):
        lines.extend(["", "By Provider:"])
        for p in data["by_provider"]:
            lines.append(f"  {p['provider']}: ${p['total_cost_usd']:.4f} ({p['request_count']} requests)")

    if data.get("by_step"):
        lines.extend(["", "By Step:"])
        for s in data["by_step"]:
            lines.append(f"  {s['step_name']}: ${s['total_cost_usd']:.4f} ({s['request_count']} requests)")

    return "\n".join(lines)


# ---- Formatting helpers ----


def _format_episode(ep: dict) -> str:
    """Format a single episode response."""
    lines = [
        f"Episode #{ep['id']} created.",
        f"Title: {ep['title']}",
        f"Status: {ep['status']}",
        "",
        "Pipeline Steps:",
    ]
    for step in ep.get("pipeline_steps", []):
        icon = _status_icon(step["status"])
        lines.append(f"  {icon} {step['step_name']}: {step['status']}")
    return "\n".join(lines)


def _status_icon(status: str) -> str:
    """Return a text icon for step status."""
    return {
        "pending": "[ ]",
        "running": "[~]",
        "needs_approval": "[?]",
        "approved": "[v]",
        "rejected": "[x]",
    }.get(status, "[-]")


def _step_summary(steps: list[dict]) -> str:
    """One-line summary of step statuses."""
    if not steps:
        return "no steps"
    parts = []
    for s in steps:
        icon = _status_icon(s["status"])
        parts.append(f"{icon}{s['step_name']}")
    return " ".join(parts)


def _next_step(step_name: str) -> str | None:
    """Return the next step in the pipeline, or None if last."""
    try:
        idx = STEP_NAMES.index(step_name)
        if idx + 1 < len(STEP_NAMES):
            return STEP_NAMES[idx + 1]
    except ValueError:
        pass
    return None
