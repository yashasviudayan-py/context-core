import os
import logging
import threading
from pathlib import Path

from context_core.config import VaultConfig, DEFAULT_CONFIG
from context_core.ingest import create_manual_document
from context_core.vault import Vault
from context_core.watcher.state import WatcherState

logger = logging.getLogger(__name__)


class HistoryIngestor:
    """Periodically reads new commands from shell history and ingests them."""

    def __init__(self, vault: Vault, state: WatcherState, config: VaultConfig = DEFAULT_CONFIG):
        self.vault = vault
        self.state = state
        self.config = config
        self.shell_name, self.history_path = self._get_history_path()
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

    def _get_history_path(self) -> tuple[str | None, Path | None]:
        shell = os.environ.get("SHELL", "").split("/")[-1]
        if shell == "zsh":
            return "zsh", Path.home() / ".zsh_history"
        elif shell == "bash":
            return "bash", Path.home() / ".bash_history"
        else:
            logger.warning(f"Unsupported shell for history monitoring: {shell}")
            return None, None

    def start(self) -> None:
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._poll_loop,
            name="history-ingestor",
            daemon=True,
        )
        self._thread.start()
        logger.info("History ingestor started")

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=10.0)
        logger.info("History ingestor stopped")

    def _poll_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                self._ingest_new_commands()
            except Exception:
                logger.exception("Error in history ingest")
            self._stop_event.wait(timeout=self.config.history_poll_interval)

    def parse_history_line(self, line: str) -> str | None:
        """
        Parse a single zsh history line.

        Handles both plain and extended format:
          Plain:    command arg1 arg2
          Extended: : 1234567890:0;command arg1 arg2

        Returns the command string, or None if the line should be skipped.
        """
        line = line.strip()
        if not line:
            return None

        if self.shell_name == "zsh" and line.startswith(": ") and ";" in line:
            _, _, command = line.partition(";")
            line = command.strip()

        if not line or len(line) < self.config.history_min_command_length:
            return None

        base_cmd = line.split()[0].split("/")[-1]
        if base_cmd in self.config.history_skip_commands:
            return None

        return line

    def _ingest_new_commands(self) -> int:
        """Read new lines from history file since last position. Returns count ingested."""
        if self.history_path is None or not self.history_path.exists():
            return 0

        last_line = self.state.get_last_history_line()

        try:
            with open(self.history_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
        except OSError:
            logger.warning(f"Cannot read history file: {self.history_path}")
            return 0

        # File was truncated or rotated
        if last_line > len(lines):
            last_line = 0

        new_lines = lines[last_line:]
        if not new_lines:
            return 0

        batch = []
        ingested = 0

        for line in new_lines:
            command = self.parse_history_line(line)
            if command is None:
                continue

            doc = create_manual_document(
                content=command,
                source_type="terminal",
                tags=["terminal", self.shell_name, "auto-captured"],
            )
            batch.append(doc)

            if len(batch) >= self.config.history_batch_size:
                self.vault.add(batch)
                ingested += len(batch)
                batch = []

        if batch:
            self.vault.add(batch)
            ingested += len(batch)

        self.state.set_last_history_line(len(lines))
        logger.info(f"Ingested {ingested} commands from {self.shell_name} (from line {last_line})")
        return ingested
