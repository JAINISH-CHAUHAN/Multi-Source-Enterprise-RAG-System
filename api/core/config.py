from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str
    APP_ENV: str
    SECRET_KEY: str
    ACCESS_TOKEN_EXPIRE_MINUTES: int

    DATABASE_URL: str

    # LLM roles
    LLM_PRIMARY_PROVIDER: str
    LLM_PRIMARY_MODEL: str

    # Embedding roles
    EMBEDDINGS_DEFAULT_PROVIDER: str
    EMBEDDINGS_DEFAULT_MODEL: str

    REDIS_URL: str = "redis://localhost:6379/0"
    class Config:
        env_file = ".env"

settings = Settings()
