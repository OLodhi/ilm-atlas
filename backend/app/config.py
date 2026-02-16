from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # PostgreSQL
    database_url: str = "postgresql+asyncpg://ilmatlas:ilmatlas_dev@localhost:5432/ilmatlas"

    # Qdrant
    qdrant_url: str = "http://localhost:6333"
    qdrant_api_key: str = ""

    # OpenRouter (LLM)
    openrouter_api_key: str = ""
    openrouter_model: str = "qwen/qwen-2.5-72b-instruct"

    # Embedding model
    embedding_model: str = "BAAI/bge-m3"

    # Upload directory
    upload_dir: str = "./uploads"

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
