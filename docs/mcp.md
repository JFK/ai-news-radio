# MCP Integration Guide

AI News Radio includes a [Model Context Protocol (MCP)](https://modelcontextprotocol.io/) server, allowing AI assistants like Claude Code to control the entire pipeline programmatically.

## What is MCP?

MCP is an open protocol that lets AI assistants interact with external tools and services. With the AI News Radio MCP server, you can create episodes, run pipeline steps, review results, and approve/reject steps — all from your AI assistant.

## Prerequisites

- AI News Radio backend running (via `docker compose up`)
- Python 3.12+ with `mcp` package installed
- An MCP-compatible client (e.g., Claude Code, Claude Desktop)

## Setup

### 1. Copy the example configuration

```bash
cp .mcp.json.example .mcp.json
```

### 2. Update paths

Edit `.mcp.json` and replace `/path/to/ai-news-radio` with your actual project path:

```json
{
  "mcpServers": {
    "ai-news-radio": {
      "type": "stdio",
      "command": "python",
      "args": ["-m", "mcp_server"],
      "cwd": "/home/youruser/ai-news-radio/backend",
      "env": {
        "AINEWSRADIO_BACKEND_URL": "http://localhost:8000",
        "PYTHONPATH": "/home/youruser/ai-news-radio/backend"
      }
    }
  }
}
```

### 3. Verify

Ask your AI assistant to run the `health_check` tool. It should return `{"status": "ok"}`.

## Available Tools

| Tool | Category | Description | Read-Only |
|------|----------|-------------|-----------|
| `health_check` | System | Check if the backend is running | Yes |
| `search_news` | Research | Search for news articles via Brave Search | Yes |
| `create_episode` | Episode | Create a new episode with 7 pipeline steps | No |
| `create_episode_from_articles` | Episode | Create an episode from pre-selected articles | No |
| `list_episodes` | Episode | List all episodes with status summary | Yes |
| `get_episode_status` | Episode | Get detailed episode status with all steps and news items | Yes |
| `run_step` | Pipeline | Execute a pipeline step (async) | No |
| `approve_step` | Pipeline | Approve a completed step | No |
| `reject_step` | Pipeline | Reject a completed step with a reason | No |
| `get_step_detail` | Pipeline | Get detailed input/output data for a step | Yes |
| `get_cost_stats` | Observability | Get API cost statistics by provider and step | Yes |

## Workflow Example

A typical end-to-end workflow:

### 1. Search for news

```
search_news(query="熊本 ニュース", count=10)
```

### 2. Create an episode from selected articles

```
create_episode_from_articles(
  title="熊本ニュース 2026-03-09",
  articles=[
    {"title": "...", "source_url": "https://...", "source_name": "熊本日日新聞"},
    {"title": "...", "source_url": "https://...", "source_name": "NHK熊本"}
  ]
)
```

The collection step is automatically approved when using `create_episode_from_articles`.

### 3. Run each step sequentially

```
run_step(episode_id=1, step_name="factcheck")
```

### 4. Poll for completion

```
get_episode_status(episode_id=1)
```

Wait until the step status changes from `running` to `needs_approval`.

### 5. Review before approving

```
get_step_detail(episode_id=1, step_name="factcheck")
```

Review the output data to verify quality.

### 6. Approve and continue

```
approve_step(episode_id=1, step_name="factcheck")
run_step(episode_id=1, step_name="analysis")
```

### 7. Repeat for remaining steps

Continue the `run_step` → `get_step_detail` → `approve_step` cycle for: `analysis` → `script` → `voice` → `video` → `publish`.

## Tips

- **Async steps**: `run_step` returns immediately. Use `get_episode_status` to poll for completion. Voice and video steps can take a while.
- **Review before approval**: Always use `get_step_detail` to inspect results before approving. This is especially important for fact-check scores and script content.
- **Rejection and re-run**: If a step's output is unsatisfactory, use `reject_step` with a reason, then `run_step` again. The step will re-execute from scratch.
- **Cost monitoring**: Use `get_cost_stats` periodically to track API spending.
- **Step order**: Steps must run in order. The previous step must be approved before running the next one.
