"""
Application Configuration
Typed configuration management using Pydantic Settings.
"""
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = Field(default="DeepResearcher AI")
    environment: str = Field(default="development")
    debug: bool = Field(default=False)

    # Security passcode (protects API & Swagger UI)
    app_access_key: str = Field(default="researcher2026", alias="APP_ACCESS_KEY")

    # Google Gemini Settings
    gemini_api_key: str = Field(..., alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    # CORS
    allowed_origins: str = Field(default="*", alias="ALLOWED_ORIGINS")

    @property
    def cors_origins(self) -> list[str]:
        if self.allowed_origins == "*":
            return ["*"]
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
