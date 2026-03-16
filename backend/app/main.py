import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.dictionary import router as dictionary_router
from app.api.episodes import router as episodes_router
from app.api.google_auth import router as google_auth_router
from app.api.health import router as health_router
from app.api.pipeline import router as pipeline_router
from app.api.pricing import router as pricing_router
from app.api.prompts import router as prompts_router
from app.api.search import router as search_router
from app.api.settings import router as settings_router
from app.api.speakers import router as speakers_router
from app.api.stats import router as stats_router
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load persisted settings from DB into in-memory config on startup."""
    from app.config import load_settings_from_db
    from app.database import async_session

    try:
        async with async_session() as session:
            await load_settings_from_db(session)
    except Exception:
        pass  # DB may not be ready yet (first run before migrations)
    yield


app = FastAPI(title="AI News Radio", version="0.1.0", lifespan=lifespan)

# Serve media files (audio/video)
try:
    os.makedirs(settings.media_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
except OSError:
    pass  # media_dir not writable (e.g., in tests)

# Serve SE preset files (built-in)
_se_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "se")
if os.path.isdir(_se_dir):
    app.mount("/static/se", StaticFiles(directory=_se_dir), name="se")

# Serve custom SE files (user uploads in media/se/)
_custom_se_dir = os.path.join(settings.media_dir, "se")
os.makedirs(_custom_se_dir, exist_ok=True)
app.mount("/media/se", StaticFiles(directory=_custom_se_dir), name="custom_se")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix="/api")
app.include_router(episodes_router, prefix="/api")
app.include_router(pipeline_router, prefix="/api")
app.include_router(stats_router, prefix="/api")
app.include_router(pricing_router, prefix="/api")
app.include_router(search_router, prefix="/api")
app.include_router(prompts_router, prefix="/api")
app.include_router(settings_router, prefix="/api")
app.include_router(dictionary_router, prefix="/api")
app.include_router(speakers_router, prefix="/api")
app.include_router(google_auth_router, prefix="/api")


