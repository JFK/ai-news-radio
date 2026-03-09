"""Step 5: Voice synthesis pipeline step."""

import logging
import os

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import Episode, Pronunciation, StepName
from app.pipeline.base import BaseStep
from app.services.tts_provider import get_tts_provider
from app.services.tts_utils import expand_reading_hints

logger = logging.getLogger(__name__)


class VoiceStep(BaseStep):
    """Generate audio from the episode script using a TTS provider."""

    @property
    def step_name(self) -> StepName:
        return StepName.VOICE

    async def execute(self, episode_id: int, input_data: dict, session: AsyncSession, **kwargs) -> dict:
        """Synthesize audio from the episode script.

        Reads episode_script from scriptwriter output, synthesizes via TTS,
        saves to media/{episode_id}/audio.{format}, updates Episode.audio_path.
        """
        episode_script = input_data.get("episode_script", "")
        if not episode_script:
            raise ValueError("No episode_script in input data")

        provider = get_tts_provider()

        # Expand reading hints for TTS: 「漢字（かな）」→「かな」
        tts_text = expand_reading_hints(episode_script)

        # Apply pronunciation dictionary replacements (longer surfaces first)
        result = await session.execute(
            select(Pronunciation).order_by(Pronunciation.priority.desc(), Pronunciation.id)
        )
        for entry in result.scalars().all():
            tts_text = tts_text.replace(entry.surface, entry.reading)

        # Synthesize audio
        logger.info("Episode %d: synthesizing audio with %s", episode_id, settings.pipeline_voice_provider)
        audio_bytes = await provider.synthesize(tts_text)

        # Save to file
        audio_format = provider.audio_format
        episode_dir = os.path.join(settings.media_dir, str(episode_id))
        os.makedirs(episode_dir, exist_ok=True)
        audio_filename = f"audio.{audio_format}"
        audio_path = os.path.join(episode_dir, audio_filename)

        with open(audio_path, "wb") as f:
            f.write(audio_bytes)

        # Calculate duration
        duration_seconds = self._get_audio_duration(audio_bytes, audio_format)

        # Update episode record
        relative_path = f"{episode_id}/{audio_filename}"
        result = await session.execute(select(Episode).where(Episode.id == episode_id))
        episode = result.scalar_one()
        episode.audio_path = relative_path
        await session.commit()

        # Record usage for TTS (input_tokens = character count for TTS pricing)
        provider_name = settings.pipeline_voice_provider
        if provider_name != "voicevox":  # VOICEVOX is free/local
            model_map = {
                "openai": settings.openai_tts_model,
                "elevenlabs": f"elevenlabs-{settings.elevenlabs_model_id.split('_')[-1]}",
                "google": f"google-tts-{settings.google_tts_voice.split('-')[2].lower()}" if len(settings.google_tts_voice.split('-')) > 2 else "google-tts-standard",
            }
            model_name = model_map.get(provider_name, provider_name)
            await self.record_usage(
                session=session,
                episode_id=episode_id,
                provider=provider_name,
                model=model_name,
                input_tokens=len(episode_script),
                output_tokens=0,
            )

        logger.info(
            "Episode %d: audio saved to %s (%.1fs, %d bytes)",
            episode_id,
            relative_path,
            duration_seconds,
            len(audio_bytes),
        )

        return {
            "audio_path": relative_path,
            "duration_seconds": duration_seconds,
            "provider": settings.pipeline_voice_provider,
            "audio_format": audio_format,
        }

    def _get_audio_duration(self, audio_bytes: bytes, audio_format: str) -> float:
        """Get audio duration in seconds."""
        if audio_format == "wav":
            return self._get_wav_duration(audio_bytes)
        # For MP3, we estimate based on typical bitrate (128kbps)
        return len(audio_bytes) / (128 * 1024 / 8)

    def _get_wav_duration(self, wav_bytes: bytes) -> float:
        """Get WAV audio duration from bytes."""
        import io
        import wave

        with wave.open(io.BytesIO(wav_bytes), "rb") as wav:
            frames = wav.getnframes()
            rate = wav.getframerate()
            return frames / rate if rate > 0 else 0.0
