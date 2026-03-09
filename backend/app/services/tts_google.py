"""Google Cloud Text-to-Speech provider implementation."""

import logging

import httpx

from app.config import settings
from app.services.tts_provider import TTSProvider
from app.services.tts_voicevox import concatenate_wav, split_sentences

logger = logging.getLogger(__name__)

GOOGLE_TTS_API_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"

# Google TTS has a 5000 byte limit per request (~2500 Japanese chars)
MAX_CHARS_PER_CHUNK = 2500


class GoogleTTSProvider(TTSProvider):
    """TTS provider using Google Cloud Text-to-Speech API.

    Pricing (2026):
    - Standard voices: $4/1M chars (free tier: 4M chars/month)
    - WaveNet voices: $16/1M chars (free tier: 1M chars/month)
    - Neural2 voices: $16/1M chars (free tier: 1M chars/month)
    - Journey voices: $30/1M chars
    """

    @property
    def audio_format(self) -> str:
        return "wav"

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV audio using Google Cloud TTS.

        Splits long text into sentences and synthesizes each separately.
        """
        sentences = split_sentences(text)
        if not sentences:
            raise ValueError("Empty text provided for synthesis")

        # Group sentences into chunks within limit
        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            if len(current) + len(sentence) > MAX_CHARS_PER_CHUNK and current:
                chunks.append(current)
                current = sentence
            else:
                current += sentence
        if current:
            chunks.append(current)

        audio_chunks: list[bytes] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for chunk in chunks:
                audio = await self._synthesize_chunk(client, chunk)
                audio_chunks.append(audio)

        return concatenate_wav(audio_chunks)

    async def _synthesize_chunk(self, client: httpx.AsyncClient, text: str) -> bytes:
        """Synthesize a single chunk via Google Cloud TTS API."""
        response = await client.post(
            GOOGLE_TTS_API_URL,
            params={"key": settings.google_api_key},
            json={
                "input": {"text": text},
                "voice": {
                    "languageCode": settings.google_tts_language_code,
                    "name": settings.google_tts_voice,
                },
                "audioConfig": {
                    "audioEncoding": "LINEAR16",
                    "sampleRateHertz": 24000,
                },
            },
        )
        response.raise_for_status()

        import base64

        audio_content = base64.b64decode(response.json()["audioContent"])
        logger.debug("Google TTS synthesized: %d chars -> %d bytes", len(text), len(audio_content))
        return audio_content

    async def health_check(self) -> bool:
        """Check if Google Cloud TTS API is accessible."""
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.get(
                    "https://texttospeech.googleapis.com/v1/voices",
                    params={"key": settings.google_api_key},
                )
                return response.status_code == 200
        except httpx.HTTPError:
            return False
