from pydantic_settings import BaseSettings


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
    pipeline_voice_provider: str = "voicevox"  # "voicevox", "openai", "elevenlabs", "google"
    openai_tts_model: str = "tts-1"
    openai_tts_voice: str = "alloy"
    elevenlabs_api_key: str = ""
    elevenlabs_voice_id: str = "21m00Tcm4TlvDq8ikWAM"  # Rachel (default)
    elevenlabs_model_id: str = "eleven_multilingual_v2"
    google_tts_voice: str = "ja-JP-Neural2-B"  # Japanese male
    google_tts_language_code: str = "ja-JP"

    # VOICEVOX
    voicevox_host: str = "http://voicevox:50021"
    voicevox_speaker_id: int = 3  # ずんだもん

    # Visual (thumbnail/background for video)
    visual_provider: str = "static"  # "static" or "google"
    visual_imagen_model: str = "imagen-4.0-fast-generate-001"
    visual_veo_model: str = "veo-2.0-generate-001"

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
