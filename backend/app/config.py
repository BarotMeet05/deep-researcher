"""
Application Configuration
Typed configuration management using Pydantic Settings.
Supports multiple LLM providers (Google Gemini, Groq, OpenRouter, HuggingFace, Custom OpenAI-compatible).
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
    app_access_key: str = Field(default="", alias="APP_ACCESS_KEY")

    # Search Engine: Tavily API Key (Optional, falls back to DuckDuckGo if empty)
    tavily_api_key: str = Field(default="", alias="TAVILY_API_KEY")

    # LLM Provider Selection: "gemini" | "groq" | "custom" (OpenAI-compatible)
    llm_provider: str = Field(default="gemini", alias="LLM_PROVIDER")

    # Google Gemini Settings (Default)
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")

    # Groq Settings (Alternative Free Tier)
    groq_api_key: str = Field(default="", alias="GROQ_API_KEY")
    groq_model: str = Field(default="llama-3.3-70b-versatile", alias="GROQ_MODEL")

    # Custom / OpenRouter / HuggingFace OpenAI-compatible Settings
    custom_llm_api_key: str = Field(default="", alias="CUSTOM_LLM_API_KEY")
    custom_llm_model: str = Field(default="meta-llama/Llama-3.1-8B-Instruct", alias="CUSTOM_LLM_MODEL")
    custom_llm_base_url: str = Field(default="https://api-inference.huggingface.co/v1", alias="CUSTOM_LLM_BASE_URL")

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
