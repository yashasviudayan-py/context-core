import pytest
import time
from pathlib import Path
from unittest.mock import MagicMock

from context_core.watcher.file_watcher import VaultFileHandler, FileWatcher
from context_core.watcher.state import WatcherState
from context_core.config import VaultConfig


@pytest.fixture
def state(tmp_path):
    s = WatcherState(db_path=tmp_path / "test.db")
    yield s
    s.close()


@pytest.fixture
def watch_dir(tmp_path):
    d = tmp_path / "watched"
    d.mkdir()
    return d


@pytest.fixture
def handler(mock_vault, state):
    return VaultFileHandler(mock_vault, state)


class TestVaultFileHandler:
    def test_handle_new_file(self, handler, watch_dir):
        f = watch_dir / "test.py"
        f.write_text("x = 42\n")
        assert handler.handle_file(str(f)) is True

    def test_handle_unchanged_file(self, handler, watch_dir):
        f = watch_dir / "test.py"
        f.write_text("x = 42\n")
        handler.handle_file(str(f))

        # Reset debounce to allow second call
        handler._debounce.clear()

        # Same content -> should not re-ingest
        assert handler.handle_file(str(f)) is False

    def test_handle_modified_file(self, handler, watch_dir):
        f = watch_dir / "test.py"
        f.write_text("x = 42\n")
        handler.handle_file(str(f))

        handler._debounce.clear()

        f.write_text("x = 99\n")
        assert handler.handle_file(str(f)) is True

    def test_skip_hidden_file(self, handler, watch_dir):
        f = watch_dir / ".hidden.py"
        f.write_text("secret = True\n")
        assert handler.handle_file(str(f)) is False

    def test_skip_unsupported_extension(self, handler, watch_dir):
        f = watch_dir / "data.bin"
        f.write_bytes(b"\x00\x01\x02")
        assert handler.handle_file(str(f)) is False

    def test_skip_empty_file(self, handler, watch_dir):
        f = watch_dir / "empty.py"
        f.write_text("")
        assert handler.handle_file(str(f)) is False

    def test_debounce(self, handler, watch_dir):
        f = watch_dir / "test.py"
        f.write_text("x = 42\n")
        assert handler.handle_file(str(f)) is True
        # Immediate second call is debounced
        assert handler.handle_file(str(f)) is False

    def test_updates_file_state(self, handler, state, watch_dir):
        f = watch_dir / "test.py"
        f.write_text("x = 42\n")
        handler.handle_file(str(f))

        file_state = state.get_file_state(str(f.resolve()))
        assert file_state is not None
        assert file_state["content_hash"] is not None


class TestFileWatcher:
    def test_initial_scan(self, mock_vault, state, watch_dir):
        (watch_dir / "a.py").write_text("a = 1\n")
        (watch_dir / "b.py").write_text("b = 2\n")
        (watch_dir / "c.txt").write_text("hello\n")
        (watch_dir / "skip.bin").write_bytes(b"\x00")

        state.add_directory(str(watch_dir))
        watcher = FileWatcher(mock_vault, state)

        count = watcher.initial_scan()
        assert count == 3  # a.py, b.py, c.txt

    def test_initial_scan_no_dirs(self, mock_vault, state):
        watcher = FileWatcher(mock_vault, state)
        assert watcher.initial_scan() == 0

    def test_initial_scan_idempotent(self, mock_vault, state, watch_dir):
        (watch_dir / "a.py").write_text("a = 1\n")
        state.add_directory(str(watch_dir))
        watcher = FileWatcher(mock_vault, state)

        first = watcher.initial_scan()
        # Clear debounce for second scan
        watcher._handler._debounce.clear()
        second = watcher.initial_scan()

        assert first == 1
        assert second == 0  # already ingested, hash matches

    def test_start_stop(self, mock_vault, state, watch_dir):
        state.add_directory(str(watch_dir))
        watcher = FileWatcher(mock_vault, state)
        watcher.start()
        assert watcher._observer.is_alive()
        watcher.stop()
        assert not watcher._observer.is_alive()
