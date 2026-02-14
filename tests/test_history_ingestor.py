import pytest

from context_core.watcher.history_ingestor import HistoryIngestor
from context_core.watcher.state import WatcherState
from unittest.mock import MagicMock


@pytest.fixture
def state(tmp_path):
    s = WatcherState(db_path=tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def history_file(tmp_path):
    path = tmp_path / ".zsh_history"
    path.write_text(
        "git status\n"
        "python train.py --epochs 50 --lr 0.001\n"
        "docker compose up -d\n"
        "ls\n"
        "cd\n"
        "kubectl get pods -n production\n"
    )
    return path


@pytest.fixture
def mock_vault():
    return MagicMock()


class TestParseHistoryLine:
    def test_plain_format(self):
        ingestor = HistoryIngestor(MagicMock(), MagicMock())
        ingestor.shell_name = "zsh"
        assert ingestor.parse_history_line("git status") == "git status"

    def test_extended_format(self):
        ingestor = HistoryIngestor(MagicMock(), MagicMock())
        ingestor.shell_name = "zsh"
        line = ": 1234567890:0;git commit -m 'fix bug'"
        assert ingestor.parse_history_line(line) == "git commit -m 'fix bug'"

    def test_skip_empty(self):
        ingestor = HistoryIngestor(MagicMock(), MagicMock())
        ingestor.shell_name = "zsh"
        assert ingestor.parse_history_line("") is None
        assert ingestor.parse_history_line("   ") is None

    def test_skip_short_commands(self):
        ingestor = HistoryIngestor(MagicMock(), MagicMock())
        ingestor.shell_name = "zsh"
        assert ingestor.parse_history_line("ls") is None
        assert ingestor.parse_history_line("cd") is None
        assert ingestor.parse_history_line("pwd") is None

    def test_skip_common_commands(self):
        ingestor = HistoryIngestor(MagicMock(), MagicMock())
        ingestor.shell_name = "zsh"
        assert ingestor.parse_history_line("cat file.txt") is None
        assert ingestor.parse_history_line("echo hello world") is None

    def test_allow_interesting_commands(self):
        ingestor = HistoryIngestor(MagicMock(), MagicMock())
        ingestor.shell_name = "zsh"
        assert ingestor.parse_history_line("docker compose up -d") == "docker compose up -d"
        assert ingestor.parse_history_line("python train.py") == "python train.py"

    def test_full_path_command(self):
        ingestor = HistoryIngestor(MagicMock(), MagicMock())
        ingestor.shell_name = "zsh"
        assert ingestor.parse_history_line("/usr/bin/ls -la") is None

    def test_extended_format_with_skip(self):
        ingestor = HistoryIngestor(MagicMock(), MagicMock())
        ingestor.shell_name = "zsh"
        assert ingestor.parse_history_line(": 123:0;ls -la") is None


class TestIngestNewCommands:
    def test_ingest_from_start(self, mock_vault, state, history_file, monkeypatch):
        monkeypatch.setattr(
            HistoryIngestor, "_get_history_path", lambda self: ("zsh", history_file)
        )
        ingestor = HistoryIngestor(mock_vault, state)
        count = ingestor._ingest_new_commands()
        # git status, python train.py, docker compose, kubectl get pods = 4
        # ls, cd = skipped
        assert count == 4
        assert state.get_last_history_line() == 6

    def test_ingest_incremental(self, mock_vault, state, history_file, monkeypatch):
        monkeypatch.setattr(
            HistoryIngestor, "_get_history_path", lambda self: ("zsh", history_file)
        )
        ingestor = HistoryIngestor(mock_vault, state)
        ingestor._ingest_new_commands()

        # Add new lines
        with open(history_file, "a") as f:
            f.write("pip install requests\n")
            f.write("pytest -v tests/\n")

        count = ingestor._ingest_new_commands()
        assert count == 2
        assert state.get_last_history_line() == 8

    def test_no_new_lines(self, mock_vault, state, history_file, monkeypatch):
        monkeypatch.setattr(
            HistoryIngestor, "_get_history_path", lambda self: ("zsh", history_file)
        )
        ingestor = HistoryIngestor(mock_vault, state)
        ingestor._ingest_new_commands()
        count = ingestor._ingest_new_commands()
        assert count == 0

    def test_nonexistent_file(self, mock_vault, state, tmp_path, monkeypatch):
        monkeypatch.setattr(
            HistoryIngestor, "_get_history_path", lambda self: ("zsh", tmp_path / "nonexistent")
        )
        ingestor = HistoryIngestor(mock_vault, state)
        count = ingestor._ingest_new_commands()
        assert count == 0

    def test_file_truncation_resets(self, mock_vault, state, history_file, monkeypatch):
        monkeypatch.setattr(
            HistoryIngestor, "_get_history_path", lambda self: ("zsh", history_file)
        )
        ingestor = HistoryIngestor(mock_vault, state)
        ingestor._ingest_new_commands()
        assert state.get_last_history_line() == 6

        # Simulate truncation (file now shorter)
        history_file.write_text("new command after rotate\n")
        count = ingestor._ingest_new_commands()
        assert count == 1
        assert state.get_last_history_line() == 1
