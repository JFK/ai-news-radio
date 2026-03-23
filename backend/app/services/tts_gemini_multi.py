"""Gemini TTS MultiSpeaker provider implementation.

Uses Gemini 2.5 Flash/Pro TTS models with MultiSpeakerMarkup for
natural two-speaker dialogue synthesis (max 2 speakers).
"""

import asyncio
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

# Max chars per request (conservative limit)
MAX_CHARS_PER_CHUNK = 5000


class GeminiMultiSpeakerTTSProvider(TTSProvider):
    """TTS provider using Gemini 2.5 TTS MultiSpeaker mode.

    Synthesizes dialogue between two speakers in a single API call
    for natural turn-taking and prosody.
    """

    def __init__(
        self,
        model: str | None = None,
        speaker_a_voice: str = "Kore",
        speaker_b_voice: str = "Charon",
        speaker_a_instructions: str = "",
        speaker_b_instructions: str = "",
    ) -> None:
        self._client = genai.Client(api_key=settings.google_api_key)
        self._model = model or settings.gemini_tts_model
        self._speaker_a_voice = speaker_a_voice
        self._speaker_b_voice = speaker_b_voice
        self._speaker_a_instructions = speaker_a_instructions
        self._speaker_b_instructions = speaker_b_instructions
        self.total_input_tokens = 0
        self.total_output_tokens = 0

    @property
    def audio_format(self) -> str:
        return "wav"

    async def synthesize(self, text: str) -> bytes:
        """Synthesize text using single-speaker mode (fallback).

        For dialogue, use synthesize_dialogue() instead.
        """
        from app.services.tts_gemini import GeminiTTSProvider

        fallback = GeminiTTSProvider(
            model=self._model,
            voice=self._speaker_a_voice,
            instructions=self._speaker_a_instructions,
        )
        result = await fallback.synthesize(text)
        self.total_input_tokens += fallback.total_input_tokens
        self.total_output_tokens += fallback.total_output_tokens
        return result

    async def synthesize_dialogue(self, dialogue: list[dict]) -> bytes:
        """Synthesize a dialogue using Gemini MultiSpeaker TTS.

        Args:
            dialogue: List of {"speaker": "speaker_a"|"speaker_b", "text": "..."} dicts.

        Returns:
            WAV audio bytes of the full dialogue.
        """
        if not dialogue:
            raise ValueError("Empty dialogue provided for synthesis")

        # Build MultiSpeaker markup text
        # Format: "Speaker Name: text\nSpeaker Name: text\n..."
        markup_lines: list[str] = []
        for turn in dialogue:
            speaker_key = turn.get("speaker", "speaker_a")
            text = turn.get("text", "")
            if text:
                markup_lines.append(f"{speaker_key}: {text}")

        full_text = "\n".join(markup_lines)

        # Split into chunks if needed
        chunks = split_text_chunks(full_text, MAX_CHARS_PER_CHUNK)
        audio_chunks: list[bytes] = []

        for chunk in chunks:
            # Prepend style instructions if configured
            content = ""
            if self._speaker_a_instructions or self._speaker_b_instructions:
                instructions_parts = []
                if self._speaker_a_instructions:
                    instructions_parts.append(f"speaker_a speaks like: {self._speaker_a_instructions}")
                if self._speaker_b_instructions:
                    instructions_parts.append(f"speaker_b speaks like: {self._speaker_b_instructions}")
                content = ". ".join(instructions_parts) + "\n\n"
            content += chunk

            config = types.GenerateContentConfig(
                response_modalities=["AUDIO"],
                speech_config=types.SpeechConfig(
                    multi_speaker_voice_config=types.MultiSpeakerVoiceConfig(
                        speaker_voice_configs=[
                            types.SpeakerVoiceConfig(
                                speaker="speaker_a",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=self._speaker_a_voice,
                                    )
                                ),
                            ),
                            types.SpeakerVoiceConfig(
                                speaker="speaker_b",
                                voice_config=types.VoiceConfig(
                                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                        voice_name=self._speaker_b_voice,
                                    )
                                ),
                            ),
                        ]
                    )
                ),
            )

            response = await self._generate_with_retry(content, config, len(chunk))
            pcm_data = response.candidates[0].content.parts[0].inline_data.data

            if response.usage_metadata:
                self.total_input_tokens += response.usage_metadata.prompt_token_count or 0
                self.total_output_tokens += response.usage_metadata.candidates_token_count or 0

            wav_data = self._pcm_to_wav(pcm_data)
            audio_chunks.append(wav_data)

            logger.debug(
                "Gemini MultiSpeaker TTS synthesized: %d chars -> %d bytes PCM",
                len(chunk),
                len(pcm_data),
            )

        return concatenate_wav(audio_chunks) if len(audio_chunks) > 1 else audio_chunks[0]

    async def _generate_with_retry(self, content: str, config: types.GenerateContentConfig, chunk_chars: int):
        """Call Gemini API with timeout and one retry."""
        timeout = settings.tts_chunk_timeout
        for attempt in range(2):
            try:
                return await asyncio.wait_for(
                    self._client.aio.models.generate_content(
                        model=self._model,
                        contents=content,
                        config=config,
                    ),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                if attempt == 0:
                    logger.warning(
                        "Gemini MultiSpeaker TTS chunk timed out after %ds (%d chars), retrying once",
                        timeout, chunk_chars,
                    )
                else:
                    raise TimeoutError(
                        f"Gemini MultiSpeaker TTS chunk timed out after {timeout}s ({chunk_chars} chars)"
                    )
        raise TimeoutError("Unreachable")  # satisfy type checker

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
