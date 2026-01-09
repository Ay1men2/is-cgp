from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str = Field(validation_alias="DATABASE_URL")
    redis_url: str = Field(validation_alias="REDIS_URL")
    inference_enabled: bool = Field(default=True, validation_alias="INFERENCE_ENABLED")
    inference_timeout_s: float = Field(default=30.0, validation_alias="INFERENCE_TIMEOUT_S")
    inference_retry_max: int = Field(default=2, validation_alias="INFERENCE_RETRY_MAX")
    inference_retry_backoff_s: float = Field(default=1.0, validation_alias="INFERENCE_RETRY_BACKOFF_S")

settings = Settings()
