"""Tests for VoiceStep pipeline step."""

import io
import os
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Episode, StepName
from app.pipeline.engine import PipelineEngine
from app.pipeline.voice import VoiceStep


def _make_wav_bytes(duration_frames: int = 100, sample_rate: int = 24000) -> bytes:
    """Create minimal valid WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * duration_frames)
    return buf.getvalue()


@pytest.fixture
def voice_step() -> VoiceStep:
    return VoiceStep()


class TestVoiceStep:
    def test_step_name(self, voice_step: VoiceStep):
        assert voice_step.step_name == StepName.VOICE

    @patch("app.pipeline.voice.get_tts_provider")
    @patch("app.pipeline.voice.settings")
    async def test_execute_generates_audio(
        self,
        mock_settings,
        mock_get_provider,
        voice_step: VoiceStep,
        session: AsyncSession,
        tmp_path,
    ):
        """execute() should generate audio and update Episode.audio_path."""
        # Setup
        engine = PipelineEngine()
        episode = await engine.create_episode("Test Episode", session)
        episode_id = episode.id

        mock_settings.media_dir = str(tmp_path)
        mock_settings.pipeline_voice_provider = "voicevox"

        wav_bytes = _make_wav_bytes(24000)  # 1 second of audio

        mock_provider = MagicMock()
        mock_provider.audio_format = "wav"
        mock_provider.synthesize = AsyncMock(return_value=wav_bytes)
        mock_get_provider.return_value = mock_provider

        input_data = {"episode_script": "健軍（けんぐん）駐屯地でテストの台本です。音声を生成します。"}

        # Execute
        result = await voice_step.execute(episode_id, input_data, session)

        # Verify reading hints were expanded for TTS
        synth_call = mock_provider.synthesize
        tts_text = synth_call.call_args[0][0]
        assert "けんぐん駐屯地" in tts_text
        assert "健軍（けんぐん）" not in tts_text

        # Verify output
        assert "audio_path" in result
        assert result["audio_format"] == "wav"
        assert result["provider"] == "voicevox"
        assert result["duration_seconds"] > 0

        # Verify file was written
        audio_file = os.path.join(str(tmp_path), str(episode_id), "audio.wav")
        assert os.path.exists(audio_file)

        # Verify Episode.audio_path was updated
        db_result = await session.execute(select(Episode).where(Episode.id == episode_id))
        episode = db_result.scalar_one()
        assert episode.audio_path == f"{episode_id}/audio.wav"

    async def test_execute_raises_on_empty_script(self, voice_step: VoiceStep, session: AsyncSession):
        """execute() should raise ValueError when episode_script is empty."""
        with pytest.raises(ValueError, match="No episode_script"):
            await voice_step.execute(1, {}, session)

        with pytest.raises(ValueError, match="No episode_script"):
            await voice_step.execute(1, {"episode_script": ""}, session)
