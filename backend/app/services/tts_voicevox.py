"""VOICEVOX TTS provider implementation."""

import logging

import httpx

from app.config import settings
from app.services.tts_provider import TTSProvider
from app.services.tts_utils import concatenate_wav, split_sentences

logger = logging.getLogger(__name__)


class VoicevoxTTSProvider(TTSProvider):
    """TTS provider using VOICEVOX engine."""

    @property
    def audio_format(self) -> str:
        return "wav"

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV audio using VOICEVOX.

        Splits text into sentences and synthesizes each separately,
        then concatenates the WAV chunks.
        """
        sentences = split_sentences(text)
        if not sentences:
            raise ValueError("Empty text provided for synthesis")

        chunks: list[bytes] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for sentence in sentences:
                chunk = await self._synthesize_sentence(client, sentence)
                chunks.append(chunk)

        return concatenate_wav(chunks)

    async def _synthesize_sentence(self, client: httpx.AsyncClient, sentence: str) -> bytes:
        """Synthesize a single sentence via VOICEVOX REST API."""
        host = settings.voicevox_host
        speaker_id = settings.voicevox_speaker_id

        # Step 1: Create audio query
        query_response = await client.post(
            f"{host}/audio_query",
            params={"text": sentence, "speaker": speaker_id},
        )
        query_response.raise_for_status()
        audio_query = query_response.json()

        # Step 2: Synthesize audio
        synthesis_response = await client.post(
            f"{host}/synthesis",
            params={"speaker": speaker_id},
            json=audio_query,
        )
        synthesis_response.raise_for_status()

        logger.debug("Synthesized sentence: %s (%d bytes)", sentence[:30], len(synthesis_response.content))
        return synthesis_response.content

    async def health_check(self) -> bool:
        """Check if VOICEVOX engine is running."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.voicevox_host}/version")
                return response.status_code == 200
        except httpx.HTTPError:
            return False
