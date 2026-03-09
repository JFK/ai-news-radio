# Setup Guide

Complete guide for setting up AI News Radio.

## Prerequisites

| Requirement | Minimum | Notes |
|-------------|---------|-------|
| Docker | 20.10+ | With Docker Compose v2 plugin |
| Git | 2.30+ | |
| RAM | 4 GB | VOICEVOX needs ~1-2 GB |
| Disk | 10 GB | For Docker images and media files |

## API Keys

You'll need at least one AI provider key and (optionally) a Brave Search key.

| Provider | Console URL | Required |
|----------|-------------|----------|
| Anthropic | https://console.anthropic.com/settings/keys | If using Claude |
| OpenAI | https://platform.openai.com/api-keys | If using GPT |
| Google | https://aistudio.google.com/apikey | If using Gemini |
| Brave Search | https://brave.com/search/api/ | For news collection & fact-checking |
| ElevenLabs | https://elevenlabs.io/app/settings/api-keys | If using ElevenLabs TTS |

## Quick Install (Automated)

The interactive setup script handles everything:

```bash
git clone https://github.com/JFK/ai-news-radio.git
cd ai-news-radio
chmod +x setup.sh
./setup.sh
```

The script will:
1. Check prerequisites (Docker, docker compose, Git)
2. Ask you to select an AI provider and enter API keys
3. Ask you to select a TTS provider
4. Generate `.env` from `.env.example`
5. Start all Docker services
6. Run database migrations
7. Verify the health check

## Manual Install

### 1. Clone and configure

```bash
git clone https://github.com/JFK/ai-news-radio.git
cd ai-news-radio
cp .env.example .env
```

### 2. Edit `.env`

Set your AI provider and API keys:

```bash
# Choose: anthropic, openai, or google
DEFAULT_AI_PROVIDER=anthropic
DEFAULT_AI_MODEL=claude-sonnet-4-20250514

# Set the API key for your chosen provider
ANTHROPIC_API_KEY=sk-ant-...

# Optional: Brave Search for news collection
BRAVE_SEARCH_API_KEY=BSA...
```

### 3. Start services

```bash
docker compose up -d --build
```

### 4. Run database migrations

```bash
docker compose exec backend alembic upgrade head
```

### 5. Verify

```bash
curl http://localhost:8000/api/health
# → {"status":"ok"}
```

Open http://localhost:3000 in your browser.

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
| `DEFAULT_AI_MODEL` | `gpt-5` | Default model |
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
| `ELEVENLABS_VOICE_ID` | `21m00Tcm4TlvDq8ikWAM` | ElevenLabs voice ID |
| `ELEVENLABS_MODEL_ID` | `eleven_multilingual_v2` | ElevenLabs model |
| `GOOGLE_TTS_VOICE` | `ja-JP-Neural2-B` | Google Cloud TTS voice |
| `GOOGLE_TTS_LANGUAGE_CODE` | `ja-JP` | Google Cloud TTS language |

### Media & YouTube

| Variable | Default | Description |
|----------|---------|-------------|
| `MEDIA_DIR` | `/app/media` | Directory for generated media files |
| `YOUTUBE_CLIENT_ID` | | YouTube OAuth client ID |
| `YOUTUBE_CLIENT_SECRET` | | YouTube OAuth client secret |

## GPU VOICEVOX

To use GPU-accelerated VOICEVOX (significantly faster synthesis), edit `docker-compose.yml`:

```yaml
voicevox:
  image: voicevox/voicevox_engine:nvidia-latest
  ports:
    - "50021:50021"
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: 1
            capabilities: [gpu]
```

Requires [NVIDIA Container Toolkit](https://docs.nvidia.com/datacenter/cloud-native/container-toolkit/install-guide.html).

## Troubleshooting

### Port conflicts

If ports 8000, 3000, 5432, 6379, or 50021 are already in use:

```bash
# Find what's using a port
lsof -i :8000

# Or change ports in docker-compose.yml
ports:
  - "8001:8000"  # Map to a different host port
```

### VOICEVOX slow first request

VOICEVOX loads its model into memory on the first synthesis request. The first request may take 30-60 seconds on CPU. Subsequent requests are much faster (5-15 seconds per sentence).

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

## Development

### Running tests

```bash
# Backend tests (pytest)
docker compose exec backend pytest

# With coverage
docker compose exec backend pytest --cov=app

# Frontend linting
docker compose exec frontend npm run lint
```

### Code formatting & linting

```bash
# Python (Ruff)
docker compose exec backend ruff check app/
docker compose exec backend ruff format app/

# TypeScript (ESLint)
docker compose exec frontend npm run lint
```
