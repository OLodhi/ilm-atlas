from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    database_url: str = "postgresql+asyncpg://ilmatlas:ilmatlas_dev@localhost:5432/ilmatlas"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # Hadith API
    hadith_api_key: str = ""

    # OpenRouter (LLM)
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen3-max"

    # Embedding model
    embedding_model: str = "BAAI/bge-m3"

    # Upload directory
    upload_dir: str = "./uploads"

    # Frontend URL (for CORS)
    frontend_url: str = "http://localhost:3000"

    # Auth
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 30

    # Email (Resend)
    resend_api_key: str = ""
    email_from: str = "noreply@ilmatlas.com"
    email_verification_expire_hours: int = 24
    password_reset_expire_hours: int = 1

    # Rate limits
    default_daily_query_limit: int = 50
    anonymous_daily_query_limit: int = 10

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
