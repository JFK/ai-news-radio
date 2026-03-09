"""Pipeline engine singleton with registered steps."""

from app.pipeline.analyzer import AnalyzerStep
from app.pipeline.collector import CollectorStep
from app.pipeline.engine import PipelineEngine
from app.pipeline.factchecker import FactcheckerStep
from app.pipeline.scriptwriter import ScriptwriterStep
from app.pipeline.video import VideoStep
from app.pipeline.voice import VoiceStep

engine = PipelineEngine()
engine.register_step(CollectorStep)
engine.register_step(FactcheckerStep)
engine.register_step(AnalyzerStep)
engine.register_step(ScriptwriterStep)
engine.register_step(VoiceStep)
engine.register_step(VideoStep)

__all__ = [
    "AnalyzerStep",
    "CollectorStep",
    "FactcheckerStep",
    "PipelineEngine",
    "ScriptwriterStep",
    "VideoStep",
    "VoiceStep",
    "engine",
]
