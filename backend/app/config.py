from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    rlm_glimpse_ttl_sec: int = Field(default=3600, validation_alias="RLM_GLIMPSE_TTL_SEC")

settings = Settings()
