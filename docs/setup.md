# Setup Guide

AI News Radio のセットアップガイド。[Claude Code](https://claude.com/claude-code) がセットアップを自動で行います。

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| [Claude Code](https://claude.com/claude-code) | Latest | **必須** — セットアップ・運用に使用 |
| Docker | 24+ | Docker Compose v2 plugin 含む |
| Python | 3.12+ | venv + MCP サーバー用 |
| Git | 2.30+ | |
| RAM | 8 GB | |
| Disk | 80 GB SSD | Docker images + media files |

**Docker のインストール:**
- Ubuntu: https://docs.docker.com/engine/install/ubuntu/
- Windows (WSL2): https://docs.docker.com/desktop/install/windows-install/
- macOS: https://docs.docker.com/desktop/install/mac-install/

## API Keys

事前に取得しておくとスムーズです。

| Provider | Console URL | Required |
|----------|-------------|----------|
| Brave Search | https://brave.com/search/api/ | Yes（ニュース収集・ファクトチェック） |
| Anthropic | https://console.anthropic.com/settings/keys | AI プロバイダー（いずれか1つ） |
| OpenAI | https://platform.openai.com/api-keys | AI プロバイダー（いずれか1つ） |
| Google | https://aistudio.google.com/apikey | AI プロバイダー（いずれか1つ） |

## Setup with Claude Code

```bash
git clone https://github.com/JFK/ai-news-radio.git
cd ai-news-radio
claude
# 「セットアップして」と入力
```

Claude Code が以下を順番に実行します:

### Step 0: 動作環境チェック

以下を確認し、不足があれば案内します:

- Docker Engine が起動しているか（`docker info`）
- docker compose v2 が使えるか（`docker compose version`）
- Python 3.12+ があるか（`python3 --version`）
- Git があるか（`git --version`）
- ポートの空き: 3000, 8000, 5432, 6379, 50021

### Step 1: Python venv + 依存インストール

```bash
python3 -m venv venv
source venv/bin/activate
pip install -e backend/
```

### Step 2: .env 作成

`.env.example` をコピーし、対話形式で設定します:

1. **AI プロバイダー**（anthropic / openai / google）
2. **API キー**（選択したプロバイダー + Brave Search）
3. **TTS プロバイダー**（voicevox / openai / google）
4. **画像生成**（static / google）

プロバイダー別の推奨モデル:

| Provider | Model |
|----------|-------|
| Anthropic | `claude-sonnet-4-20250514` |
| OpenAI | `gpt-5.2` |
| Google | `gemini-2.5-pro` |

### Step 3: Docker 起動 + DB マイグレーション

```bash
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

### Step 4: ヘルスチェック

- Backend: http://localhost:8000/api/health → `{"status":"ok"}`
- Frontend: http://localhost:3000

### Step 5: MCP サーバー設定

`.mcp.json` を生成し、Claude Code から MCP ツールでパイプラインを操作できるようにします。

```json
{
  "mcpServers": {
    "ai-news-radio": {
      "type": "stdio",
      "command": "<project>/venv/bin/python",
      "args": ["-m", "mcp_server"],
      "cwd": "<project>/backend",
      "env": {
        "AINEWSRADIO_BACKEND_URL": "http://localhost:8000",
        "PYTHONPATH": "<project>/backend"
      }
    }
  }
}
```

`<project>` はリポジトリの絶対パスに置き換わります。

設定後、Claude Code を再起動すると MCP ツール（`search_news`, `create_episode`, `run_step` 等）が使えるようになります。

## Environment Variables Reference

### Database & Queue

| Variable | Default | Description |
|----------|---------|-------------|
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/ainewsradio` | PostgreSQL connection string |
| `REDIS_URL` | `redis://redis:6379/0` | Redis connection string |

### AI Provider

| Variable | Default | Description |
|----------|---------|-------------|
| `DEFAULT_AI_PROVIDER` | `openai` | Default AI provider (`anthropic`, `openai`, `google`) |
| `DEFAULT_AI_MODEL` | `gpt-5.2` | Default model |
| `PIPELINE_FACTCHECK_PROVIDER` | (default) | Provider for fact-check step |
| `PIPELINE_FACTCHECK_MODEL` | (default) | Model for fact-check step |
| `PIPELINE_ANALYSIS_PROVIDER` | (default) | Provider for analysis step |
| `PIPELINE_ANALYSIS_MODEL` | (default) | Model for analysis step |
| `PIPELINE_SCRIPT_PROVIDER` | (default) | Provider for script step |
| `PIPELINE_SCRIPT_MODEL` | (default) | Model for script step |

### API Keys

| Variable | Description |
|----------|-------------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `OPENAI_API_KEY` | OpenAI API key |
| `GOOGLE_API_KEY` | Google AI API key |
| `BRAVE_SEARCH_API_KEY` | Brave Search API key |

### News Collection

| Variable | Default | Description |
|----------|---------|-------------|
| `COLLECTION_METHOD` | `brave` | Collection method |
| `COLLECTION_QUERIES` | `熊本 ニュース,...` | Comma-separated search queries |

### Voice / TTS

| Variable | Default | Description |
|----------|---------|-------------|
| `PIPELINE_VOICE_PROVIDER` | `voicevox` | TTS provider (`voicevox`, `openai`, `elevenlabs`, `google`) |
| `VOICEVOX_HOST` | `http://voicevox:50021` | VOICEVOX engine URL |
| `VOICEVOX_SPEAKER_ID` | `3` | VOICEVOX character ID |
| `OPENAI_TTS_MODEL` | `tts-1` | OpenAI TTS model |
| `OPENAI_TTS_VOICE` | `alloy` | OpenAI TTS voice |
| `ELEVENLABS_API_KEY` | | ElevenLabs API key |
| `GOOGLE_TTS_VOICE` | `ja-JP-Neural2-B` | Google Cloud TTS voice |
| `GOOGLE_TTS_LANGUAGE_CODE` | `ja-JP` | Google Cloud TTS language |

### Visual / Video

| Variable | Default | Description |
|----------|---------|-------------|
| `VISUAL_PROVIDER` | `static` | Image generation (`static` or `google`) |
| `VISUAL_IMAGEN_MODEL` | `imagen-4.0-fast-generate-001` | Imagen model |
| `MEDIA_DIR` | `/app/media` | Directory for generated media files |

## Troubleshooting

### Port conflicts

```bash
# Find what's using a port
lsof -i :8000
# Or: ss -tlnp | grep 8000
```

### Database migration errors

```bash
# Reset the database completely
docker compose down -v
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

### Container won't start

```bash
# Check logs
docker compose logs backend
docker compose logs db

# Rebuild from scratch
docker compose down
docker compose build --no-cache
docker compose up -d
```
