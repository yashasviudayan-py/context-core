from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional
import hashlib


@dataclass
class DocumentMetadata:
    """Metadata attached to every document in the vault."""

    source_type: str  # "manual", "file", "clipboard", "terminal"
    timestamp: str  # ISO 8601
    file_path: Optional[str] = None
    file_extension: Optional[str] = None
    tags: list[str] = field(default_factory=list)
    content_hash: Optional[str] = None

    def to_chroma_dict(self) -> dict:
        """Flatten to ChromaDB-compatible metadata (str/int/float/bool only)."""
        d: dict = {
            "source_type": self.source_type,
            "timestamp": self.timestamp,
        }
        if self.file_path:
            d["file_path"] = self.file_path
        if self.file_extension:
            d["file_extension"] = self.file_extension
        if self.tags:
            d["tags"] = ",".join(self.tags)
        if self.content_hash:
            d["content_hash"] = self.content_hash
        return d


@dataclass
class Document:
    """A document to be stored in the vault."""

    content: str
    metadata: DocumentMetadata
    id: Optional[str] = None

    def generate_id(self) -> str:
        """Deterministic ID from content hash for deduplication."""
        full_hash = hashlib.sha256(self.content.encode()).hexdigest()
        self.metadata.content_hash = full_hash
        self.id = f"doc_{full_hash[:16]}"
        return self.id


@dataclass
class SearchResult:
    """A single search result with relevance score."""

    content: str
    metadata: dict
    distance: float  # ChromaDB distance (lower = more similar)
    similarity: float  # 1 - distance
    document_id: str


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: str  # "system", "user", "assistant"
    content: str


@dataclass
class ChatResponse:
    """Response from the Oracle RAG pipeline."""

    content: str
    model: str
    context_ids: list[str] = field(default_factory=list)
    context_count: int = 0
