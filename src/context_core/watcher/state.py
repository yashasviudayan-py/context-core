import sqlite3
import threading
from pathlib import Path
from datetime import datetime, timezone
from dataclasses import dataclass

DEFAULT_STATE_DB = Path("./watcher_state.db")


@dataclass
class WatchedDirectory:
    id: int
    path: str
    added_at: str
    recursive: bool


class WatcherState:
    """SQLite-backed state manager for the watcher daemon."""

    def __init__(self, db_path: Path = DEFAULT_STATE_DB):
        self.db_path = db_path
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self) -> None:
        with self._lock:
            self._conn.executescript("""
                CREATE TABLE IF NOT EXISTS watched_directories (
                    id        INTEGER PRIMARY KEY AUTOINCREMENT,
                    path      TEXT NOT NULL UNIQUE,
                    added_at  TEXT NOT NULL,
                    recursive INTEGER NOT NULL DEFAULT 1
                );

                CREATE TABLE IF NOT EXISTS file_state (
                    file_path     TEXT PRIMARY KEY,
                    content_hash  TEXT NOT NULL,
                    mtime         REAL NOT NULL,
                    last_ingested TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS clipboard_state (
                    id            INTEGER PRIMARY KEY CHECK (id = 1),
                    last_hash     TEXT NOT NULL DEFAULT '',
                    last_ingested TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS history_state (
                    id            INTEGER PRIMARY KEY CHECK (id = 1),
                    last_line_num INTEGER NOT NULL DEFAULT 0,
                    last_ingested TEXT NOT NULL DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS daemon_state (
                    id         INTEGER PRIMARY KEY CHECK (id = 1),
                    pid        INTEGER,
                    started_at TEXT,
                    status     TEXT NOT NULL DEFAULT 'stopped'
                );
            """)

    # --- Watched Directories ---

    def add_directory(self, path: str, recursive: bool = True) -> WatchedDirectory:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                "INSERT INTO watched_directories (path, added_at, recursive) VALUES (?, ?, ?)",
                (path, now, int(recursive)),
            )
            self._conn.commit()
            row = self._conn.execute(
                "SELECT * FROM watched_directories WHERE path = ?", (path,)
            ).fetchone()
        return WatchedDirectory(
            id=row["id"],
            path=row["path"],
            added_at=row["added_at"],
            recursive=bool(row["recursive"]),
        )

    def remove_directory(self, path: str) -> bool:
        with self._lock:
            cursor = self._conn.execute("DELETE FROM watched_directories WHERE path = ?", (path,))
            self._conn.commit()
            return cursor.rowcount > 0

    def list_directories(self) -> list[WatchedDirectory]:
        rows = self._conn.execute("SELECT * FROM watched_directories ORDER BY added_at").fetchall()
        return [
            WatchedDirectory(
                id=r["id"],
                path=r["path"],
                added_at=r["added_at"],
                recursive=bool(r["recursive"]),
            )
            for r in rows
        ]

    # --- File State ---

    def get_file_state(self, file_path: str) -> dict | None:
        row = self._conn.execute(
            "SELECT * FROM file_state WHERE file_path = ?", (file_path,)
        ).fetchone()
        return dict(row) if row else None

    def upsert_file_state(self, file_path: str, content_hash: str, mtime: float) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO file_state (file_path, content_hash, mtime, last_ingested)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(file_path) DO UPDATE SET
                       content_hash = excluded.content_hash,
                       mtime = excluded.mtime,
                       last_ingested = excluded.last_ingested""",
                (file_path, content_hash, mtime, now),
            )
            self._conn.commit()

    def remove_file_state(self, file_path: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM file_state WHERE file_path = ?", (file_path,))
            self._conn.commit()

    # --- Clipboard State ---

    def get_last_clipboard_hash(self) -> str:
        row = self._conn.execute("SELECT last_hash FROM clipboard_state WHERE id = 1").fetchone()
        return row["last_hash"] if row else ""

    def set_last_clipboard_hash(self, hash_val: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO clipboard_state (id, last_hash, last_ingested)
                   VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       last_hash = excluded.last_hash,
                       last_ingested = excluded.last_ingested""",
                (hash_val, now),
            )
            self._conn.commit()

    # --- History State ---

    def get_last_history_line(self) -> int:
        row = self._conn.execute("SELECT last_line_num FROM history_state WHERE id = 1").fetchone()
        return row["last_line_num"] if row else 0

    def set_last_history_line(self, line_num: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO history_state (id, last_line_num, last_ingested)
                   VALUES (1, ?, ?)
                   ON CONFLICT(id) DO UPDATE SET
                       last_line_num = excluded.last_line_num,
                       last_ingested = excluded.last_ingested""",
                (line_num, now),
            )
            self._conn.commit()

    # --- Daemon State ---

    def set_daemon_pid(self, pid: int) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            self._conn.execute(
                """INSERT INTO daemon_state (id, pid, started_at, status)
                   VALUES (1, ?, ?, 'running')
                   ON CONFLICT(id) DO UPDATE SET
                       pid = excluded.pid,
                       started_at = excluded.started_at,
                       status = 'running'""",
                (pid, now),
            )
            self._conn.commit()

    def get_daemon_pid(self) -> int | None:
        row = self._conn.execute(
            "SELECT pid FROM daemon_state WHERE id = 1 AND status = 'running'"
        ).fetchone()
        return row["pid"] if row else None

    def clear_daemon_pid(self) -> None:
        with self._lock:
            self._conn.execute(
                "UPDATE daemon_state SET pid = NULL, status = 'stopped' WHERE id = 1"
            )
            self._conn.commit()

    def get_daemon_status(self) -> dict:
        row = self._conn.execute("SELECT * FROM daemon_state WHERE id = 1").fetchone()
        if row:
            return {"pid": row["pid"], "started_at": row["started_at"], "status": row["status"]}
        return {"pid": None, "started_at": None, "status": "stopped"}

    def close(self) -> None:
        self._conn.close()
