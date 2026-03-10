"""Google Cloud Text-to-Speech provider implementation."""

import base64
import logging

import httpx

from app.config import settings
from app.services.tts_provider import TTSProvider
from app.services.tts_utils import concatenate_wav, split_sentences

logger = logging.getLogger(__name__)

GOOGLE_TTS_API_URL = "https://texttospeech.googleapis.com/v1/text:synthesize"

# Google TTS has a 5000 byte limit per request
# Japanese chars are 3 bytes in UTF-8, so ~1600 chars max
MAX_BYTES_PER_CHUNK = 4800


class GoogleTTSProvider(TTSProvider):
    """TTS provider using Google Cloud Text-to-Speech API.

    Supports both plain text and SSML input.
    """

    @property
    def audio_format(self) -> str:
        return "wav"

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV audio using Google Cloud TTS.

        If text starts with <speak>, it is treated as SSML.
        Otherwise, it is split into sentences and sent as plain text.
        """
        is_ssml = text.strip().startswith("<speak>")

        if is_ssml:
            return await self._synthesize_ssml(text)

        return await self._synthesize_plain(text)

    async def _synthesize_plain(self, text: str) -> bytes:
        """Synthesize plain text by splitting into sentence chunks."""
        sentences = split_sentences(text)
        if not sentences:
            raise ValueError("Empty text provided for synthesis")

        chunks: list[str] = []
        current = ""
        for sentence in sentences:
            candidate = current + sentence
            if len(candidate.encode("utf-8")) > MAX_BYTES_PER_CHUNK and current:
                chunks.append(current)
                current = sentence
            else:
                current = candidate
        if current:
            chunks.append(current)

        audio_chunks: list[bytes] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for chunk in chunks:
                audio = await self._synthesize_chunk(client, {"text": chunk})
                audio_chunks.append(audio)

        return concatenate_wav(audio_chunks)

    async def _synthesize_ssml(self, ssml: str) -> bytes:
        """Synthesize SSML input by splitting into chunks.

        SSML is split on </break> or paragraph-level boundaries
        to stay within the byte limit.
        """
        # Split SSML into manageable chunks
        chunks = self._split_ssml(ssml)

        audio_chunks: list[bytes] = []
        async with httpx.AsyncClient(timeout=60.0) as client:
            for chunk in chunks:
                audio = await self._synthesize_chunk(client, {"ssml": chunk})
                audio_chunks.append(audio)

        return concatenate_wav(audio_chunks)

    def _split_ssml(self, ssml: str) -> list[str]:
        """Split SSML into chunks that fit within the byte limit.

        Each chunk is wrapped in <speak>...</speak>.
        """
        # Remove outer <speak> tags
        body = ssml.strip()
        if body.startswith("<speak>"):
            body = body[7:]
        if body.endswith("</speak>"):
            body = body[:-8]

        if len(f"<speak>{body}</speak>".encode()) <= MAX_BYTES_PER_CHUNK:
            return [f"<speak>{body}</speak>"]

        # Split on break tags or newlines as natural boundaries
        import re

        parts = re.split(r'(<break[^/]*/>\s*)', body)

        chunks: list[str] = []
        current = ""
        for part in parts:
            candidate = current + part
            if len(f"<speak>{candidate}</speak>".encode()) > MAX_BYTES_PER_CHUNK and current:
                chunks.append(f"<speak>{current}</speak>")
                current = part
            else:
                current = candidate
        if current.strip():
            chunks.append(f"<speak>{current}</speak>")

        return chunks if chunks else [f"<speak>{body}</speak>"]

    async def _synthesize_chunk(
        self, client: httpx.AsyncClient, input_data: dict
    ) -> bytes:
        """Synthesize a single chunk via Google Cloud TTS API.

        Args:
            client: HTTP client.
            input_data: Either {"text": "..."} or {"ssml": "..."}.
        """
        response = await client.post(
            GOOGLE_TTS_API_URL,
            params={"key": settings.google_api_key},
            json={
                "input": input_data,
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
        if response.status_code != 200:
            logger.error(
                "Google TTS error %d: %s",
                response.status_code,
                response.text[:500],
            )
            response.raise_for_status()

        audio_content = base64.b64decode(response.json()["audioContent"])
        input_type = "ssml" if "ssml" in input_data else "text"
        input_len = len(input_data.get("ssml", input_data.get("text", "")))
        logger.debug(
            "Google TTS synthesized (%s): %d chars -> %d bytes",
            input_type,
            input_len,
            len(audio_content),
        )
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
