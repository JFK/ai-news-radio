"""Tests for external TTS providers (ElevenLabs, Google Cloud TTS)."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tts_elevenlabs import ElevenLabsTTSProvider
from app.services.tts_google import GoogleTTSProvider


class TestElevenLabsTTSProvider:
    def test_audio_format(self):
        provider = ElevenLabsTTSProvider()
        assert provider.audio_format == "mp3"

    @patch("app.services.tts_elevenlabs.settings")
    async def test_synthesize(self, mock_settings):
        mock_settings.elevenlabs_api_key = "test-key"
        mock_settings.elevenlabs_voice_id = "test-voice"
        mock_settings.elevenlabs_model_id = "eleven_multilingual_v2"

        provider = ElevenLabsTTSProvider()

        with patch("app.services.tts_elevenlabs.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_response = MagicMock()
            mock_response.content = b"fake-mp3-data"
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            result = await provider.synthesize("テスト音声です。")

            assert result == b"fake-mp3-data"
            mock_client.post.assert_called_once()
            # Verify API URL contains voice ID
            call_args = mock_client.post.call_args
            assert "test-voice" in call_args[0][0]

    async def test_synthesize_empty_raises(self):
        provider = ElevenLabsTTSProvider()
        with pytest.raises(ValueError, match="Empty text"):
            await provider.synthesize("")

    @patch("app.services.tts_elevenlabs.settings")
    async def test_health_check(self, mock_settings):
        mock_settings.elevenlabs_api_key = "test-key"

        provider = ElevenLabsTTSProvider()

        with patch("app.services.tts_elevenlabs.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_client.get.return_value = mock_response

            assert await provider.health_check() is True


class TestGoogleTTSProvider:
    def test_audio_format(self):
        provider = GoogleTTSProvider()
        assert provider.audio_format == "wav"

    @patch("app.services.tts_google.settings")
    async def test_synthesize(self, mock_settings):
        mock_settings.google_api_key = "test-key"
        mock_settings.google_tts_voice = "ja-JP-Neural2-B"
        mock_settings.google_tts_language_code = "ja-JP"

        provider = GoogleTTSProvider()

        import base64

        # Google TTS returns base64-encoded LINEAR16 WAV
        # Create a minimal valid WAV for testing
        import io
        import wave

        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(24000)
            w.writeframes(b"\x00\x00" * 100)
        wav_bytes = buf.getvalue()
        b64_audio = base64.b64encode(wav_bytes).decode()

        with patch("app.services.tts_google.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_response = MagicMock()
            mock_response.json.return_value = {"audioContent": b64_audio}
            mock_response.raise_for_status = MagicMock()
            mock_client.post.return_value = mock_response

            result = await provider.synthesize("テスト。")

            assert len(result) > 0
            mock_client.post.assert_called_once()

    async def test_synthesize_empty_raises(self):
        provider = GoogleTTSProvider()
        with pytest.raises(ValueError, match="Empty text"):
            await provider.synthesize("")


class TestGetTTSProviderExtended:
    @patch("app.services.tts_provider.settings")
    def test_elevenlabs_provider(self, mock_settings):
        mock_settings.pipeline_voice_provider = "elevenlabs"
        mock_settings.elevenlabs_api_key = "test"
        from app.services.tts_provider import get_tts_provider

        provider = get_tts_provider()
        assert isinstance(provider, ElevenLabsTTSProvider)

    @patch("app.services.tts_provider.settings")
    def test_google_provider(self, mock_settings):
        mock_settings.pipeline_voice_provider = "google"
        from app.services.tts_provider import get_tts_provider

        provider = get_tts_provider()
        assert isinstance(provider, GoogleTTSProvider)
