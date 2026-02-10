import os
import pytest
from unittest.mock import patch, MagicMock

from context_core.watcher.daemon import (
    _is_process_running,
    start_daemon,
    stop_daemon,
    daemon_status,
)
from context_core.watcher.state import WatcherState


@pytest.fixture
def state(tmp_path):
    s = WatcherState(db_path=tmp_path / "test.db")
    yield s
    s.close()


class TestIsProcessRunning:
    def test_current_process(self):
        assert _is_process_running(os.getpid()) is True

    def test_nonexistent_pid(self):
        # PID 99999999 is almost certainly not running
        assert _is_process_running(99999999) is False


class TestDaemonStatus:
    def test_status_when_not_running(self, state, tmp_path):
        with patch("context_core.watcher.daemon.WatcherState", return_value=state):
            info = daemon_status()
            assert info["status"] == "stopped"
            assert info["pid"] is None
            assert info["watched_directories"] == 0

    def test_status_with_stale_pid(self, state, tmp_path):
        state.set_daemon_pid(99999999)  # non-existent PID
        with patch("context_core.watcher.daemon.WatcherState", return_value=state):
            info = daemon_status()
            assert info["status"] == "stopped"
            assert info["pid"] is None
            assert "stale" in info.get("note", "").lower()

    def test_status_with_watched_dirs(self, state, tmp_path):
        state.add_directory("/tmp/a")
        state.add_directory("/tmp/b")
        with patch("context_core.watcher.daemon.WatcherState", return_value=state):
            info = daemon_status()
            assert info["watched_directories"] == 2


class TestStopDaemon:
    def test_stop_when_not_running(self, state):
        with patch("context_core.watcher.daemon.WatcherState", return_value=state):
            assert stop_daemon() is False

    def test_stop_clears_stale_pid(self, state):
        state.set_daemon_pid(99999999)
        with patch("context_core.watcher.daemon.WatcherState", return_value=state):
            assert stop_daemon() is False
            assert state.get_daemon_pid() is None


class TestStartDaemon:
    def test_returns_existing_pid_if_running(self, state):
        state.set_daemon_pid(os.getpid())  # current process is "running"
        with patch("context_core.watcher.daemon.WatcherState", return_value=state):
            pid = start_daemon(foreground=False)
            assert pid == os.getpid()
