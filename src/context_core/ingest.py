from pathlib import Path
from datetime import datetime, timezone
from typing import Optional

from context_core.config import VaultConfig, DEFAULT_CONFIG
from context_core.models import Document, DocumentMetadata
from context_core.vault import Vault


def create_manual_document(
    content: str,
    tags: list[str] | None = None,
    source_type: str = "manual",
) -> Document:
    """Create a Document from raw text input."""
    metadata = DocumentMetadata(
        source_type=source_type,
        timestamp=datetime.now(timezone.utc).isoformat(),
        tags=tags or [],
    )
    doc = Document(content=content, metadata=metadata)
    doc.generate_id()
    return doc


def _chunk_text(text: str, max_chars: int, overlap: int) -> list[str]:
    """Split text into overlapping chunks, breaking at line boundaries."""
    if len(text) <= max_chars:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk: list[str] = []
    current_len = 0

    for line in lines:
        line_len = len(line) + 1  # +1 for newline
        if current_len + line_len > max_chars and current_chunk:
            chunks.append("\n".join(current_chunk))
            # Keep overlap by rewinding
            overlap_chunk: list[str] = []
            overlap_len = 0
            for prev_line in reversed(current_chunk):
                if overlap_len + len(prev_line) + 1 > overlap:
                    break
                overlap_chunk.insert(0, prev_line)
                overlap_len += len(prev_line) + 1
            current_chunk = overlap_chunk
            current_len = overlap_len

        current_chunk.append(line)
        current_len += line_len

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


def read_file(
    path: Path, config: VaultConfig = DEFAULT_CONFIG,
) -> Optional[Document]:
    """Read a single file and return a Document, or None if unsupported/too large."""
    if path.suffix.lower() not in config.supported_extensions:
        return None
    if not path.is_file():
        return None
    if path.stat().st_size > config.max_file_size_bytes:
        return None
    if path.stat().st_size == 0:
        return None

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None

    metadata = DocumentMetadata(
        source_type="file",
        timestamp=datetime.now(timezone.utc).isoformat(),
        file_path=str(path.resolve()),
        file_extension=path.suffix.lower(),
    )
    doc = Document(content=content, metadata=metadata)
    doc.generate_id()
    return doc


def read_file_chunked(
    path: Path, config: VaultConfig = DEFAULT_CONFIG,
) -> list[Document]:
    """Read a file and split into chunks if needed. Returns list of Documents."""
    if path.suffix.lower() not in config.supported_extensions:
        return []
    if not path.is_file():
        return []
    if path.stat().st_size > config.max_file_size_bytes:
        return []
    if path.stat().st_size == 0:
        return []

    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    chunks = _chunk_text(content, config.max_chunk_chars, config.chunk_overlap_chars)
    timestamp = datetime.now(timezone.utc).isoformat()
    file_path = str(path.resolve())
    ext = path.suffix.lower()
    docs = []

    for i, chunk in enumerate(chunks):
        metadata = DocumentMetadata(
            source_type="file",
            timestamp=timestamp,
            file_path=file_path,
            file_extension=ext,
        )
        if len(chunks) > 1:
            metadata.tags = [f"chunk:{i + 1}/{len(chunks)}"]
        doc = Document(content=chunk, metadata=metadata)
        doc.generate_id()
        docs.append(doc)

    return docs


def ingest_directory(
    directory: Path,
    vault: Vault,
    recursive: bool = True,
    config: VaultConfig = DEFAULT_CONFIG,
) -> tuple[int, int]:
    """
    Ingest all supported files from a directory.
    Returns (ingested_count, skipped_count).
    """
    ingested = 0
    skipped = 0
    pattern = "**/*" if recursive else "*"
    batch: list[Document] = []

    for path in directory.glob(pattern):
        if any(part.startswith(".") for part in path.relative_to(directory).parts):
            continue

        docs = read_file_chunked(path, config)
        if not docs:
            if path.is_file():
                skipped += 1
            continue

        batch.extend(docs)

        if len(batch) >= 50:
            vault.add(batch)
            ingested += len(batch)
            batch = []

    if batch:
        vault.add(batch)
        ingested += len(batch)

    return ingested, skipped
