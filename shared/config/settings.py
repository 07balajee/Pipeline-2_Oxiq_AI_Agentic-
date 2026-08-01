from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """
    Application settings and environment configurations.
    Loads values from environment variables or a local .env file.
    """
    # Core Service settings
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"
    debug: bool = False

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
