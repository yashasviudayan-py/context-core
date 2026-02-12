from context_core.models import Document, DocumentMetadata


class TestDocumentMetadata:
    def test_to_chroma_dict_basic(self):
        meta = DocumentMetadata(
            source_type="manual",
            timestamp="2025-01-01T00:00:00+00:00",
        )
        d = meta.to_chroma_dict()
        assert d == {
            "source_type": "manual",
            "timestamp": "2025-01-01T00:00:00+00:00",
        }

    def test_to_chroma_dict_with_all_fields(self):
        meta = DocumentMetadata(
            source_type="file",
            timestamp="2025-01-01T00:00:00+00:00",
            file_path="/tmp/test.py",
            file_extension=".py",
            tags=["python", "test"],
            content_hash="abc123",
        )
        d = meta.to_chroma_dict()
        assert d["file_path"] == "/tmp/test.py"
        assert d["file_extension"] == ".py"
        assert d["tags"] == "python,test"
        assert d["content_hash"] == "abc123"

    def test_to_chroma_dict_omits_none_fields(self):
        meta = DocumentMetadata(source_type="manual", timestamp="t")
        d = meta.to_chroma_dict()
        assert "file_path" not in d
        assert "file_extension" not in d
        assert "tags" not in d
        assert "content_hash" not in d


class TestDocument:
    def test_generate_id_is_deterministic(self):
        doc1 = Document(
            content="hello world",
            metadata=DocumentMetadata(source_type="manual", timestamp="t"),
        )
        doc2 = Document(
            content="hello world",
            metadata=DocumentMetadata(source_type="file", timestamp="t2"),
        )
        assert doc1.generate_id() == doc2.generate_id()

    def test_generate_id_sets_hash(self):
        doc = Document(
            content="test",
            metadata=DocumentMetadata(source_type="manual", timestamp="t"),
        )
        doc.generate_id()
        assert doc.metadata.content_hash is not None
        assert doc.id.startswith("doc_")

    def test_different_content_different_id(self):
        doc1 = Document(
            content="hello",
            metadata=DocumentMetadata(source_type="manual", timestamp="t"),
        )
        doc2 = Document(
            content="world",
            metadata=DocumentMetadata(source_type="manual", timestamp="t"),
        )
        assert doc1.generate_id() != doc2.generate_id()
