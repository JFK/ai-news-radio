# Architecture

This document describes the system architecture of AI News Radio.

## System Overview

AI News Radio is a web application that automates the entire workflow from news collection to YouTube publishing, with AI-powered fact-checking, critical analysis, and script generation. Every step includes a human approval gate to ensure quality.

```
┌─────────────┐    ┌─────────┐    ┌───────────┐    ┌──────────┐
│  Frontend   │───▶│ Backend │───▶│ PostgreSQL│    │  Redis   │
│  React/Vite │◀───│ FastAPI │◀───│    16     │    │  (queue) │
└─────────────┘    └────┬────┘    └───────────┘    └────┬─────┘
                        │                               │
                   ┌────┴────────────────────────┐     │
                   │       Pipeline Steps         │◀────┘
                   │  (Celery async workers)      │
                   └────┬───────┬───────┬────────┘
                        │       │       │
                   ┌────┴──┐ ┌─┴────┐ ┌┴───────┐
                   │  AI   │ │ TTS  │ │ Search │
                   │Provid.│ │Provid│ │(Brave) │
                   └───────┘ └──────┘ └────────┘
```

## Pipeline (7 Steps)

```
[1. Collection] → ✅ → [2. Fact-check] → ✅ → [3. Analysis] → ✅ → [4. Script] → ✅ → [5. Voice] → ✅ → [6. Video] → ✅ → [7. Publish]
```

Each `✅` represents a **human approval gate**. No step proceeds to the next without explicit approval.

| # | Step | Name | AI | Description |
|---|------|------|----|-------------|
| 1 | Collection | `collection` | — | Web search via Brave Search API, deduplication, filtering |
| 2 | Fact-check | `factcheck` | Yes (+web) | Source credibility scoring, cross-referencing, verification URLs |
| 3 | Analysis | `analysis` | Yes | Background context, multiple perspectives, data validation, impact assessment |
| 4 | Script | `script` | Yes | Radio script with critical thinking + accessibility integrated |
| 5 | Voice | `voice` | — | Text-to-speech synthesis (VOICEVOX / OpenAI / ElevenLabs / Google) |
| 6 | Video | `video` | — | FFmpeg: audio + background → MP4 |
| 7 | Publish | `publish` | — | YouTube Data API v3 upload |

### Step State Machine

```
pending → running → needs_approval → approved → (next step)
                                   → rejected → pending (can re-run)
```

- **pending**: Waiting to be executed
- **running**: Currently executing (async via Celery)
- **needs_approval**: Completed, waiting for human review
- **approved**: Approved by human, next step can proceed
- **rejected**: Rejected by human with a reason, can be re-run

## Data Model

```
Episode (1 broadcast)
├── NewsItem[] (individual articles)
│   ├── fact_check_score (1-5)
│   ├── analysis_data (JSON)
│   └── script_text
├── PipelineStep[] (7 steps)
│   ├── status
│   ├── input_data (JSON)
│   └── output_data (JSON)
└── ApiUsage[] (cost tracking)
    ├── provider, model
    ├── input_tokens, output_tokens
    └── cost_usd
```

### Key Relationships

- **Episode** has many **NewsItem** records (the articles in this broadcast)
- **Episode** has exactly 7 **PipelineStep** records (one per step)
- **Episode** has many **ApiUsage** records (one per AI API call)
- Each step's `output_data` becomes the next step's `input_data`

## Docker Compose Services

| Service | Image | Port | Description |
|---------|-------|------|-------------|
| `backend` | Custom (FastAPI) | 8000 | API server |
| `frontend` | Custom (Vite/React) | 3000 | Dashboard UI |
| `db` | postgres:16 | 5432 | Primary database |
| `redis` | redis:7-alpine | 6379 | Celery message broker |
| `celery-worker` | Custom (same as backend) | — | Async task worker |
| `voicevox` | voicevox/voicevox_engine:cpu-latest | 50021 | TTS engine |

## AI Provider Abstraction

The system supports multiple AI providers through an abstraction layer (`backend/app/services/ai_provider.py`).

```python
class AIProvider(ABC):
    async def generate(prompt, model, system=None, **kwargs) -> AIResponse
    async def web_search(query, **kwargs) -> SearchResult
```

**Supported providers:**
- **Anthropic** — Claude models (default)
- **OpenAI** — GPT models
- **Google** — Gemini models

Each pipeline step can use a different provider/model via environment variables:

```
PIPELINE_FACTCHECK_PROVIDER=anthropic
PIPELINE_FACTCHECK_MODEL=claude-sonnet-4-20250514
PIPELINE_ANALYSIS_PROVIDER=openai
PIPELINE_ANALYSIS_MODEL=gpt-4o
```

## TTS Provider Abstraction

Text-to-speech is also provider-agnostic (`backend/app/services/tts_provider.py`).

```python
class TTSProvider(ABC):
    async def synthesize(text: str) -> bytes
    async def health_check() -> bool
    @property
    def audio_format() -> str  # "wav" or "mp3"
```

**Supported providers:**
- **VOICEVOX** — Local, free, Japanese-optimized (default)
- **OpenAI** — OpenAI TTS API
- **ElevenLabs** — ElevenLabs API
- **Google** — Google Cloud TTS

## Cost Tracking

Every AI API call records token usage to the `ApiUsage` table:
- Provider and model used
- Input/output token counts
- Estimated cost in USD

The dashboard visualizes costs by provider, by step, and by episode, with date range filtering.

## API Endpoints

### Episodes (`/api/episodes`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/episodes` | Create a new episode |
| POST | `/episodes/from-articles` | Create episode from pre-selected articles |
| GET | `/episodes` | List all episodes |
| GET | `/episodes/{id}` | Get episode details |
| GET | `/episodes/{id}/news-items` | Get news items for an episode |

### Pipeline (`/api/episodes/{id}/steps`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/episodes/{id}/steps` | List pipeline steps |
| POST | `/episodes/{id}/steps/{step_name}/run` | Execute a step |
| POST | `/steps/{id}/approve` | Approve a step |
| POST | `/steps/{id}/reject` | Reject a step |

### Stats (`/api/stats`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/stats/costs` | Overall cost statistics (with date filter) |
| GET | `/stats/costs/episodes/{id}` | Per-episode cost statistics |

### Search (`/api/search`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/search/news` | Search news via Brave Search |

### Pricing (`/api/pricing`)

| Method | Path | Description |
|--------|------|-------------|
| GET | `/pricing` | List model pricing entries |
| POST | `/pricing` | Create pricing entry |
| PUT | `/pricing/{id}` | Update pricing entry |
| DELETE | `/pricing/{id}` | Delete pricing entry |

### Health

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
