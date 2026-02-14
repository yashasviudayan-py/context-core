import pytest
from unittest.mock import patch, MagicMock
import subprocess

from context_core.watcher.clipboard_monitor import ClipboardMonitor
from context_core.watcher.state import WatcherState


@pytest.fixture
def state(tmp_path):
    s = WatcherState(db_path=tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def monitor(state):
    vault = MagicMock()
    return ClipboardMonitor(vault, state)


class TestCheckAndIngest:
    def test_ingest_new_content(self, monitor):
        with patch.object(
            monitor, "_get_clipboard", return_value="This is some new clipboard content for testing"
        ):
            assert monitor.check_and_ingest() is True
            monitor.vault.add.assert_called_once()

    def test_skip_duplicate_content(self, monitor):
        content = "This is some clipboard content for testing"
        with patch.object(monitor, "_get_clipboard", return_value=content):
            monitor.check_and_ingest()
            monitor.check_and_ingest()
            # Only called once (second call is duplicate)
            assert monitor.vault.add.call_count == 1

    def test_skip_short_content(self, monitor):
        with patch.object(monitor, "_get_clipboard", return_value="short"):
            assert monitor.check_and_ingest() is False
            monitor.vault.add.assert_not_called()

    def test_skip_empty_content(self, monitor):
        with patch.object(monitor, "_get_clipboard", return_value=""):
            assert monitor.check_and_ingest() is False

    def test_skip_none_content(self, monitor):
        with patch.object(monitor, "_get_clipboard", return_value=None):
            assert monitor.check_and_ingest() is False

    def test_skip_too_long(self, monitor):
        with patch.object(monitor, "_get_clipboard", return_value="x" * 60_000):
            assert monitor.check_and_ingest() is False

    def test_strips_whitespace(self, monitor):
        with patch.object(
            monitor, "_get_clipboard", return_value="  some clipboard content with spaces  "
        ):
            monitor.check_and_ingest()
            call_args = monitor.vault.add.call_args[0][0]
            assert call_args[0].content == "some clipboard content with spaces"


class TestGetClipboard:
    def test_successful_pbpaste(self, monitor):
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "clipboard text"
        with patch(
            "context_core.watcher.clipboard_monitor.shutil.which", return_value="/usr/bin/pbpaste"
        ):
            with patch(
                "context_core.watcher.clipboard_monitor.subprocess.run", return_value=mock_result
            ):
                assert monitor._get_clipboard() == "clipboard text"

    def test_pbpaste_failure(self, monitor):
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.args = ["pbpaste"]
        with patch(
            "context_core.watcher.clipboard_monitor.shutil.which", return_value="/usr/bin/pbpaste"
        ):
            with patch(
                "context_core.watcher.clipboard_monitor.subprocess.run", return_value=mock_result
            ):
                with pytest.raises(subprocess.CalledProcessError):
                    monitor._get_clipboard()

    def test_pbpaste_timeout(self, monitor):
        with patch(
            "context_core.watcher.clipboard_monitor.shutil.which", return_value="/usr/bin/pbpaste"
        ):
            with patch(
                "context_core.watcher.clipboard_monitor.subprocess.run",
                side_effect=subprocess.TimeoutExpired(cmd="pbpaste", timeout=2),
            ):
                assert monitor._get_clipboard() is None

    def test_pbpaste_not_found(self, monitor):
        with patch(
            "context_core.watcher.clipboard_monitor.shutil.which", return_value="/usr/bin/pbpaste"
        ):
            with patch(
                "context_core.watcher.clipboard_monitor.subprocess.run",
                side_effect=FileNotFoundError,
            ):
                assert monitor._get_clipboard() is None


class TestLifecycle:
    def test_start_stop(self, monitor):
        with patch.object(monitor, "_get_clipboard", return_value=None):
            monitor.start()
            assert monitor._thread is not None
            assert monitor._thread.is_alive()
            monitor.stop()
            assert not monitor._thread.is_alive()
