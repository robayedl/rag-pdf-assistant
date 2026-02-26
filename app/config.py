from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "rag-pdf-assistant"
    environment: str = "local"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()