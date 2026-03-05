from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.episodes import router as episodes_router
from app.api.health import router as health_router
from app.api.pipeline import router as pipeline_router
from app.api.stats import router as stats_router

app = FastAPI(title="AI News Radio", version="0.1.0")

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
