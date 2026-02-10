from context_core.models import Document, DocumentMetadata
from context_core.search import search_vault


class TestSearchVault:
    def _add_sample_docs(self, vault):
        docs = [
            Document(
                content="Python function to sort a list using quicksort",
                metadata=DocumentMetadata(
                    source_type="manual", timestamp="t",
                    tags=["python", "algorithm"],
                ),
            ),
            Document(
                content="JavaScript React component for a login form",
                metadata=DocumentMetadata(
                    source_type="file", timestamp="t",
                    file_path="/tmp/login.jsx", file_extension=".jsx",
                ),
            ),
            Document(
                content="SQL query to join users and orders tables",
                metadata=DocumentMetadata(
                    source_type="file", timestamp="t",
                    file_path="/tmp/query.sql", file_extension=".sql",
                ),
            ),
        ]
        for doc in docs:
            doc.generate_id()
        vault.add(docs)

    def test_basic_search(self, mock_vault):
        self._add_sample_docs(mock_vault)
        results = search_vault(mock_vault, "sorting algorithm")
        assert len(results) > 0

    def test_filter_by_source_type(self, mock_vault):
        self._add_sample_docs(mock_vault)
        results = search_vault(mock_vault, "code", source_type="file")
        for r in results:
            assert r.metadata["source_type"] == "file"

    def test_filter_by_extension(self, mock_vault):
        self._add_sample_docs(mock_vault)
        results = search_vault(mock_vault, "query", file_extension=".sql")
        assert len(results) == 1
        assert results[0].metadata["file_extension"] == ".sql"

    def test_filter_extension_auto_dot(self, mock_vault):
        self._add_sample_docs(mock_vault)
        results = search_vault(mock_vault, "query", file_extension="sql")
        assert len(results) == 1

    def test_min_similarity_filters(self, mock_vault):
        self._add_sample_docs(mock_vault)
        results = search_vault(mock_vault, "sorting", min_similarity=0.99)
        # With default embeddings, unlikely to get 0.99 similarity
        # This just tests the filter mechanism works
        assert all(r.similarity >= 0.99 for r in results)

    def test_empty_vault(self, mock_vault):
        results = search_vault(mock_vault, "anything")
        assert results == []
