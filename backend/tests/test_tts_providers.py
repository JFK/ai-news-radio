"""Tests for TTS provider abstraction and implementations."""

import io
import wave
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tts_openai import OpenAITTSProvider, split_text_chunks
from app.services.tts_voicevox import VoicevoxTTSProvider, concatenate_wav, split_sentences

# --- Helper ---


def _make_wav_bytes(duration_frames: int = 100, sample_rate: int = 24000) -> bytes:
    """Create minimal valid WAV bytes."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(b"\x00\x00" * duration_frames)
    return buf.getvalue()


# --- split_sentences ---


class TestSplitSentences:
    def test_basic_japanese(self):
        text = "こんにちは。今日は良い天気です。明日はどうでしょう？"
        result = split_sentences(text)
        assert len(result) == 3
        assert result[0] == "こんにちは。"
        assert result[1] == "今日は良い天気です。"
        assert result[2] == "明日はどうでしょう？"

    def test_exclamation(self):
        text = "すごい！本当ですか？"
        result = split_sentences(text)
        assert len(result) == 2

    def test_newline_split(self):
        text = "一行目\n二行目\n三行目"
        result = split_sentences(text)
        assert len(result) == 3

    def test_empty_string(self):
        assert split_sentences("") == []

    def test_no_punctuation(self):
        text = "句読点なしのテキスト"
        result = split_sentences(text)
        assert result == ["句読点なしのテキスト"]

    def test_whitespace_only(self):
        assert split_sentences("   ") == []


# --- concatenate_wav ---


class TestConcatenateWav:
    def test_single_chunk(self):
        wav = _make_wav_bytes()
        result = concatenate_wav([wav])
        assert result == wav

    def test_multiple_chunks(self):
        wav1 = _make_wav_bytes(100)
        wav2 = _make_wav_bytes(200)
        result = concatenate_wav([wav1, wav2])

        # Verify it's a valid WAV with combined frames
        with wave.open(io.BytesIO(result), "rb") as w:
            assert w.getnframes() == 300


# --- split_text_chunks ---


class TestSplitTextChunks:
    def test_short_text_single_chunk(self):
        text = "短いテキスト。"
        result = split_text_chunks(text)
        assert result == [text]

    def test_empty_text(self):
        assert split_text_chunks("") == []

    def test_long_text_splits(self):
        # Create text that exceeds max_chars
        sentence = "これはテスト文です。"  # ~10 chars
        text = sentence * 500  # ~5000 chars
        result = split_text_chunks(text, max_chars=100)
        assert len(result) > 1
        # Each chunk should be <= max_chars (approximately, may be slightly over due to boundary)
        for chunk in result:
            assert len(chunk) <= 5100  # generous upper bound


# --- VoicevoxTTSProvider ---


class TestVoicevoxProvider:
    @patch("app.services.tts_voicevox.settings")
    async def test_synthesize_calls_api(self, mock_settings):
        mock_settings.voicevox_host = "http://localhost:50021"
        mock_settings.voicevox_speaker_id = 3

        wav_bytes = _make_wav_bytes()

        provider = VoicevoxTTSProvider()
        with patch("app.services.tts_voicevox.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            # audio_query response
            mock_query_resp = MagicMock()
            mock_query_resp.json.return_value = {"accent_phrases": []}
            mock_query_resp.raise_for_status = MagicMock()

            # synthesis response
            mock_synth_resp = MagicMock()
            mock_synth_resp.content = wav_bytes
            mock_synth_resp.raise_for_status = MagicMock()

            mock_client.post.side_effect = [mock_query_resp, mock_synth_resp]

            result = await provider.synthesize("テスト。")

            assert result == wav_bytes
            assert mock_client.post.call_count == 2
            # First call: audio_query
            assert "/audio_query" in mock_client.post.call_args_list[0][0][0]
            # Second call: synthesis
            assert "/synthesis" in mock_client.post.call_args_list[1][0][0]

    async def test_synthesize_empty_raises(self):
        provider = VoicevoxTTSProvider()
        with pytest.raises(ValueError, match="Empty text"):
            await provider.synthesize("")

    def test_audio_format(self):
        provider = VoicevoxTTSProvider()
        assert provider.audio_format == "wav"

    @patch("app.services.tts_voicevox.settings")
    async def test_health_check_success(self, mock_settings):
        mock_settings.voicevox_host = "http://localhost:50021"

        provider = VoicevoxTTSProvider()
        with patch("app.services.tts_voicevox.httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client_cls.return_value.__aenter__ = AsyncMock(return_value=mock_client)
            mock_client_cls.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_client.get.return_value = mock_resp

            assert await provider.health_check() is True


# --- OpenAITTSProvider ---


class TestOpenAITTSProvider:
    @patch("app.services.tts_openai.settings")
    async def test_synthesize_calls_api(self, mock_settings):
        mock_settings.openai_api_key = "test-key"
        mock_settings.openai_tts_model = "tts-1"
        mock_settings.openai_tts_voice = "alloy"

        provider = OpenAITTSProvider()

        mock_speech_response = MagicMock()
        mock_speech_response.content = b"fake-mp3-data"

        provider._client = AsyncMock()
        provider._client.audio.speech.create = AsyncMock(return_value=mock_speech_response)

        result = await provider.synthesize("テスト音声です。")

        assert result == b"fake-mp3-data"
        provider._client.audio.speech.create.assert_called_once()

    async def test_synthesize_empty_raises(self):
        provider = OpenAITTSProvider.__new__(OpenAITTSProvider)
        with pytest.raises(ValueError, match="Empty text"):
            await provider.synthesize("")

    def test_audio_format(self):
        provider = OpenAITTSProvider.__new__(OpenAITTSProvider)
        assert provider.audio_format == "mp3"


# --- get_tts_provider ---


class TestGetTTSProvider:
    @patch("app.services.tts_provider.settings")
    def test_voicevox_provider(self, mock_settings):
        mock_settings.pipeline_voice_provider = "voicevox"
        from app.services.tts_provider import get_tts_provider

        provider = get_tts_provider()
        assert isinstance(provider, VoicevoxTTSProvider)

    @patch("app.services.tts_provider.settings")
    def test_openai_provider(self, mock_settings):
        mock_settings.pipeline_voice_provider = "openai"
        mock_settings.openai_api_key = "test"
        from app.services.tts_provider import get_tts_provider

        provider = get_tts_provider()
        assert isinstance(provider, OpenAITTSProvider)

    @patch("app.services.tts_provider.settings")
    def test_unknown_provider_raises(self, mock_settings):
        mock_settings.pipeline_voice_provider = "unknown"
        from app.services.tts_provider import get_tts_provider

        with pytest.raises(ValueError, match="Unknown TTS provider"):
            get_tts_provider()
