"""OpenAI TTS provider implementation."""

import io
import logging

import openai

from app.config import settings
from app.services.tts_provider import TTSProvider

logger = logging.getLogger(__name__)

# OpenAI TTS has a 4096-character limit per request
MAX_CHARS_PER_CHUNK = 4096


def split_text_chunks(text: str, max_chars: int = MAX_CHARS_PER_CHUNK) -> list[str]:
    """Split text into chunks that fit within the character limit.

    Tries to split on sentence boundaries (。！？\\n) for natural breaks.
    """
    if not text:
        return []

    if len(text) <= max_chars:
        return [text]

    chunks: list[str] = []
    current = ""

    for char in text:
        current += char
        if char in "。！？\n" and len(current) >= max_chars * 0.5:
            stripped = current.strip()
            if stripped:
                chunks.append(stripped)
            current = ""

    # Handle remaining text
    stripped = current.strip()
    if stripped:
        if chunks and len(chunks[-1]) + len(stripped) <= max_chars:
            chunks[-1] += stripped
        else:
            chunks.append(stripped)

    return chunks


def concatenate_mp3(chunks: list[bytes]) -> bytes:
    """Concatenate multiple MP3 byte chunks into a single MP3 file.

    MP3 frames are self-contained, so simple concatenation works.
    """
    output = io.BytesIO()
    for chunk in chunks:
        output.write(chunk)
    return output.getvalue()


class OpenAITTSProvider(TTSProvider):
    """TTS provider using OpenAI's TTS API."""

    def __init__(self) -> None:
        self._client = openai.AsyncOpenAI(api_key=settings.openai_api_key)

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
                model=settings.openai_tts_model,
                voice=settings.openai_tts_voice,
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
