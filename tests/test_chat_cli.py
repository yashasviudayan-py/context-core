from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from context_core.cli import cli


class TestChatCLI:
    def setup_method(self):
        self.runner = CliRunner()

    @patch("context_core.cli.check_ollama_running", return_value=False)
    def test_chat_ollama_not_running(self, mock_ollama):
        result = self.runner.invoke(cli, ["chat", "test query"])
        assert result.exit_code != 0
        assert "Ollama" in result.output

    @patch("context_core.cli.get_vault")
    @patch("context_core.cli.check_ollama_running", return_value=True)
    def test_chat_no_query_no_interactive(self, mock_ollama, mock_get_vault):
        mock_get_vault.return_value = MagicMock()
        with patch("context_core.ollama_client.detect_chat_model", return_value="llama3"):
            result = self.runner.invoke(cli, ["chat"])
            assert result.exit_code != 0
            assert "query" in result.output.lower() or "interactive" in result.output.lower()

    @patch("context_core.cli.get_vault")
    @patch("context_core.cli.check_ollama_running", return_value=True)
    def test_chat_no_models_available(self, mock_ollama, mock_get_vault):
        mock_get_vault.return_value = MagicMock()
        with patch("context_core.ollama_client.detect_chat_model", return_value=None):
            result = self.runner.invoke(cli, ["chat", "test"])
            assert result.exit_code != 0
            assert "No chat models" in result.output

    @patch("context_core.cli._chat_single")
    @patch("context_core.cli.get_vault")
    @patch("context_core.cli.check_ollama_running", return_value=True)
    def test_chat_single_query(self, mock_ollama, mock_get_vault, mock_single):
        mock_get_vault.return_value = MagicMock()
        with patch("context_core.ollama_client.detect_chat_model", return_value="llama3:latest"):
            result = self.runner.invoke(cli, ["chat", "what is foo?"])
            assert result.exit_code == 0
            mock_single.assert_called_once()
            # Verify the query was passed
            call_args = mock_single.call_args
            assert call_args[0][1] == "llama3:latest"
            assert call_args[0][2] == "what is foo?"

    @patch("context_core.cli._chat_single")
    @patch("context_core.cli.get_vault")
    @patch("context_core.cli.check_ollama_running", return_value=True)
    def test_chat_with_explicit_model(self, mock_ollama, mock_get_vault, mock_single):
        mock_get_vault.return_value = MagicMock()
        result = self.runner.invoke(cli, ["chat", "query", "--model", "mistral"])
        assert result.exit_code == 0
        call_args = mock_single.call_args
        assert call_args[0][1] == "mistral"

    @patch("context_core.cli._chat_repl")
    @patch("context_core.cli.get_vault")
    @patch("context_core.cli.check_ollama_running", return_value=True)
    def test_chat_interactive_mode(self, mock_ollama, mock_get_vault, mock_repl):
        mock_get_vault.return_value = MagicMock()
        with patch("context_core.ollama_client.detect_chat_model", return_value="llama3"):
            result = self.runner.invoke(cli, ["chat", "-i"])
            assert result.exit_code == 0
            mock_repl.assert_called_once()

    @patch("context_core.cli._chat_single")
    @patch("context_core.cli.get_vault")
    @patch("context_core.cli.check_ollama_running", return_value=True)
    def test_chat_custom_context_count(self, mock_ollama, mock_get_vault, mock_single):
        mock_get_vault.return_value = MagicMock()
        with patch("context_core.ollama_client.detect_chat_model", return_value="llama3"):
            result = self.runner.invoke(cli, ["chat", "query", "-c", "10"])
            assert result.exit_code == 0
