import logging
import time
from pathlib import Path

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from context_core.config import VaultConfig, DEFAULT_CONFIG
from context_core.ingest import read_file
from context_core.vault import Vault
from context_core.watcher.state import WatcherState

logger = logging.getLogger(__name__)


class VaultFileHandler(FileSystemEventHandler):
    """Handles file create/modify events by ingesting into the vault."""

    def __init__(self, vault: Vault, state: WatcherState, config: VaultConfig = DEFAULT_CONFIG):
        self.vault = vault
        self.state = state
        self.config = config
        self._debounce: dict[str, float] = {}

    def on_created(self, event):
        self._handle_event(event)

    def on_modified(self, event):
        self._handle_event(event)

    def _handle_event(self, event):
        if not event.is_directory:
            self.handle_file(event.src_path)

    def handle_file(self, file_path: str) -> bool:
        """
        Process a single file change. Returns True if ingested.

        1. Debounce (editors fire multiple events per save)
        2. Skip hidden files
        3. Call ingest.read_file()
        4. Compare content hash against file_state table
        5. If changed, vault.add() and update file_state
        """
        path = Path(file_path)

        # Debounce
        now = time.monotonic()
        last = self._debounce.get(file_path, 0.0)
        if now - last < self.config.debounce_seconds:
            return False
        self._debounce[file_path] = now

        # Skip hidden files/dirs
        if any(part.startswith(".") for part in path.parts):
            return False

        doc = read_file(path, self.config)
        if doc is None:
            return False

        # Check if content actually changed
        existing = self.state.get_file_state(str(path.resolve()))
        if existing and existing["content_hash"] == doc.metadata.content_hash:
            return False

        self.vault.add([doc])
        self.state.upsert_file_state(
            file_path=str(path.resolve()),
            content_hash=doc.metadata.content_hash,
            mtime=path.stat().st_mtime,
        )
        logger.info(f"Ingested: {file_path}")
        return True


class FileWatcher:
    """Manages watchdog Observer for all watched directories."""

    def __init__(self, vault: Vault, state: WatcherState, config: VaultConfig = DEFAULT_CONFIG):
        self.vault = vault
        self.state = state
        self.config = config
        self._observer = Observer()
        self._handler = VaultFileHandler(vault, state, config)

    def start(self) -> None:
        """Schedule all watched directories and start the observer thread."""
        directories = self.state.list_directories()
        for d in directories:
            path = Path(d.path)
            if path.is_dir():
                self._observer.schedule(self._handler, str(path), recursive=d.recursive)
                logger.info(f"Watching: {d.path} (recursive={d.recursive})")
            else:
                logger.warning(f"Skipping non-existent directory: {d.path}")
        self._observer.start()

    def stop(self) -> None:
        """Stop the observer and wait for it to finish."""
        self._observer.stop()
        self._observer.join(timeout=5.0)

    def initial_scan(self) -> int:
        """
        Scan all watched directories to catch files changed while daemon was stopped.
        Returns number of files ingested.
        """
        ingested = 0
        for d in self.state.list_directories():
            path = Path(d.path)
            if not path.is_dir():
                continue
            pattern = "**/*" if d.recursive else "*"
            for file_path in path.glob(pattern):
                if file_path.is_file():
                    try:
                        if self._handler.handle_file(str(file_path)):
                            ingested += 1
                    except Exception:
                        logger.exception(f"Error processing file: {file_path}")
        return ingested
