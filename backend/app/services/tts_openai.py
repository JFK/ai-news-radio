"""OpenAI TTS provider implementation."""

import logging

import openai

from app.config import settings
from app.services.tts_provider import TTSProvider
from app.services.tts_utils import concatenate_mp3, split_text_chunks

logger = logging.getLogger(__name__)


class OpenAITTSProvider(TTSProvider):
    """TTS provider using OpenAI's TTS API."""

    def __init__(self, model: str | None = None, voice: str | None = None) -> None:
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)
        self._model = model or settings.openai_tts_model
        self._voice = voice or settings.openai_tts_voice

    @property
    def audio_format(self) -> str:
        return "mp3"

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to MP3 audio using OpenAI TTS.

        Splits long text into chunks and concatenates results.
        """
        text_chunks = split_text_chunks(text)
        if not text_chunks:
            raise ValueError("Empty text provided for synthesis")

        audio_chunks: list[bytes] = []
        for chunk in text_chunks:
            response = await self._client.audio.speech.create(
                model=self._model,
                voice=self._voice,
                input=chunk,
            )
            audio_chunks.append(response.content)
            logger.debug("Synthesized chunk: %d chars -> %d bytes", len(chunk), len(response.content))

        return concatenate_mp3(audio_chunks)

    async def health_check(self) -> bool:
        """Check if OpenAI API is accessible."""
        try:
            # Simple API key validation — list models
            await self._client.models.list()
            return True
        except openai.APIError:
            return False
