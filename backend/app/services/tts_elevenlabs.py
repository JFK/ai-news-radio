"""ElevenLabs TTS provider implementation."""

import logging

import httpx

from app.config import settings
from app.services.tts_openai import concatenate_mp3, split_text_chunks
from app.services.tts_provider import TTSProvider

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1"

# ElevenLabs has a ~5000 character limit per request
MAX_CHARS_PER_CHUNK = 5000


class ElevenLabsTTSProvider(TTSProvider):
    """TTS provider using ElevenLabs API.

    Pricing (2026):
    - Standard voices: ~$0.30/1K chars ($300/1M chars)
    - Turbo models: ~$0.15/1K chars ($150/1M chars)
    - Free tier: 10K chars/month
    """

    @property
    def audio_format(self) -> str:
        return "mp3"

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to MP3 audio using ElevenLabs.

        Splits long text into chunks and concatenates results.
        """
        text_chunks = split_text_chunks(text, max_chars=MAX_CHARS_PER_CHUNK)
        if not text_chunks:
            raise ValueError("Empty text provided for synthesis")

        audio_chunks: list[bytes] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for chunk in text_chunks:
                audio = await self._synthesize_chunk(client, chunk)
                audio_chunks.append(audio)

        return concatenate_mp3(audio_chunks)

    async def _synthesize_chunk(self, client: httpx.AsyncClient, text: str) -> bytes:
        """Synthesize a single chunk via ElevenLabs API."""
        url = f"{ELEVENLABS_API_URL}/text-to-speech/{settings.elevenlabs_voice_id}"

        response = await client.post(
            url,
            headers={
                "xi-api-key": settings.elevenlabs_api_key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
            json={
                "text": text,
                "model_id": settings.elevenlabs_model_id,
                "voice_settings": {
                    "stability": 0.5,
                    "similarity_boost": 0.75,
                },
            },
        )
        response.raise_for_status()

        logger.debug("ElevenLabs synthesized: %d chars -> %d bytes", len(text), len(response.content))
        return response.content

    async def health_check(self) -> bool:
        """Check if ElevenLabs API is accessible."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    f"{ELEVENLABS_API_URL}/user",
                    headers={"xi-api-key": settings.elevenlabs_api_key},
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False
