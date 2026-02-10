from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from context_core.cli import cli


class TestCLI:
    def setup_method(self):
        self.runner = CliRunner()

    def test_version(self):
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    @patch("context_core.cli.get_vault")
    def test_add(self, mock_get_vault):
        mock_vault = MagicMock()
        mock_get_vault.return_value = mock_vault

        result = self.runner.invoke(cli, ["add", "hello world"])
        assert result.exit_code == 0
        assert "Added" in result.output
        mock_vault.add.assert_called_once()

    @patch("context_core.cli.get_vault")
    def test_add_with_tags(self, mock_get_vault):
        mock_vault = MagicMock()
        mock_get_vault.return_value = mock_vault

        result = self.runner.invoke(cli, ["add", "test", "--tags", "py,fix"])
        assert result.exit_code == 0
        mock_vault.add.assert_called_once()

    @patch("context_core.cli.get_vault")
    def test_stats(self, mock_get_vault):
        mock_vault = MagicMock()
        mock_vault.stats.return_value = {
            "total_documents": 10,
            "collection_name": "test",
            "embedding_model": "nomic-embed-text",
            "storage_path": "/tmp/chroma",
        }
        mock_get_vault.return_value = mock_vault

        result = self.runner.invoke(cli, ["stats"])
        assert result.exit_code == 0
        assert "10" in result.output

    @patch("context_core.cli.get_vault")
    def test_search_no_results(self, mock_get_vault):
        mock_vault = MagicMock()
        mock_vault.query.return_value = []
        mock_get_vault.return_value = mock_vault

        # Patch search_vault to return empty
        with patch("context_core.cli.search_vault", return_value=[]):
            result = self.runner.invoke(cli, ["search", "nothing"])
            assert result.exit_code == 0
            assert "No results found" in result.output

    @patch("context_core.cli.get_vault")
    def test_delete(self, mock_get_vault):
        mock_vault = MagicMock()
        mock_get_vault.return_value = mock_vault

        result = self.runner.invoke(cli, ["delete", "doc_abc123"])
        assert result.exit_code == 0
        assert "Deleted" in result.output
        mock_vault.delete.assert_called_once_with(["doc_abc123"])

    @patch("context_core.cli.get_vault")
    def test_peek_empty(self, mock_get_vault):
        mock_vault = MagicMock()
        mock_vault.peek.return_value = {"ids": []}
        mock_get_vault.return_value = mock_vault

        result = self.runner.invoke(cli, ["peek"])
        assert result.exit_code == 0
        assert "empty" in result.output.lower()

    def test_ollama_not_running(self):
        with patch("context_core.cli.check_ollama_running", return_value=False):
            result = self.runner.invoke(cli, ["stats"])
            assert result.exit_code != 0
            assert "Ollama is not running" in result.output
