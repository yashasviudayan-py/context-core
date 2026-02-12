import pytest

import chromadb

from context_core.config import VaultConfig
from context_core.vault import Vault


@pytest.fixture
def temp_config(tmp_path):
    """Config pointing to a temporary directory."""
    return VaultConfig(chroma_path=tmp_path / "test_chroma")


@pytest.fixture
def mock_vault(temp_config):
    """Vault with ChromaDB's default embedding (no Ollama needed)."""
    vault = Vault.__new__(Vault)
    vault.config = temp_config
    vault._client = chromadb.PersistentClient(path=str(temp_config.chroma_path))
    vault._embedding_fn = None
    vault._collection = vault._client.get_or_create_collection(
        name="test_vault",
        metadata={"hnsw:space": "cosine"},
    )
    return vault


@pytest.fixture
def sample_dir(tmp_path):
    """Create a temporary directory with sample files for ingestion tests."""
    root = tmp_path / "sample_files"
    root.mkdir()

    # Python file
    (root / "hello.py").write_text("def hello():\n    return 'world'\n")

    # Markdown file
    (root / "notes.md").write_text("# Notes\nThis is a test markdown file.\n")

    # Text file
    (root / "readme.txt").write_text("This is a plain text readme file.\n")

    # Unsupported file (binary-ish)
    (root / "data.bin").write_bytes(b"\x00\x01\x02\x03")

    # Hidden file (should be skipped)
    (root / ".secret").write_text("secret stuff")

    # Empty file (should be skipped)
    (root / "empty.py").write_text("")

    # Subdirectory with a file
    sub = root / "subdir"
    sub.mkdir()
    (sub / "nested.py").write_text("x = 42\n")

    return root
