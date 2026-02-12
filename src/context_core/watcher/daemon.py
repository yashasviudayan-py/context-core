import logging
import os
import signal
import sys
import time
from pathlib import Path

from context_core.vault import Vault
from context_core.watcher.state import WatcherState
from context_core.watcher.file_watcher import FileWatcher
from context_core.watcher.clipboard_monitor import ClipboardMonitor
from context_core.watcher.history_ingestor import HistoryIngestor

import tempfile

logger = logging.getLogger(__name__)

DEFAULT_LOG_PATH = Path(tempfile.gettempdir()) / "context_core_watcher.log"


class WatcherDaemon:
    """Orchestrates all watcher components."""

    def __init__(self, state: WatcherState, vault: Vault | None = None):
        self.state = state
        self._vault = vault
        self._file_watcher: FileWatcher | None = None
        self._clipboard_monitor: ClipboardMonitor | None = None
        self._history_ingestor: HistoryIngestor | None = None
        self._running = False

    @property
    def vault(self) -> Vault:
        if self._vault is None:
            self._vault = Vault()
        return self._vault

    def run(self, write_pipe: int | None = None) -> None:
        """Main entry point. Sets up signal handlers and starts all monitors."""
        self._running = True
        self.state.set_daemon_pid(os.getpid())

        signal.signal(signal.SIGTERM, self._signal_handler)
        signal.signal(signal.SIGINT, self._signal_handler)

        logging.basicConfig(
            filename=str(DEFAULT_LOG_PATH),
            level=logging.INFO,
            format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
        )

        logger.info(f"Watcher daemon starting (PID={os.getpid()})")

        try:
            self._start_monitors()
            if write_pipe:
                os.write(write_pipe, b"1")
                os.close(write_pipe)

            while self._running:
                time.sleep(1.0)
        except Exception:
            if write_pipe:
                os.close(write_pipe)
            logger.exception("Fatal error in watcher daemon")
        finally:
            self._stop_monitors()
            self.state.clear_daemon_pid()
            logger.info("Watcher daemon stopped")

    def _start_monitors(self) -> None:
        self._file_watcher = FileWatcher(self.vault, self.state)
        initial_count = self._file_watcher.initial_scan()
        logger.info(f"Initial scan: {initial_count} files ingested")
        self._file_watcher.start()

        self._clipboard_monitor = ClipboardMonitor(self.vault, self.state)
        self._clipboard_monitor.start()

        self._history_ingestor = HistoryIngestor(self.vault, self.state)
        self._history_ingestor.start()

    def _stop_monitors(self) -> None:
        if self._file_watcher:
            self._file_watcher.stop()
        if self._clipboard_monitor:
            self._clipboard_monitor.stop()
        if self._history_ingestor:
            self._history_ingestor.stop()

    def _signal_handler(self, signum, frame) -> None:
        logger.info(f"Received signal {signum}, shutting down...")
        self._running = False


def _is_process_running(pid: int) -> bool:
    """Check if a process with the given PID is running."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def start_daemon(foreground: bool = False) -> int:
    """
    Start the watcher daemon.
    If foreground=True, runs in the current process.
    Otherwise, spawns a background process.
    Returns the daemon PID.
    """
    # TODO: Implement a file-based lock to prevent race conditions
    # where multiple processes try to start the daemon at the same time.
    # The current check is a good-enough mitigation for now.
    state = WatcherState()
    existing_pid = state.get_daemon_pid()
    if existing_pid and _is_process_running(existing_pid):
        return existing_pid

    if foreground:
        daemon = WatcherDaemon(state)
        daemon.run()
        return os.getpid()
    else:
        read_pipe, write_pipe = os.pipe()
        proc = subprocess.Popen(
            [sys.executable, "-m", "context_core.watcher.daemon", str(write_pipe)],
            pass_fds=[write_pipe],
            start_new_session=True,
        )
        os.close(write_pipe)

        # Wait for daemon to be ready
        os.read(read_pipe, 1)
        os.close(read_pipe)

        time.sleep(0.1)  # Give it a moment to stabilize
        if proc.poll() is not None:
            raise RuntimeError("Daemon failed to start")

        state.set_daemon_pid(proc.pid)
        return proc.pid


def stop_daemon(timeout: int = 10) -> bool:
    """
    Stop the running watcher daemon. Returns True if successfully stopped.
    Args:
        timeout: Time in seconds to wait for graceful shutdown before sending SIGKILL.
    """
    state = WatcherState()
    pid = state.get_daemon_pid()
    if pid is None:
        return False

    if not _is_process_running(pid):
        state.clear_daemon_pid()
        return False

    os.kill(pid, signal.SIGTERM)

    for _ in range(timeout * 2):
        if not _is_process_running(pid):
            state.clear_daemon_pid()
            return True
        time.sleep(0.5)

    os.kill(pid, signal.SIGKILL)
    state.clear_daemon_pid()
    return True


def daemon_status() -> dict:
    """Get the current daemon status."""
    state = WatcherState()
    info = state.get_daemon_status()
    pid = info.get("pid")

    if pid and not _is_process_running(pid):
        state.clear_daemon_pid()
        info["status"] = "stopped"
        info["pid"] = None
        info["note"] = "Daemon was not running (stale PID cleared)"

    info["watched_directories"] = len(state.list_directories())
    return info


if __name__ == "__main__":
    write_pipe_fd = int(sys.argv[1]) if len(sys.argv) > 1 else None
    state = WatcherState()
    daemon = WatcherDaemon(state)
    daemon.run(write_pipe=write_pipe_fd)
