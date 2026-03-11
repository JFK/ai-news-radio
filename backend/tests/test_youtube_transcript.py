"""Tests for YouTubeTranscriptService."""

from unittest.mock import MagicMock, patch

import pytest

from app.services.youtube_transcript import YouTubeTranscriptService


@pytest.fixture
def yt_service() -> YouTubeTranscriptService:
    return YouTubeTranscriptService()


class TestYouTubeURLDetection:
    """Tests for YouTube URL detection and ID extraction."""

    @pytest.mark.parametrize(
        "url,expected",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", True),
            ("https://youtu.be/dQw4w9WgXcQ", True),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", True),
            ("https://example.com/news/1", False),
            ("https://example.com/youtube.com/watch", False),
        ],
    )
    def test_is_youtube_url(self, url: str, expected: bool):
        assert YouTubeTranscriptService.is_youtube_url(url) is expected

    @pytest.mark.parametrize(
        "url,expected_id",
        [
            ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://youtu.be/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://www.youtube.com/embed/dQw4w9WgXcQ", "dQw4w9WgXcQ"),
            ("https://example.com/news/1", None),
        ],
    )
    def test_extract_video_id(self, url: str, expected_id: str | None):
        assert YouTubeTranscriptService.extract_video_id(url) == expected_id


class TestYouTubeTranscript:
    """Tests for transcript retrieval (mocked)."""

    async def test_get_transcript_invalid_url(self, yt_service: YouTubeTranscriptService):
        """Should return failure for non-YouTube URL."""
        result = await yt_service.get_transcript("https://example.com/not-youtube")
        assert result.success is False
        assert "Invalid YouTube URL" in (result.error or "")

    async def test_get_transcript_success(self, yt_service: YouTubeTranscriptService):
        """Should extract transcript text (mocked)."""
        mock_snippet = MagicMock()
        mock_snippet.text = "こんにちは世界"

        mock_fetched = MagicMock()
        mock_fetched.__iter__ = MagicMock(return_value=iter([mock_snippet]))

        mock_transcript = MagicMock()
        mock_transcript.fetch.return_value = mock_fetched

        mock_transcript_list = MagicMock()
        mock_transcript_list.find_manually_created_transcript.return_value = mock_transcript

        mock_api = MagicMock()
        mock_api.list.return_value = mock_transcript_list

        with patch("youtube_transcript_api.YouTubeTranscriptApi", return_value=mock_api):
            result = await yt_service.get_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.success is True
        assert "こんにちは世界" in result.text
        assert result.language == "ja"

    async def test_get_transcript_no_transcript_available(self, yt_service: YouTubeTranscriptService):
        """Should return failure when no transcript is available."""
        mock_transcript_list = MagicMock()
        mock_transcript_list.find_manually_created_transcript.side_effect = Exception("Not found")
        mock_transcript_list.find_generated_transcript.side_effect = Exception("Not found")

        mock_api = MagicMock()
        mock_api.list.return_value = mock_transcript_list

        with patch("youtube_transcript_api.YouTubeTranscriptApi", return_value=mock_api):
            result = await yt_service.get_transcript("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

        assert result.success is False
