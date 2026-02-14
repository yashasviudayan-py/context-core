from unittest.mock import patch, MagicMock
from click.testing import CliRunner

from context_core.cli import cli


class TestWatchCLI:
    def setup_method(self):
        self.runner = CliRunner()

    @patch("context_core.cli.check_ollama_running", return_value=True)
    @patch("context_core.watcher.daemon.start_daemon", return_value=12345)
    def test_watch_start(self, mock_start, mock_ollama):
        result = self.runner.invoke(cli, ["watch", "start"])
        assert result.exit_code == 0
        assert "12345" in result.output

    @patch("context_core.watcher.daemon.stop_daemon", return_value=True)
    def test_watch_stop(self, mock_stop):
        result = self.runner.invoke(cli, ["watch", "stop"])
        assert result.exit_code == 0
        assert "stopped" in result.output.lower()

    @patch("context_core.watcher.daemon.stop_daemon", return_value=False)
    def test_watch_stop_not_running(self, mock_stop):
        result = self.runner.invoke(cli, ["watch", "stop"])
        assert result.exit_code == 0
        assert "not running" in result.output.lower()

    @patch("context_core.watcher.daemon.daemon_status")
    def test_watch_status(self, mock_status):
        mock_status.return_value = {
            "status": "running",
            "pid": 12345,
            "started_at": "2025-01-01T00:00:00",
            "watched_directories": 3,
        }
        result = self.runner.invoke(cli, ["watch", "status"])
        assert result.exit_code == 0
        assert "12345" in result.output
        assert "3" in result.output

    @patch("context_core.watcher.state.WatcherState")
    def test_watch_add(self, mock_state_cls, tmp_path):
        mock_state = MagicMock()
        mock_state_cls.return_value = mock_state

        result = self.runner.invoke(cli, ["watch", "add", str(tmp_path)])
        assert result.exit_code == 0
        assert "watching" in result.output.lower()
        mock_state.add_directory.assert_called_once()

    @patch("context_core.watcher.state.WatcherState")
    def test_watch_remove(self, mock_state_cls, tmp_path):
        mock_state = MagicMock()
        mock_state.remove_directory.return_value = True
        mock_state_cls.return_value = mock_state

        result = self.runner.invoke(cli, ["watch", "remove", str(tmp_path)])
        assert result.exit_code == 0
        assert "removed" in result.output.lower()

    @patch("context_core.watcher.state.WatcherState")
    def test_watch_list_empty(self, mock_state_cls):
        mock_state = MagicMock()
        mock_state.list_directories.return_value = []
        mock_state_cls.return_value = mock_state

        result = self.runner.invoke(cli, ["watch", "list"])
        assert result.exit_code == 0
        assert "no directories" in result.output.lower()

    @patch("context_core.watcher.state.WatcherState")
    def test_watch_list_with_dirs(self, mock_state_cls):
        from context_core.watcher.state import WatchedDirectory

        mock_state = MagicMock()
        mock_state.list_directories.return_value = [
            WatchedDirectory(id=1, path="/tmp/a", added_at="2025-01-01", recursive=True),
            WatchedDirectory(id=2, path="/tmp/b", added_at="2025-01-02", recursive=False),
        ]
        mock_state_cls.return_value = mock_state

        result = self.runner.invoke(cli, ["watch", "list"])
        assert result.exit_code == 0
        assert "/tmp/a" in result.output
        assert "/tmp/b" in result.output

    def test_watch_start_no_ollama(self):
        with patch("context_core.cli.check_ollama_running", return_value=False):
            result = self.runner.invoke(cli, ["watch", "start"])
            assert result.exit_code != 0
            assert "Ollama" in result.output
