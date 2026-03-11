"""YouTube transcript extraction service."""

import asyncio
import logging
import re
from dataclasses import dataclass

logger = logging.getLogger(__name__)

YOUTUBE_URL_PATTERNS = [
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/watch\?v=([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?youtu\.be/([a-zA-Z0-9_-]{11})"),
    re.compile(r"(?:https?://)?(?:www\.)?youtube\.com/embed/([a-zA-Z0-9_-]{11})"),
]


@dataclass
class TranscriptResult:
    """Result of a YouTube transcript extraction."""

    text: str
    language: str
    success: bool
    error: str | None = None


class YouTubeTranscriptService:
    """Extract transcripts from YouTube videos."""

    @staticmethod
    def is_youtube_url(url: str) -> bool:
        """Check if a URL is a YouTube video URL."""
        return any(pattern.search(url) for pattern in YOUTUBE_URL_PATTERNS)

    @staticmethod
    def extract_video_id(url: str) -> str | None:
        """Extract the video ID from a YouTube URL."""
        for pattern in YOUTUBE_URL_PATTERNS:
            match = pattern.search(url)
            if match:
                return match.group(1)
        return None

    async def get_transcript(self, url: str) -> TranscriptResult:
        """Get the transcript for a YouTube video.

        Tries Japanese → auto-generated Japanese → English transcripts.

        Args:
            url: YouTube video URL.

        Returns:
            TranscriptResult with transcript text or error.
        """
        video_id = self.extract_video_id(url)
        if not video_id:
            return TranscriptResult(text="", language="", success=False, error="Invalid YouTube URL")

        try:
            return await asyncio.to_thread(self._fetch_transcript, video_id)
        except Exception as e:
            logger.warning("YouTube transcript failed for %s: %s", video_id, e)
            return TranscriptResult(text="", language="", success=False, error=str(e))

    def _fetch_transcript(self, video_id: str) -> TranscriptResult:
        """Fetch transcript synchronously (runs in thread)."""
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()

        # Try language priorities: Japanese manual → Japanese auto → English
        language_priorities = ["ja", "en"]
        try:
            transcript_list = api.list(video_id)
        except Exception as e:
            return TranscriptResult(text="", language="", success=False, error=str(e))

        # Try manually created transcripts first
        for lang in language_priorities:
            try:
                transcript = transcript_list.find_manually_created_transcript([lang])
                fetched = transcript.fetch()
                text = " ".join(snippet.text for snippet in fetched)
                return TranscriptResult(text=text, language=lang, success=True)
            except Exception:
                continue

        # Try auto-generated transcripts
        for lang in language_priorities:
            try:
                transcript = transcript_list.find_generated_transcript([lang])
                fetched = transcript.fetch()
                text = " ".join(snippet.text for snippet in fetched)
                return TranscriptResult(text=text, language=f"{lang}-auto", success=True)
            except Exception:
                continue

        return TranscriptResult(text="", language="", success=False, error="No transcript available")
