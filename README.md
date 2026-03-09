[日本語版はこちら](README.ja.md)

# AI News Radio

A web application that automates the entire news broadcast pipeline — from collection to YouTube publishing — with AI-powered fact-checking, critical analysis, and script generation.

**"Not just reading the news. A radio that thinks with you."**

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12+-3776AB.svg)](https://python.org)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6.svg)](https://typescriptlang.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)](https://docs.docker.com/compose/)

## Features

- **7-step pipeline** — Collection → Fact-check → Analysis → Script → Voice → Video → Publish
- **Human approval gates** — Every step requires human review before proceeding
- **Multi AI provider** — Anthropic Claude / OpenAI GPT / Google Gemini, switchable per step
- **Multi TTS provider** — VOICEVOX / OpenAI TTS / ElevenLabs / Google Cloud TTS
- **Brave Search integration** — Web search for news collection and fact-checking
- **Cost tracking** — Token usage and cost visualization on the dashboard
- **MCP integration** — Control the entire pipeline from AI assistants like Claude Code
- **i18n** — English and Japanese frontend

## Architecture

```
[1. Collect] → ✅ → [2. Fact-check] → ✅ → [3. Analyze] → ✅ → [4. Script] → ✅ → [5. Voice] → ✅ → [6. Video] → ✅ → [7. Publish]
```

Each `✅` is a human approval gate. No step proceeds without explicit approval.

## Quick Start

```bash
# 1. Clone
git clone https://github.com/JFK/ai-news-radio.git
cd ai-news-radio

# 2. Run the interactive setup script
chmod +x setup.sh
./setup.sh
```

The setup script will:
- Check prerequisites (Docker, docker compose, Git)
- Prompt for AI provider selection and API keys
- Generate the `.env` file
- Start all Docker services
- Run database migrations
- Verify the health check

For manual setup, see [docs/setup.md](docs/setup.md).

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Backend | Python 3.12 + FastAPI |
| Frontend | React 19 (Vite) + TypeScript + Tailwind CSS |
| Database | PostgreSQL 16 + SQLAlchemy (async) + Alembic |
| Queue | Celery + Redis |
| AI | Anthropic Claude / OpenAI / Google Gemini |
| TTS | VOICEVOX / OpenAI / ElevenLabs / Google Cloud |
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
