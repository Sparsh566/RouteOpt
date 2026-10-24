import os
from typing import Any

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    APP_NAME: str = "RouteOpt Commercial Fleet & AI Simulation Engine"
    OSRM_URL: str = os.getenv("OSRM_URL", "http://localhost:5000")
    GROQ_API_KEY: str | None = os.getenv("GROQ_API_KEY")
    ROUTEOPT_API_KEY: str | None = os.getenv("ROUTEOPT_API_KEY")
    DEFAULT_REGION: str = "MUMBAI_MMRDA"
    RATE_LIMIT_PER_MINUTE: int = int(os.getenv("RATE_LIMIT_PER_MINUTE", "60"))
    ALLOWED_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8000",
    ]

    @field_validator("ALLOWED_ORIGINS", mode="before")
    @classmethod
    def parse_allowed_origins(cls, v: Any) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        if isinstance(v, (list, tuple)):
            return list(v)
        return [
            "http://localhost:3000",
            "http://localhost:8000",
            "http://127.0.0.1:3000",
            "http://127.0.0.1:8000",
        ]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
