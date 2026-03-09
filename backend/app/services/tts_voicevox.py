"""VOICEVOX TTS provider implementation."""

import io
import logging
import wave

import httpx

from app.config import settings
from app.services.tts_provider import TTSProvider

logger = logging.getLogger(__name__)


def split_sentences(text: str) -> list[str]:
    """Split text into sentences on Japanese punctuation and newlines."""
    if not text:
        return []

    sentences: list[str] = []
    current = ""
    for char in text:
        if char in "。！？\n":
            current += char
            stripped = current.strip()
            if stripped:
                sentences.append(stripped)
            current = ""
        else:
            current += char

    stripped = current.strip()
    if stripped:
        sentences.append(stripped)

    return sentences


def concatenate_wav(chunks: list[bytes]) -> bytes:
    """Concatenate multiple WAV byte chunks into a single WAV file."""
    if len(chunks) == 1:
        return chunks[0]

    output = io.BytesIO()
    params_set = False

    with wave.open(output, "wb") as out_wav:
        for chunk in chunks:
            with wave.open(io.BytesIO(chunk), "rb") as in_wav:
                if not params_set:
                    out_wav.setparams(in_wav.getparams())
                    params_set = True
                out_wav.writeframes(in_wav.readframes(in_wav.getnframes()))

    return output.getvalue()


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
