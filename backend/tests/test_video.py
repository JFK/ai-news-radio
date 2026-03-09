"""Tests for VideoStep pipeline step."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import PipelineStep, StepName, StepStatus
from app.pipeline.engine import PipelineEngine
from app.pipeline.video import VideoStep


@pytest.fixture
def video_step() -> VideoStep:
    return VideoStep()


class TestVideoStep:
    def test_step_name(self, video_step: VideoStep):
        assert video_step.step_name == StepName.VIDEO

    async def test_execute_raises_on_missing_audio(self, video_step: VideoStep):
        """execute() should raise ValueError when audio_path is missing."""
        with pytest.raises(ValueError, match="No audio_path"):
            await video_step.execute(1, {})

        with pytest.raises(ValueError, match="No audio_path"):
            await video_step.execute(1, {"audio_path": ""})

    @patch("app.pipeline.video.async_session")
    @patch("app.pipeline.video.settings")
    @patch("app.pipeline.video.asyncio.create_subprocess_exec")
    async def test_execute_calls_ffmpeg(
        self,
        mock_subprocess,
        mock_settings,
        mock_session_factory,
        video_step: VideoStep,
        session: AsyncSession,
        tmp_path,
    ):
        """execute() should call FFmpeg and ffprobe."""
        # Setup
        engine = PipelineEngine()
        episode = await engine.create_episode("Test Episode", session)
        episode_id = episode.id

        # Create a script step with output_data
        from sqlalchemy import select

        result = await session.execute(
            select(PipelineStep).where(
                PipelineStep.episode_id == episode_id,
                PipelineStep.step_name == StepName.SCRIPT,
            )
        )
        script_step = result.scalar_one()
        script_step.output_data = {"episode_script": "テストの台本です。"}
        script_step.status = StepStatus.APPROVED
        await session.commit()

        # Create dummy audio file
        audio_dir = tmp_path / str(episode_id)
        audio_dir.mkdir()
        audio_file = audio_dir / "audio.wav"
        audio_file.write_bytes(b"fake-audio-data")

        mock_settings.media_dir = str(tmp_path)

        mock_ctx = AsyncMock()
        mock_ctx.__aenter__ = AsyncMock(return_value=session)
        mock_ctx.__aexit__ = AsyncMock(return_value=False)
        mock_session_factory.return_value = mock_ctx

        # Mock ffprobe (first call) and ffmpeg (second call)
        ffprobe_proc = AsyncMock()
        ffprobe_proc.returncode = 0
        ffprobe_proc.communicate.return_value = (
            b'{"format": {"duration": "10.5"}}',
            b"",
        )

        ffmpeg_proc = AsyncMock()
        ffmpeg_proc.returncode = 0
        ffmpeg_proc.communicate.return_value = (b"", b"")

        mock_subprocess.side_effect = [ffprobe_proc, ffmpeg_proc]

        input_data = {"audio_path": f"{episode_id}/audio.wav"}

        # Execute
        result = await video_step.execute(episode_id, input_data)

        # Verify
        assert result["video_path"] == f"{episode_id}/video.mp4"
        assert result["duration_seconds"] == 10.5
        assert mock_subprocess.call_count == 2

        # First call should be ffprobe
        first_call_args = mock_subprocess.call_args_list[0][0]
        assert first_call_args[0] == "ffprobe"

        # Second call should be ffmpeg
        second_call_args = mock_subprocess.call_args_list[1][0]
        assert second_call_args[0] == "ffmpeg"

    def test_escape_drawtext(self, video_step: VideoStep):
        """Test FFmpeg drawtext text escaping."""
        text = "Hello: World's\nTest"
        escaped = video_step._escape_drawtext(text)
        assert "\\:" in escaped
        assert "\\n" in escaped
        assert "\\'" in escaped
