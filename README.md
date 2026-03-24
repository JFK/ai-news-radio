[日本語版はこちら](README.ja.md)

# AI News Radio

A web application that automates the entire news broadcast pipeline — from collection to YouTube publishing — with AI-powered fact-checking, critical analysis, and script generation.

**"Not just reading the news. A radio that thinks with you."**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6.svg)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)

## Features

- **6-step pipeline** — Collection → Fact-check → Analysis → Script → Voice → Video
- **Human approval gates** — Every step requires human review before proceeding
- **Multi AI provider** — Anthropic Claude / OpenAI GPT / Google Gemini, switchable per step
- **Multi TTS provider** — Gemini TTS / VOICEVOX / OpenAI TTS / ElevenLabs / Google Cloud TTS
- **Brave Search integration** — Web search for news collection and fact-checking
- **YouTube Data API v3** — Search YouTube videos as news sources (opt-in)
- **Multi-source analysis** — Excel/PDF/image parsing, YouTube transcript extraction
- **Media bias analysis** — 2-axis evaluation (political leaning / power structure) per news source
- **note.com article generation** — Markdown articles with YouTube embeds, episode info, and auto-generated hashtags
- **Deep research** — Multi-round AI investigation with academic paper search (Semantic Scholar + arXiv)
- **Foreign news translation** — Auto-detect language (CJK heuristic) → AI translate + Japanese context
- **Cost tracking** — Token usage and cost visualization on the dashboard
- **Google Drive export** — Export analysis results as NotebookLM source text
- **WebUI settings** — Manage all settings from the browser (API keys, providers, prompts, etc.)
- **MCP integration** — Control the entire pipeline from AI assistants like Claude Code
- **i18n** — English and Japanese frontend

## Architecture

```
[1. Collect] → ✅ → [2. Fact-check] → ✅ → [3. Analyze] → ✅ → [4. Script] → ✅ → [5. Voice] → ✅ → [6. Video]
```

Each `✅` is a human approval gate. No step proceeds without explicit approval.

## Requirements

| Resource | Minimum |
|----------|---------|
| OS | Ubuntu 22.04+ / WSL2 / macOS |
| CPU | 4 vCPU |
| RAM | 8 GB |
| Disk | 80 GB SSD |
| Docker | Docker Engine 24+ / Docker Compose v2 |
| Python | 3.12+ |
| **[Claude Code](https://claude.com/claude-code)** | **Required for setup & operation** |

**Required API keys** (at least one AI provider):

| Service | Purpose | Required |
|---------|---------|----------|
| [Brave Search](https://brave.com/search/api/) | News collection & fact-check | Yes |
| [OpenAI](https://platform.openai.com/) | AI (GPT) / TTS | One AI provider required |
| [Anthropic](https://console.anthropic.com/) | AI (Claude) | One AI provider required |
| [Google AI](https://aistudio.google.com/) | AI (Gemini) / TTS / Imagen | One AI provider required |
| [YouTube Data API v3](https://console.cloud.google.com/apis/library/youtube.googleapis.com) | YouTube video search | Optional |

## Quick Start

This project uses **[Claude Code](https://claude.com/claude-code)** for setup, development, and pipeline operation via MCP.

```bash
# 1. Clone
git clone https://github.com/JFK/ai-news-radio.git
cd ai-news-radio

# 2. Launch Claude Code and say "セットアップして"
claude
```

Claude Code will automatically:
- Check prerequisites (Docker, Python, ports)
- Create Python venv and install dependencies
- Prompt for AI provider selection and API keys
- Generate the `.env` file
- Start all Docker services and run migrations
- Configure MCP server for pipeline control

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Frontend | React 19 (Vite) + TypeScript + Tailwind CSS |
| Database | PostgreSQL 16 + SQLAlchemy (async) + Alembic |
| Queue | Celery + Redis |
| AI | Anthropic Claude / OpenAI / Google Gemini |
| TTS | Gemini TTS / VOICEVOX / OpenAI / ElevenLabs / Google Cloud |
| Video | FFmpeg |
| Search | Brave Search API |
| Infra | Docker Compose |

## MCP Integration

AI News Radio includes a built-in [MCP (Model Context Protocol)](https://modelcontextprotocol.io/) server, enabling AI assistants like Claude Code to control the entire pipeline programmatically.

See [docs/mcp.md](docs/mcp.md) for setup and usage.

## Documentation

| Document | Description |
|----------|-------------|
| [docs/setup.md](docs/setup.md) | Detailed setup guide |
| [docs/architecture.md](docs/architecture.md) | Architecture overview |
| [docs/mcp.md](docs/mcp.md) | MCP integration guide |
| [CONTRIBUTING.md](CONTRIBUTING.md) | Contribution guidelines |

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[Apache License 2.0](LICENSE)

## Credits

- Text-to-speech: [VOICEVOX](https://voicevox.hiroshiba.jp/)
- News search: [Brave Search API](https://brave.com/search/api/)
