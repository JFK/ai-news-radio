import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.episodes import router as episodes_router
from app.api.health import router as health_router
from app.api.pipeline import router as pipeline_router
from app.api.stats import router as stats_router
from app.config import settings

app = FastAPI(title="AI News Radio", version="0.1.0")

# Serve media files (audio/video)
try:
    os.makedirs(settings.media_dir, exist_ok=True)
    app.mount("/media", StaticFiles(directory=settings.media_dir), name="media")
except OSError:
    pass  # media_dir not writable (e.g., in tests)

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
