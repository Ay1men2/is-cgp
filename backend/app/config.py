from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    rlm_glimpse_ttl_sec: int = Field(default=86400, validation_alias="RLM_GLIMPSE_TTL_SEC")
    app_env: str = Field(default="prod", validation_alias="APP_ENV")
    rlm_debug_options_enabled: bool = Field(
        default=False, validation_alias="RLM_DEBUG_OPTIONS_ENABLED"
    )
    rlm_debug_token: str | None = Field(default=None, validation_alias="RLM_DEBUG_TOKEN")

settings = Settings()
