from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/ainewsradio"

    # Redis
    redis_url: str = "redis://redis:6379/0"

    # AI Provider defaults
    default_ai_provider: str = "openai"
    default_ai_model: str = "gpt-5"

    # Per-step AI configuration
    pipeline_factcheck_provider: str = "openai"
    pipeline_factcheck_model: str = "gpt-5"
    pipeline_analysis_provider: str = "openai"
    pipeline_analysis_model: str = "gpt-5"
    pipeline_script_provider: str = "openai"
    pipeline_script_model: str = "gpt-5"

    # API Keys
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""
    brave_search_api_key: str = ""

    # Collection
    collection_method: str = "brave"  # "brave" or "scraper"
    collection_queries: str = "熊本 ニュース,熊本県 政治,熊本 経済"

    # Media
    media_dir: str = "/app/media"

    # Voice/TTS
    pipeline_voice_provider: str = "voicevox"  # "voicevox" or "openai"
    openai_tts_model: str = "tts-1"
    openai_tts_voice: str = "alloy"

    # VOICEVOX
    voicevox_host: str = "http://voicevox:50021"
    voicevox_speaker_id: int = 3  # ずんだもん

    # YouTube
    youtube_client_id: str = ""
    youtube_client_secret: str = ""

    model_config = {"env_file": ".env", "extra": "ignore"}


settings = Settings()
