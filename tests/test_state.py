import pytest
import sqlite3

from context_core.watcher.state import WatcherState


@pytest.fixture
def state(tmp_path):
    s = WatcherState(db_path=tmp_path / "test.db")
    yield s
    s.close()


class TestWatchedDirectories:
    def test_add_directory(self, state):
        d = state.add_directory("/tmp/project")
        assert d.path == "/tmp/project"
        assert d.recursive is True
        assert d.id is not None

    def test_add_non_recursive(self, state):
        d = state.add_directory("/tmp/project", recursive=False)
        assert d.recursive is False

    def test_add_duplicate_raises(self, state):
        state.add_directory("/tmp/project")
        with pytest.raises(sqlite3.IntegrityError):
            state.add_directory("/tmp/project")

    def test_remove_directory(self, state):
        state.add_directory("/tmp/project")
        assert state.remove_directory("/tmp/project") is True
        assert state.list_directories() == []

    def test_remove_nonexistent(self, state):
        assert state.remove_directory("/tmp/nope") is False

    def test_list_directories(self, state):
        state.add_directory("/tmp/a")
        state.add_directory("/tmp/b")
        dirs = state.list_directories()
        assert len(dirs) == 2
        assert dirs[0].path == "/tmp/a"
        assert dirs[1].path == "/tmp/b"

    def test_list_empty(self, state):
        assert state.list_directories() == []


class TestFileState:
    def test_upsert_and_get(self, state):
        state.upsert_file_state("/tmp/file.py", "abc123", 1234567890.0)
        result = state.get_file_state("/tmp/file.py")
        assert result is not None
        assert result["content_hash"] == "abc123"
        assert result["mtime"] == 1234567890.0

    def test_upsert_overwrites(self, state):
        state.upsert_file_state("/tmp/file.py", "hash1", 1.0)
        state.upsert_file_state("/tmp/file.py", "hash2", 2.0)
        result = state.get_file_state("/tmp/file.py")
        assert result["content_hash"] == "hash2"
        assert result["mtime"] == 2.0

    def test_get_nonexistent(self, state):
        assert state.get_file_state("/tmp/nope.py") is None

    def test_remove(self, state):
        state.upsert_file_state("/tmp/file.py", "hash", 1.0)
        state.remove_file_state("/tmp/file.py")
        assert state.get_file_state("/tmp/file.py") is None


class TestClipboardState:
    def test_initial_empty(self, state):
        assert state.get_last_clipboard_hash() == ""

    def test_set_and_get(self, state):
        state.set_last_clipboard_hash("abc123")
        assert state.get_last_clipboard_hash() == "abc123"

    def test_overwrite(self, state):
        state.set_last_clipboard_hash("first")
        state.set_last_clipboard_hash("second")
        assert state.get_last_clipboard_hash() == "second"


class TestHistoryState:
    def test_initial_zero(self, state):
        assert state.get_last_history_line() == 0

    def test_set_and_get(self, state):
        state.set_last_history_line(42)
        assert state.get_last_history_line() == 42

    def test_overwrite(self, state):
        state.set_last_history_line(10)
        state.set_last_history_line(20)
        assert state.get_last_history_line() == 20


class TestDaemonState:
    def test_initial_no_pid(self, state):
        assert state.get_daemon_pid() is None

    def test_set_and_get_pid(self, state):
        state.set_daemon_pid(12345)
        assert state.get_daemon_pid() == 12345

    def test_clear_pid(self, state):
        state.set_daemon_pid(12345)
        state.clear_daemon_pid()
        assert state.get_daemon_pid() is None

    def test_daemon_status_default(self, state):
        status = state.get_daemon_status()
        assert status["status"] == "stopped"
        assert status["pid"] is None

    def test_daemon_status_running(self, state):
        state.set_daemon_pid(99)
        status = state.get_daemon_status()
        assert status["status"] == "running"
        assert status["pid"] == 99

    def test_daemon_status_after_clear(self, state):
        state.set_daemon_pid(99)
        state.clear_daemon_pid()
        status = state.get_daemon_status()
        assert status["status"] == "stopped"
