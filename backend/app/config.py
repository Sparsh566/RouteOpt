import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    APP_NAME: str = "RouteOpt Commercial Fleet & AI Simulation Engine"
    OSRM_URL: str = os.getenv("OSRM_URL", "http://localhost:5000")
    GROQ_API_KEY: Optional[str] = os.getenv("GROQ_API_KEY")
    GROK_API_KEY: Optional[str] = os.getenv("GROK_API_KEY") or os.getenv("XAI_API_KEY")
    DEFAULT_REGION: str = "MUMBAI_MMRDA"
    
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

settings = Settings()
