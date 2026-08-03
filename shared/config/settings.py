from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings and environment configurations.
    Single authoritative source of truth for runtime config.
    Loads values from environment variables or a local .env file.
    """
    # Environment & Service settings
    environment: str = "development"
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    debug: bool = False

    # Master & Distributed Worker Service URLs
    master_service_url: str = "http://127.0.0.1:8000"
    agent6_service_url: str = "http://127.0.0.1:8001"
    agent7_service_url: str = "http://127.0.0.1:8002"
    agent8_service_url: str = "http://127.0.0.1:8003"
    
    # Timeout & Retry Policies
    agent_http_timeout_seconds: float = 30.0
    health_http_timeout_seconds: float = 3.0
    max_retry_attempts: int = 3

    # Databases (mocked for now)
    database_url: str = "postgresql://postgres:password@localhost:5432/oxiqai_recruitment_db"

    # API credentials (mocked for now)
    anthropic_api_key: str = "mock-anthropic-key"
    openai_api_key: str = "mock-openai-key"

    # Google Workspace (mocked for now)
    google_application_credentials: str = "mock-credentials.json"
    google_calendar_id: str = "primary"

    # SMTP Server (mocked for now)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_username: str = "recruitment@oxiqai.com"
    smtp_password: str = "mock-password"
    smtp_from_email: str = "recruitment@oxiqai.com"

    # Configuration loading rules
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate a global settings singleton
settings = Settings()
