import chromadb
from chromadb.utils.embedding_functions import OllamaEmbeddingFunction

from context_core.config import VaultConfig, DEFAULT_CONFIG
from context_core.models import Document, SearchResult


class Vault:
    """The core vector store interface for Context Core."""

    def __init__(self, config: VaultConfig = DEFAULT_CONFIG):
        self.config = config
        self._embedding_fn = OllamaEmbeddingFunction(
            model_name=config.embedding_model,
            url=config.ollama_url,
        )
        self._client = chromadb.PersistentClient(
            path=str(config.chroma_path),
        )
        self._collection = self._client.get_or_create_collection(
            name=config.collection_name,
            embedding_function=self._embedding_fn,
            metadata={"hnsw:space": "cosine"},
        )

    @property
    def count(self) -> int:
        """Number of documents in the vault."""
        return self._collection.count()

    def add(self, documents: list[Document]) -> int:
        """Add documents to the vault (upserts). Returns number added."""
        for doc in documents:
            if not doc.id:
                doc.generate_id()

        self._collection.upsert(
            ids=[doc.id for doc in documents],
            documents=[doc.content for doc in documents],
            metadatas=[doc.metadata.to_chroma_dict() for doc in documents],
        )
        return len(documents)

    def query(
        self,
        query_text: str,
        n_results: int = 10,
        where: dict | None = None,
        where_document: dict | None = None,
    ) -> list[SearchResult]:
        """Semantic search. Returns results sorted by relevance."""
        results = self._collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            where_document=where_document,
            include=["documents", "metadatas", "distances"],
        )

        search_results = []
        if results["ids"] and results["ids"][0]:
            for i, doc_id in enumerate(results["ids"][0]):
                distance = results["distances"][0][i]
                search_results.append(
                    SearchResult(
                        content=results["documents"][0][i],
                        metadata=results["metadatas"][0][i],
                        distance=distance,
                        similarity=1.0 - distance,
                        document_id=doc_id,
                    )
                )
        return search_results

    def delete(self, ids: list[str]) -> None:
        """Delete documents by ID."""
        self._collection.delete(ids=ids)

    def peek(self, n: int = 5) -> dict:
        """Preview the first n documents in the collection."""
        return self._collection.peek(limit=n)

    def stats(self) -> dict:
        """Return vault statistics."""
        return {
            "total_documents": self.count,
            "collection_name": self.config.collection_name,
            "embedding_model": self.config.embedding_model,
            "storage_path": str(self.config.chroma_path),
        }
