from context_core.ingest import create_manual_document, read_file, ingest_directory
from context_core.config import VaultConfig


class TestCreateManualDocument:
    def test_basic(self):
        doc = create_manual_document("hello world")
        assert doc.content == "hello world"
        assert doc.metadata.source_type == "manual"
        assert doc.id is not None
        assert doc.id.startswith("doc_")

    def test_with_tags(self):
        doc = create_manual_document("test", tags=["python", "fix"])
        assert doc.metadata.tags == ["python", "fix"]

    def test_custom_source_type(self):
        doc = create_manual_document("test", source_type="clipboard")
        assert doc.metadata.source_type == "clipboard"


class TestReadFile:
    def test_read_python_file(self, sample_dir):
        doc = read_file(sample_dir / "hello.py")
        assert doc is not None
        assert "def hello" in doc.content
        assert doc.metadata.source_type == "file"
        assert doc.metadata.file_extension == ".py"

    def test_read_markdown_file(self, sample_dir):
        doc = read_file(sample_dir / "notes.md")
        assert doc is not None
        assert "# Notes" in doc.content

    def test_skip_unsupported_extension(self, sample_dir):
        doc = read_file(sample_dir / "data.bin")
        assert doc is None

    def test_skip_empty_file(self, sample_dir):
        doc = read_file(sample_dir / "empty.py")
        assert doc is None

    def test_skip_nonexistent(self, tmp_path):
        doc = read_file(tmp_path / "nope.py")
        assert doc is None

    def test_skip_too_large(self, tmp_path):
        big = tmp_path / "big.py"
        big.write_text("x" * 2_000_000)
        config = VaultConfig(max_file_size_bytes=1_000_000)
        doc = read_file(big, config)
        assert doc is None


class TestIngestDirectory:
    def test_ingest_counts(self, sample_dir, mock_vault):
        ingested, skipped = ingest_directory(sample_dir, mock_vault)
        # hello.py, notes.md, readme.txt, subdir/nested.py = 4 ingested
        # data.bin = 1 skipped (unsupported), empty.py = 1 skipped (empty)
        # .secret = hidden, not counted
        assert ingested == 4
        assert skipped == 2

    def test_ingest_non_recursive(self, sample_dir, mock_vault):
        ingested, skipped = ingest_directory(sample_dir, mock_vault, recursive=False)
        # Only top-level: hello.py, notes.md, readme.txt = 3
        # Skipped: data.bin, empty.py = 2
        assert ingested == 3
        assert skipped == 2

    def test_ingest_populates_vault(self, sample_dir, mock_vault):
        ingest_directory(sample_dir, mock_vault)
        assert mock_vault.count == 4

    def test_ingest_idempotent(self, sample_dir, mock_vault):
        ingest_directory(sample_dir, mock_vault)
        ingest_directory(sample_dir, mock_vault)
        assert mock_vault.count == 4  # upsert, no duplicates
