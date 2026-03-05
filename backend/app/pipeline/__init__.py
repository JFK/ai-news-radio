"""Pipeline engine singleton with registered steps."""

from app.pipeline.collector import CollectorStep
from app.pipeline.engine import PipelineEngine

engine = PipelineEngine()
engine.register_step(CollectorStep)

__all__ = ["CollectorStep", "PipelineEngine", "engine"]
