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
    debounce_seconds: float = 5.0

    # Clipboard settings
    clipboard_poll_interval: float = 5.0
    clipboard_min_length: int = 10
    clipboard_max_length: int = 50_000

    # History settings
    history_poll_interval: float = 30.0
    history_batch_size: int = 20
    history_min_command_length: int = 5
    history_skip_commands: frozenset[str] = frozenset({
        "ls", "cd", "pwd", "clear", "exit", "which", "echo",
        "cat", "less", "more", "head", "tail", "man",
    })

DEFAULT_CONFIG = VaultConfig()
