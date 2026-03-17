"""Tests for VideoStep pipeline step."""

from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
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

    async def test_execute_raises_on_missing_audio(self, video_step: VideoStep, session: AsyncSession):
        """execute() should raise ValueError when audio_path is missing."""
        with pytest.raises(ValueError, match="No audio_path"):
            await video_step.execute(1, {}, session)

        with pytest.raises(ValueError, match="No audio_path"):
            await video_step.execute(1, {"audio_path": ""}, session)

    @patch("app.pipeline.video.get_visual_provider")
    @patch("app.pipeline.video.settings")
    @patch("app.pipeline.video.asyncio.create_subprocess_exec")
    async def test_execute_calls_ffmpeg(
        self,
        mock_subprocess,
        mock_settings,
        mock_get_visual,
        video_step: VideoStep,
        session: AsyncSession,
        tmp_path,
    ):
        """execute() should generate background image, then call FFmpeg and ffprobe."""
        # Setup
        engine = PipelineEngine()
        episode = await engine.create_episode("Test Episode", session)
        episode_id = episode.id

        # Create a script step with output_data
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
        mock_settings.visual_provider = "static"

        # Mock visual provider
        mock_provider = AsyncMock()
        mock_provider.generate_background_image = AsyncMock(return_value=str(audio_dir / "background.png"))
        mock_provider.generate_thumbnail = AsyncMock(return_value=str(audio_dir / "thumbnail.png"))
        mock_get_visual.return_value = mock_provider

        # Mock ffprobe (first call), background image ffmpeg (from static provider is mocked),
        # and final ffmpeg (video composition)
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
        result = await video_step.execute(episode_id, input_data, session)

        # Verify
        assert result["video_path"] == f"{episode_id}/video.mp4"
        assert result["duration_seconds"] == 10.5
        assert "visual_provider" in result

        # Visual provider should have been called
        mock_provider.generate_background_image.assert_called_once()
        mock_provider.generate_thumbnail.assert_called_once()

        # ffprobe + ffmpeg
        assert mock_subprocess.call_count == 2
        first_call_args = mock_subprocess.call_args_list[0][0]
        assert first_call_args[0] == "ffprobe"
        second_call_args = mock_subprocess.call_args_list[1][0]
        assert second_call_args[0] == "ffmpeg"

    def test_load_avatars_empty(self, video_step: VideoStep):
        """_load_avatars returns empty dict when no speakers have avatars."""
        assert video_step._load_avatars({}) == {}
