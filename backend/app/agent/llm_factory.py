"""
Pluggable LLM Provider Factory
Instantiates LangChain BaseChatModel instances dynamically based on environment configuration.
Supports:
- "gemini" (Default: Google Gemini 2.5 Flash via langchain-google-genai)
- "groq" (Groq Cloud Llama-3.3-70B via langchain-groq)
- "custom" (Hugging Face Serverless Inference, OpenRouter, or OpenAI-compatible endpoints)
"""
import logging
from langchain_core.language_models.chat_models import BaseChatModel
from app.config import get_settings

logger = logging.getLogger(__name__)


def get_llm(temperature: float = 0.2) -> BaseChatModel:
    """
    Returns a configured LangChain ChatModel based on LLM_PROVIDER in settings.
    """
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "gemini":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.gemini_api_key:
            raise ValueError("GEMINI_API_KEY is not configured in environment.")

        logger.info("Initializing Google Gemini model: %s", settings.gemini_model)
        return ChatGoogleGenerativeAI(
            model=settings.gemini_model,
            google_api_key=settings.gemini_api_key,
            api_version="v1beta",
            temperature=temperature,
        )

    elif provider == "groq":
        from langchain_groq import ChatGroq

        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is not configured in environment.")

        logger.info("Initializing Groq model: %s", settings.groq_model)
        return ChatGroq(
            model_name=settings.groq_model,
            groq_api_key=settings.groq_api_key,
            temperature=temperature,
        )

    elif provider in ("custom", "openai", "openrouter", "huggingface"):
        from langchain_openai import ChatOpenAI

        api_key = settings.custom_llm_api_key or "none"
        logger.info("Initializing custom OpenAI-compatible endpoint: %s (%s)", settings.custom_llm_model, settings.custom_llm_base_url)
        return ChatOpenAI(
            model=settings.custom_llm_model,
            api_key=api_key,
            base_url=settings.custom_llm_base_url,
            temperature=temperature,
        )

    else:
        raise ValueError(
            f"Unsupported LLM provider '{provider}'. Must be 'gemini', 'groq', or 'custom'."
        )
