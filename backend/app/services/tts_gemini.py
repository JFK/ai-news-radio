"""Gemini TTS provider implementation.

Uses Gemini 2.5 Flash/Pro TTS models for high-quality, natural Japanese speech.
Unlike Google Cloud TTS (Neural2), this uses LLM-based speech generation
with natural language style control.
"""

import io
import logging
import wave

from google import genai
from google.genai import types

from app.config import settings
from app.services.tts_provider import TTSProvider
from app.services.tts_utils import concatenate_wav, split_text_chunks

logger = logging.getLogger(__name__)

# Gemini TTS outputs raw PCM at 24kHz, mono, 16-bit
GEMINI_SAMPLE_RATE = 24000
GEMINI_CHANNELS = 1
GEMINI_SAMPLE_WIDTH = 2  # 16-bit

# Max chars per request (conservative limit within 32k token context)
MAX_CHARS_PER_CHUNK = 5000


class GeminiTTSProvider(TTSProvider):
    """TTS provider using Gemini 2.5 TTS models.

    Produces natural-sounding Japanese speech with style control
    via natural language instructions (no SSML needed).
    """

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = settings.gemini_tts_model
        self._voice = settings.gemini_tts_voice
        self._instructions = settings.gemini_tts_instructions

    @property
    def audio_format(self) -> str:
        return "wav"

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to WAV audio using Gemini TTS.

        Prepends style instructions to the text for natural prosody control.
        Splits long text into chunks and concatenates the results.
        """
        chunks = split_text_chunks(text, MAX_CHARS_PER_CHUNK)
        if not chunks:
            raise ValueError("Empty text provided for synthesis")

        audio_chunks: list[bytes] = []
        for chunk in chunks:
            pcm_data = await self._synthesize_chunk(chunk)
            wav_data = self._pcm_to_wav(pcm_data)
            audio_chunks.append(wav_data)

        return concatenate_wav(audio_chunks)

    async def _synthesize_chunk(self, text: str) -> bytes:
        """Synthesize a single chunk, returning raw PCM bytes."""
        # Prepend style instructions if configured
        if self._instructions:
            content = f"{self._instructions}: {text}"
        else:
            content = text

        config = types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=self._voice,
                    )
                )
            ),
        )

        response = await self._client.aio.models.generate_content(
            model=self._model,
            contents=content,
            config=config,
        )

        pcm_data = response.candidates[0].content.parts[0].inline_data.data
        logger.debug(
            "Gemini TTS synthesized: %d chars -> %d bytes PCM",
            len(text),
            len(pcm_data),
        )
        return pcm_data

    def _pcm_to_wav(self, pcm_data: bytes) -> bytes:
        """Wrap raw PCM data in a WAV header."""
        output = io.BytesIO()
        with wave.open(output, "wb") as wf:
            wf.setnchannels(GEMINI_CHANNELS)
            wf.setsampwidth(GEMINI_SAMPLE_WIDTH)
            wf.setframerate(GEMINI_SAMPLE_RATE)
            wf.writeframes(pcm_data)
        return output.getvalue()

    async def health_check(self) -> bool:
        """Check if Gemini API is accessible."""
        try:
            await self._client.aio.models.get(model=self._model)
            return True
        except Exception:
            return False
