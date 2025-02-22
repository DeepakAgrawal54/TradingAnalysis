from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    openai_api_key: str
    alpha_vantage_key: str
    FRED_API_KEY: str
    newsapi_key: str
    reddit_client_id: str
    reddit_client_secret: str
    cache_ttl: int = 3600
    groq_api_key: str
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()
