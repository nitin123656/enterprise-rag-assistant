import os
from pathlib import Path
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
load_dotenv(ROOT_DIR / ".env")

class Settings:
    app_name: str = "Enterprise Document Knowledge Assistant"
    data_dir: Path = Path(os.getenv("CHROMA_PATH", str(ROOT_DIR / "data" / "chroma")))
    cors_origins: list[str] = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS",
            "http://localhost:5173,http://127.0.0.1:5173,https://enterprise-rag-assistant-six.vercel.app",
        ).split(",")
        if origin.strip()
    ]
    collection_name: str = os.getenv("CHROMA_COLLECTION", "enterprise_documents")
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
    gemini_fallback_model: str = os.getenv("GEMINI_FALLBACK_MODEL", "gemini-3.5-flash")
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1200"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "100"))
    top_k: int = int(os.getenv("TOP_K", "3"))
    # Chroma cosine distance: lower is more similar. Tune on representative documents.
    max_cosine_distance: float = float(os.getenv("MAX_COSINE_DISTANCE", "0.85"))
    max_upload_mb: int = int(os.getenv("MAX_UPLOAD_MB", "15"))

settings = Settings()
