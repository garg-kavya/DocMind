"""
Application Configuration
==========================

Purpose:
    Centralized configuration management using Pydantic BaseSettings.
    All configuration is loaded from environment variables, .env files,
    and configs/default.yaml with proper validation and type coercion.

Configuration Sections:

    AppSettings:
        - APP_NAME: str = "RAG PDF Q&A"
        - APP_VERSION: str = "0.1.0"
        - DEBUG: bool = False
        - LOG_LEVEL: str = "INFO"
        - UPLOAD_DIR: str = "./uploads"
        - MAX_UPLOAD_SIZE_MB: int = 50

    OpenAISettings:
        - OPENAI_API_KEY: str (required, secret)
        - EMBEDDING_MODEL: str = "text-embedding-3-small"
        - EMBEDDING_DIMENSIONS: int = 1536
        - EMBEDDING_BATCH_SIZE: int = 100
        - LLM_MODEL: str = "gpt-4o"
        - LLM_TEMPERATURE: float = 0.1
        - LLM_MAX_TOKENS: int = 1024

    ChunkingSettings:
        - CHUNK_SIZE_TOKENS: int = 512
            Justification: 512 tokens balances precision and context.
            256 is too granular (loses surrounding context, noisy retrieval).
            1024 is too broad (dilutes relevance, wastes LLM context window).
            512 allows ~5 chunks to fit in a 4K context budget with room
            for the prompt, history, and generated answer.
        - CHUNK_OVERLAP_TOKENS: int = 64
            12.5% overlap preserves cross-boundary information without
            excessive duplication in the vector store.
        - SPLIT_SEPARATORS: list[str] = ["\\n\\n", "\\n", ". ", " "]
            Hierarchical splitting: paragraphs > lines > sentences > words.

    RetrievalSettings:
        - VECTOR_STORE_TYPE: str = "faiss"  # "faiss" | "chroma"
        - TOP_K: int = 5
        - TOP_K_CANDIDATES: int = 10  # retrieve 2x for re-ranking
        - SIMILARITY_THRESHOLD: float = 0.70
        - MMR_DIVERSITY_FACTOR: float = 0.3

    SessionSettings:
        - SESSION_TTL_MINUTES: int = 60
        - MAX_CONVERSATION_TURNS: int = 10
        - SESSION_CLEANUP_INTERVAL_SECONDS: int = 300

    ServerSettings:
        - HOST: str = "0.0.0.0"
        - PORT: int = 8000
        - WORKERS: int = 1
        - CORS_ORIGINS: list[str] = ["*"]

Inputs:
    - Environment variables (highest priority)
    - .env file in project root
    - configs/default.yaml (lowest priority, base defaults)

Outputs:
    - Validated Settings singleton accessible via get_settings()

Dependencies:
    - pydantic-settings
    - pyyaml
"""
