from context_core.models import Document, DocumentMetadata


class TestVault:
    def test_add_and_count(self, mock_vault):
        doc = Document(
            content="def hello(): return 'world'",
            metadata=DocumentMetadata(source_type="manual", timestamp="t"),
        )
        doc.generate_id()
        mock_vault.add([doc])
        assert mock_vault.count == 1

    def test_add_multiple(self, mock_vault):
        docs = []
        for i in range(5):
            doc = Document(
                content=f"document number {i}",
                metadata=DocumentMetadata(source_type="manual", timestamp="t"),
            )
            doc.generate_id()
            docs.append(doc)
        mock_vault.add(docs)
        assert mock_vault.count == 5

    def test_upsert_deduplicates(self, mock_vault):
        doc1 = Document(
            content="same content",
            metadata=DocumentMetadata(source_type="manual", timestamp="t1"),
        )
        doc1.generate_id()
        doc2 = Document(
            content="same content",
            metadata=DocumentMetadata(source_type="manual", timestamp="t2"),
        )
        doc2.generate_id()

        mock_vault.add([doc1])
        mock_vault.add([doc2])
        assert mock_vault.count == 1

    def test_delete(self, mock_vault):
        doc = Document(
            content="to be deleted",
            metadata=DocumentMetadata(source_type="manual", timestamp="t"),
        )
        doc.generate_id()
        mock_vault.add([doc])
        assert mock_vault.count == 1

        mock_vault.delete([doc.id])
        assert mock_vault.count == 0

    def test_query_returns_results(self, mock_vault):
        doc = Document(
            content="Python function for sorting a list",
            metadata=DocumentMetadata(source_type="manual", timestamp="t"),
        )
        doc.generate_id()
        mock_vault.add([doc])

        results = mock_vault.query("sort list", n_results=5)
        assert len(results) == 1
        assert results[0].document_id == doc.id
        assert results[0].content == doc.content

    def test_query_empty_vault(self, mock_vault):
        results = mock_vault.query("anything", n_results=5)
        assert results == []

    def test_peek(self, mock_vault):
        doc = Document(
            content="peek test",
            metadata=DocumentMetadata(source_type="manual", timestamp="t"),
        )
        doc.generate_id()
        mock_vault.add([doc])

        data = mock_vault.peek(n=5)
        assert len(data["ids"]) == 1

    def test_stats(self, mock_vault):
        info = mock_vault.stats()
        assert "total_documents" in info
        assert "collection_name" in info
        assert "embedding_model" in info
        assert "storage_path" in info
