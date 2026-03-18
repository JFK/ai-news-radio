from typing import TYPE_CHECKING

from pydantic_settings import BaseSettings

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/ainewsradio"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # AI Provider defaults
    default_ai_provider: str = "openai"
    default_ai_model: str = "gpt-5.2"

    # Per-step AI configuration
    pipeline_factcheck_provider: str = "openai"
    pipeline_factcheck_model: str = "gpt-5.2"
    pipeline_analysis_provider: str = "openai"
    pipeline_analysis_model: str = "gpt-5.2"
    pipeline_script_provider: str = "openai"
    pipeline_script_model: str = "gpt-5.2"

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    brave_search_api_key: str = ""

    # Collection
    collection_method: str = "brave"
    collection_queries: str = "熊本 ニュース,熊本県 政治,熊本 経済"

    # Content enrichment
    collection_crawl_enabled: bool = True
    collection_crawl_timeout: float = 15.0
    collection_crawl_max_body_chars: int = 50000
    collection_youtube_enabled: bool = True
    collection_document_enabled: bool = True

    # AI multi-stage research
    collection_ai_research_enabled: bool = False
    collection_ai_research_max_rounds: int = 2
    collection_ai_research_provider: str = ""
    collection_ai_research_model: str = ""

    # Media
    media_dir: str = "/app/media"

    # Voice/TTS
    voice_section_silence: float = 1.5  # Silence between sections (seconds)
    srt_offset: float = 0.0  # SRT subtitle delay offset (seconds, positive = later)
    pipeline_voice_provider: str = "gemini"  # "voicevox", "openai", "elevenlabs", "google", "gemini"
    openai_tts_model: str = "tts-1"
    openai_tts_voice: str = "alloy"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel (default)
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    google_tts_voice: str = "ja-JP-Neural2-B"  # Japanese male
    google_tts_language_code: str = "ja-JP"
    gemini_tts_model: str = "gemini-2.5-flash-preview-tts"
    gemini_tts_voice: str = "Kore"  # Prebuilt voice name
    gemini_tts_instructions: str = "落ち着いたニュースキャスターのように、明瞭で聞き取りやすく話してください"

    # Sound Effects (SE)
    se_intro: str = "intro_chime"  # Preset name or "none"
    se_transition: str = "transition_chime"  # Preset name or "none"
    se_outro: str = "outro_chime"  # Preset name or "none"

    # VOICEVOX
    voicevox_host: str = "http://voicevox:50021"
    voicevox_speaker_id: int = 3  # ずんだもん

    # Visual (thumbnail/background for video)
    visual_provider: str = "static"  # "static" or "google"
    visual_imagen_model: str = "imagen-4.0-fast-generate-001"
    visual_veo_model: str = "veo-2.0-generate-001"

    # Video overlay styling
    video_border_color: str = "#DC1E1E"  # Hex color for thumbnail/video border
    video_logo_path: str = ""  # Path to logo image (replaces "AI NEWS RADIO" text badge)
    video_logo_enabled: bool = True  # Show logo/text badge on thumbnail & video

    # YouTube CTA (Call To Action) after opening
    youtube_cta_enabled: bool = True
    youtube_cta_text: str = (
        "この番組では、ニュースの背景や多様な視点をわかりやすくお届けしています。"
        "チャンネル登録と高評価、よろしくお願いします。"
    )

    # YouTube Outro after ending
    youtube_outro_enabled: bool = True
    youtube_outro_text: str = (
        "ご視聴ありがとうございました。"
        "チャンネル登録、高評価もよろしくお願いします。"
        "また次回の放送でお会いしましょう。"
    )

    # Google Drive Export (OAuth 2.0)
    google_drive_enabled: bool = False
    google_drive_folder_id: str = ""
    google_drive_client_id: str = ""
    google_drive_client_secret: str = ""
    google_drive_refresh_token: str = ""  # Set automatically via OAuth callback
    google_drive_redirect_base: str = ""  # e.g. http://localhost:8000

    # Export AI configuration
    pipeline_export_provider: str = ""
    pipeline_export_model: str = ""

    # Script mode (multi-speaker)
    script_default_mode: str = "auto"  # auto / explainer / solo
    shorts_max_duration_seconds: int = 30

    # Shorts video
    shorts_video_provider: str = "ffmpeg"  # "ffmpeg" or "veo"
    shorts_veo_audio: bool = True  # Use Veo's generate_audio (skip TTS merge)

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()


async def load_settings_from_db(session: "AsyncSession") -> None:
    """Load settings from app_settings table and override in-memory settings."""
    from sqlalchemy import select

    from app.models.app_setting import AppSetting

    result = await session.execute(select(AppSetting))
    for row in result.scalars():
        key = row.key
        if hasattr(settings, key):
            field_info = Settings.model_fields.get(key)
            if field_info:
                # Convert value to appropriate type
                annotation = field_info.annotation
                if annotation is bool:
                    val: object = row.value.lower() in ("true", "1", "yes")
                elif annotation is int:
                    val = int(row.value) if row.value else 0
                elif annotation is float:
                    val = float(row.value) if row.value else 0.0
                else:
                    val = row.value
                object.__setattr__(settings, key, val)
