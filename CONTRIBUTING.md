# Contributing to AI News Radio

Thank you for your interest in contributing! This guide will help you get started.

## Development Setup

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/ai-news-radio.git
cd ai-news-radio
```

### 2. Start the development environment

```bash
cp .env.example .env
# Edit .env with your API keys
docker compose up -d --build
docker compose exec backend alembic upgrade head
```

See [docs/setup.md](docs/setup.md) for detailed instructions.

### 3. Verify

- Frontend: http://localhost:3000
- Backend: http://localhost:8000/api/health

## Code Style

### Python (Backend)

- **Formatter/Linter**: [Ruff](https://docs.astral.sh/ruff/)
- **Target**: Python 3.12
- **Line length**: 120
- **Type hints**: Required on all public functions
- **Docstrings**: Required on all public functions

```bash
# Check
docker compose exec backend ruff check app/

# Format
docker compose exec backend ruff format app/
```

### TypeScript (Frontend)

- **Linter**: ESLint
- **Formatter**: Prettier (via ESLint)

```bash
docker compose exec frontend npm run lint
```

## Testing

### Backend

```bash
# Run all tests
docker compose exec backend pytest

# With coverage
docker compose exec backend pytest --cov=app

# Specific test file
docker compose exec backend pytest tests/test_pipeline.py
```

- Framework: pytest
- Async mode: `asyncio_mode = "auto"` (no need for `@pytest.mark.asyncio`)
- Test database: Uses aiosqlite (in-memory SQLite)

### Frontend

```bash
docker compose exec frontend npm run lint
```

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
feat: add Google TTS provider support
fix: correct token count in cost calculation
docs: update setup guide for GPU VOICEVOX
refactor: extract common pipeline logic to base class
test: add factchecker unit tests
```

## Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feat/your-feature
   ```

2. Make your changes with tests if applicable.

3. Ensure linting and tests pass:
   ```bash
   docker compose exec backend ruff check app/
   docker compose exec backend pytest
   ```

4. Push and create a PR targeting `main`.

5. Reference the related issue in your PR description (e.g., `Closes #42`).

6. A maintainer will review your PR. Please respond to feedback promptly.

## Project Structure

See [docs/architecture.md](docs/architecture.md) for a detailed architecture overview.

Key directories:

```
backend/
├── app/
│   ├── api/          # FastAPI route handlers
│   ├── models/       # SQLAlchemy models
│   ├── pipeline/     # Pipeline step implementations
│   └── services/     # AI, TTS, and external service integrations
├── mcp_server/       # MCP server for AI assistant integration
└── tests/

frontend/
└── src/
    ├── components/   # React components
    ├── api/          # API client
    ├── hooks/        # Custom React hooks
    └── types/        # TypeScript type definitions
```

## License

By contributing, you agree that your contributions will be licensed under the [Apache License 2.0](LICENSE).
