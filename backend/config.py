from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    ADMIN_EMAIL:    str = ""
    ADMIN_PASSWORD: str = ""
    ADMIN_SECRET:   str
    GMAIL_USER:         str = ""
    GMAIL_APP_PASSWORD: str = ""
    OPENAI_API_KEY: str = ""  # OpenAI API key for AI analysis
    PINECONE_API_KEY: str = ""
    PINECONE_ENVIRONMENT: str = ""
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

@lru_cache()
def get_settings():
    return Settings()
