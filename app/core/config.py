from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # LLM
    LLM_PROVIDER: str = "google"
    LLM_MODEL: str = "gemini-3.6-flash"
    GOOGLE_API_KEY: str = ""
    ANTHROPIC_API_KEY: str = ""

    # LLM call resilience — see app/services/llm_client.py. Neither provider
    # client had an explicit timeout before this, so a hung connection could
    # hang a /chat request indefinitely. Retries use each SDK's own native
    # exponential backoff (HttpRetryOptions / httpx-based), not a hand-rolled
    # loop — LLM_MAX_RETRIES is retry *attempts*, so 2 means up to 3 calls total.
    LLM_TIMEOUT_SECONDS: int = 30
    LLM_MAX_RETRIES: int = 2

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

    # Tracing — see app/core/tracing.py. Empty (dev default): spans print to
    # the console, zero external services. Set to any OTel-compatible
    # collector endpoint (Jaeger, Grafana Tempo, Honeycomb, ...) to export
    # real traces instead — same local-first-dev/production-shaped-deploy
    # split as Qdrant/Postgres above.
    OTEL_EXPORTER_OTLP_ENDPOINT: str = ""

    # Data boundary — see app/services/data_boundary.py. "block" rejects
    # ingestion of anything matching a sensitive-data pattern (the exact gap
    # that let a real tuition-payment letter with bank details reach the
    # public demo, see docs/DEPLOYMENT.md); "warn" logs but allows it; "off"
    # disables the check entirely. Default is the strict setting on purpose.
    DATA_BOUNDARY_MODE: str = "block"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
