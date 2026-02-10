import logging
import threading
from pathlib import Path

from context_core.ingest import create_manual_document
from context_core.vault import Vault
from context_core.watcher.state import WatcherState

logger = logging.getLogger(__name__)

DEFAULT_HISTORY_PATH = Path.home() / ".zsh_history"


class HistoryIngestor:
    """Periodically reads new commands from zsh_history and ingests them."""

    POLL_INTERVAL = 30.0
    BATCH_SIZE = 20
    MIN_COMMAND_LENGTH = 5

    SKIP_COMMANDS = frozenset({
        "ls", "cd", "pwd", "clear", "exit", "which", "echo",
        "cat", "less", "more", "head", "tail", "man",
    })

    def __init__(
        self,
        vault: Vault,
        state: WatcherState,
        history_path: Path = DEFAULT_HISTORY_PATH,
    ):
        self.vault = vault
        self.state = state
        self.history_path = history_path
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None

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
            self._stop_event.wait(timeout=self.POLL_INTERVAL)

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

        # Extended history format: ": timestamp:0;command"
        if line.startswith(": ") and ";" in line:
            _, _, command = line.partition(";")
            line = command.strip()

        if not line or len(line) < self.MIN_COMMAND_LENGTH:
            return None

        base_cmd = line.split()[0].split("/")[-1]
        if base_cmd in self.SKIP_COMMANDS:
            return None

        return line

    def _ingest_new_commands(self) -> int:
        """Read new lines from history file since last position. Returns count ingested."""
        if not self.history_path.exists():
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
                tags=["terminal", "zsh", "auto-captured"],
            )
            batch.append(doc)

            if len(batch) >= self.BATCH_SIZE:
                self.vault.add(batch)
                ingested += len(batch)
                batch = []

        if batch:
            self.vault.add(batch)
            ingested += len(batch)

        self.state.set_last_history_line(len(lines))
        logger.info(f"Ingested {ingested} commands (from line {last_line})")
        return ingested
