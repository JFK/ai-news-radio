"""TTS Provider abstraction layer.

Provides a unified interface for multiple TTS providers (VOICEVOX, OpenAI).
"""

from abc import ABC, abstractmethod

from app.config import settings


class TTSProvider(ABC):
    """Abstract base class for TTS providers."""

    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        """Synthesize text to audio bytes (WAV or MP3)."""
        ...

    @abstractmethod
    async def health_check(self) -> bool:
        """Check if the TTS service is available."""
        ...

    @property
    @abstractmethod
    def audio_format(self) -> str:
        """Return the audio format produced by this provider ("wav" or "mp3")."""
        ...


def get_tts_provider(
    model: str | None = None,
    voice: str | None = None,
    instructions: str | None = None,
) -> TTSProvider:
    """Factory function to get a TTS provider based on settings.

    Args:
        model: Override TTS model (provider-specific).
        voice: Override TTS voice name.
        instructions: Override voice style instructions (Gemini TTS only).
    """
    provider_name = settings.pipeline_voice_provider

    if provider_name == "voicevox":
        from app.services.tts_voicevox import VoicevoxTTSProvider

        return VoicevoxTTSProvider()
    elif provider_name == "openai":
        from app.services.tts_openai import OpenAITTSProvider

        return OpenAITTSProvider(model=model, voice=voice)
    elif provider_name == "elevenlabs":
        from app.services.tts_elevenlabs import ElevenLabsTTSProvider

        return ElevenLabsTTSProvider()
    elif provider_name == "google":
        from app.services.tts_google import GoogleTTSProvider

        return GoogleTTSProvider(voice=voice)
    elif provider_name == "gemini":
        from app.services.tts_gemini import GeminiTTSProvider

        return GeminiTTSProvider(model=model, voice=voice, instructions=instructions)
    else:
        raise ValueError(f"Unknown TTS provider: {provider_name}")
