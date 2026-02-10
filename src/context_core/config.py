from pathlib import Path
from dataclasses import dataclass


@dataclass(frozen=True)
class VaultConfig:
    """Immutable configuration for the Vault."""

    chroma_path: Path = Path("./chroma_data")
    collection_name: str = "context_vault"
    ollama_url: str = "http://localhost:11434/api/embeddings"
    embedding_model: str = "nomic-embed-text"
    supported_extensions: tuple[str, ...] = (
        ".py", ".md", ".txt", ".js", ".ts", ".jsx", ".tsx",
        ".json", ".yaml", ".yml", ".toml", ".sh", ".bash",
        ".css", ".html", ".sql", ".rs", ".go", ".java",
    )
    max_file_size_bytes: int = 1_048_576  # 1 MB
    max_chunk_chars: int = 6000  # ~1500 tokens, safe for 8192-token embedding models
    chunk_overlap_chars: int = 200
    default_result_count: int = 10

    # Chat / Oracle settings
    ollama_base_url: str = "http://localhost:11434"
    chat_model: str | None = None  # None = auto-detect
    chat_context_results: int = 5
    chat_temperature: float = 0.7
    chat_max_context_chars: int = 8000


DEFAULT_CONFIG = VaultConfig()
