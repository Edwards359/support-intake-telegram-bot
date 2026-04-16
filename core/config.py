from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

PromptVariant = Literal["default", "alt"]


class Settings(BaseSettings):
    telegram_bot_token: str = Field(..., alias="TELEGRAM_BOT_TOKEN")
    operator_chat_id: int = Field(..., alias="OPERATOR_CHAT_ID")

    openai_api_key: str = Field(..., alias="OPENAI_API_KEY")
    openai_model: str = Field(default="gpt-5.4-mini-2026-03-17", alias="OPENAI_MODEL")
    openai_base_url: str = Field(default="https://api.openai.com/v1", alias="OPENAI_BASE_URL")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    crm_webhook_url: str | None = Field(default=None, alias="CRM_WEBHOOK_URL")
    crm_webhook_secret: str | None = Field(default=None, alias="CRM_WEBHOOK_SECRET")

    prompt_variant: PromptVariant = Field(default="default", alias="PROMPT_VARIANT")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        populate_by_name=True,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
