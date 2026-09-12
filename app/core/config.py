from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    LLM_PROVIDER: str = "google"
    LLM_MODEL: str = "gemini-3.6-flash"
    GOOGLE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # Embeddings
    EMBEDDING_MODEL: str = "BAAI/bge-small-en-v1.5"

    # Vector store
    QDRANT_URL: str = ""
    QDRANT_COLLECTION: str = "documents"
    QDRANT_LOCAL_PATH: str = "./qdrant_data"

    # Session storage
    DATABASE_URL: str = "sqlite:///./sessions.db"

    # Chunking
    CHUNK_SIZE: int = 800
    CHUNK_OVERLAP: int = 120

    # Retrieval
    TOP_K: int = 4

    LOG_LEVEL: str = "INFO"

    # API access
    # Shared-secret gate for /documents, /chat, /evaluate — see app/core/auth.py.
    # Empty (the local-dev default) disables the gate entirely.
    API_KEY: str = ""

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
