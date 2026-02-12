import logging
import subprocess
import threading
import shutil

from context_core.config import VaultConfig, DEFAULT_CONFIG
from context_core.ingest import create_manual_document
from context_core.vault import Vault
from context_core.utils import content_hash
from context_core.watcher.state import WatcherState

logger = logging.getLogger(__name__)


class ClipboardMonitor:
    """Polls the macOS clipboard and ingests new text content."""

    def __init__(self, vault: Vault, state: WatcherState, config: VaultConfig = DEFAULT_CONFIG):
        self.vault = vault
        self.state = state
        self.config = config
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="clipboard-monitor",
            daemon=True,
        )
        self._thread.start()
        logger.info("Clipboard monitor started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10.0)
        logger.info("Clipboard monitor stopped")

    def _get_clipboard(self) -> str | None:
        """Read current clipboard text via pbpaste."""
        if not shutil.which("pbpaste"):
            logger.warning("`pbpaste` command not found, clipboard monitoring disabled.")
            self._stop_event.set()
            return None
        try:
            result = subprocess.run(
                ["pbpaste"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            if result.returncode == 0:
                return result.stdout
            else:
                raise subprocess.CalledProcessError(result.returncode, result.args)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            pass
        return None

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self.check_and_ingest()
            except Exception:
                logger.exception("Error in clipboard poll")
            self._stop_event.wait(timeout=self.config.clipboard_poll_interval)

    def check_and_ingest(self) -> bool:
        """Check clipboard for new content and ingest if changed. Returns True if ingested."""
        text = self._get_clipboard()
        if not text or len(text.strip()) < self.config.clipboard_min_length:
            return False
        if len(text) > self.config.clipboard_max_length:
            return False

        text = text.strip()
        current_hash = content_hash(text)
        last_hash = self.state.get_last_clipboard_hash()

        if current_hash == last_hash:
            return False

        doc = create_manual_document(
            content=text,
            source_type="clipboard",
            tags=["clipboard", "auto-captured"],
        )
        self.vault.add([doc])
        self.state.set_last_clipboard_hash(current_hash)
        logger.info(f"Ingested clipboard content ({len(text)} chars)")
        return True
