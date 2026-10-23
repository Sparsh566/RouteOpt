import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "RouteOpt Commercial Fleet & AI Simulation Engine"
    OSRM_URL: str = os.getenv("OSRM_URL", "http://localhost:5000")
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    DEFAULT_REGION: str = "MUMBAI_MMRDA"
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000"
    ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
