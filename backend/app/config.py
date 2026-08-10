import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    APP_NAME: str = "RouteOpt Backend"
    OSRM_URL: str = os.getenv("OSRM_URL", "http://localhost:5000")
    
    model_config = SettingsConfigDict(env_file=".env")

settings = Settings()
