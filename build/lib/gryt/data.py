from __future__ import annotations

import json
import sqlite3
import threading
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class Data(ABC):
    """
    Abstract data store.

    For MVP, we implement an SQLite-backed store with simple helpers
    for creating tables, inserting JSON-friendly data, querying, and updating.
    """

    def __init__(self, db_path: Path | str = Path(".gryt.db"), in_memory: bool = False) -> None:
        self._db_path = ":memory:" if in_memory else str(db_path)
        self._conn: Optional[sqlite3.Connection] = None
        self._lock = threading.RLock()
        self.connect()

    @property
    def conn(self) -> sqlite3.Connection:
        assert self._conn is not None, "Database connection is not initialized"
        return self._conn

    def connect(self) -> None:
        with self._lock:
            self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
        # Initialize predefined tables on first connect
        self._init_tables()

    @abstractmethod
    def create_table(self, table_name: str, schema: Dict[str, str]) -> None:
        """Create a table with a schema mapping column -> SQL type/constraints."""

    @abstractmethod
    def insert(self, table_name: str, data: Dict[str, Any]) -> None:
        """Insert a dict as row; dict/list values are JSON-serialized automatically."""

    @abstractmethod
    def query(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        """Execute a SELECT and return a list of dict rows with JSON automatically parsed."""

    @abstractmethod
    def update(self, table_name: str, data: Dict[str, Any], where: str, params: Tuple[Any, ...]) -> None:
        """Update rows matching the where clause with params."""

    def close(self) -> None:
        with self._lock:
            if self._conn is not None:
                self._conn.close()
                self._conn = None


class SqliteData(Data):
    """SQLite-backed Data implementation.

    Thread-safe via a re-entrant lock around connection operations.
    """

    def _init_tables(self) -> None:
        """Create predefined tables used by gryt primitives.
        - pipelines, runners, steps_output, versions
        """
        with self._lock:
            # Ensure foreign keys are enforced
            self.conn.execute("PRAGMA foreign_keys = ON")
            # pipelines
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS pipelines (
                    pipeline_id TEXT PRIMARY KEY,
                    name TEXT,
                    start_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    end_timestamp DATETIME,
                    status TEXT,
                    config_json TEXT
                )
                """
            )
            # runners
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS runners (
                    runner_id TEXT PRIMARY KEY,
                    pipeline_id TEXT,
                    name TEXT,
                    execution_order INTEGER,
                    status TEXT,
                    FOREIGN KEY (pipeline_id) REFERENCES pipelines(pipeline_id) ON DELETE CASCADE
                )
                """
            )
            # steps_output: ensure schema supports multiple records per step (history)
            # Target schema:
            # output_id INTEGER PRIMARY KEY AUTOINCREMENT,
            # step_id TEXT,
            # runner_id TEXT,
            # name TEXT,
            # output_json TEXT,
            # status TEXT,
            # duration REAL,
            # timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            # FOREIGN KEY (runner_id) REFERENCES runners(runner_id) ON DELETE CASCADE
            # Create if missing, otherwise migrate if old schema found
            cur = self.conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='steps_output'")
            exists = cur.fetchone() is not None
            if not exists:
                self.conn.execute(
                    """
                    CREATE TABLE steps_output (
                        output_id INTEGER PRIMARY KEY AUTOINCREMENT,
                        step_id TEXT,
                        runner_id TEXT,
                        name TEXT,
                        output_json TEXT,
                        stdout TEXT,
                        stderr TEXT,
                        status TEXT,
                        duration REAL,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (runner_id) REFERENCES runners(runner_id) ON DELETE CASCADE
                    )
                    """
                )
            else:
                # Detect old schema lacking output_id or having PRIMARY KEY on step_id
                info = self.conn.execute("PRAGMA table_info(steps_output)").fetchall()
                cols = {row["name"]: row for row in info}
                has_output_id = "output_id" in cols
                # sqlite3.Row does not support .get(); use index access by column name
                step_id_is_pk = bool(cols["step_id"]["pk"]) if "step_id" in cols else False
                if (not has_output_id) or step_id_is_pk:
                    # Perform migration: create new table, copy data, drop old, rename
                    self.conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS steps_output_new (
                            output_id INTEGER PRIMARY KEY AUTOINCREMENT,
                            step_id TEXT,
                            runner_id TEXT,
                            name TEXT,
                            output_json TEXT,
                            stdout TEXT,
                            stderr TEXT,
                            status TEXT,
                            duration REAL,
                            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                            FOREIGN KEY (runner_id) REFERENCES runners(runner_id) ON DELETE CASCADE
                        )
                        """
                    )
                    # Copy data from old table into new table (output_id will autogenerate)
                    self.conn.execute(
                        """
                        INSERT INTO steps_output_new (step_id, runner_id, name, output_json, status, duration, timestamp)
                        SELECT step_id, runner_id, name, output_json, status, duration, timestamp FROM steps_output
                        """
                    )
                    self.conn.execute("DROP TABLE steps_output")
                    self.conn.execute("ALTER TABLE steps_output_new RENAME TO steps_output")
                # Ensure stdout/stderr columns exist on current table
                info2 = self.conn.execute("PRAGMA table_info(steps_output)").fetchall()
                cols2 = {row[1] if isinstance(row, tuple) else row["name"]: row for row in info2}
                if "stdout" not in cols2:
                    self.conn.execute("ALTER TABLE steps_output ADD COLUMN stdout TEXT")
                    try:
                        getattr(self, "_last_migrations_applied", []).append("add steps_output.stdout column")
                    except Exception:
                        pass
                if "stderr" not in cols2:
                    self.conn.execute("ALTER TABLE steps_output ADD COLUMN stderr TEXT")
                    try:
                        getattr(self, "_last_migrations_applied", []).append("add steps_output.stderr column")
                    except Exception:
                        pass
            # versions
            self.conn.execute(
                """
                CREATE TABLE IF NOT EXISTS versions (
                    version_id TEXT PRIMARY KEY,
                    app_name TEXT,
                    version_string TEXT,
                    commit_hash TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            self.conn.commit()

    def _jsonify(self, value: Any) -> Any:
        if isinstance(value, (dict, list)):
            return json.dumps(value, separators=(",", ":"))
        return value

    def _dejsonify(self, value: Any) -> Any:
        if isinstance(value, str) and value[:1] in "[{":
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                return value
        return value

    def create_table(self, table_name: str, schema: Dict[str, str]) -> None:
        columns = ", ".join(f"{k} {v}" for k, v in schema.items())
        with self._lock:
            self.conn.execute(f"CREATE TABLE IF NOT EXISTS {table_name} ({columns})")
            self.conn.commit()

    def insert(self, table_name: str, data: Dict[str, Any]) -> None:
        data2 = {k: self._jsonify(v) for k, v in data.items()}
        placeholders = ", ".join(["?"] * len(data2))
        columns = ", ".join(data2.keys())
        with self._lock:
            self.conn.execute(
                f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})",
                tuple(data2.values()),
            )
            self.conn.commit()

    def query(self, sql: str, params: Tuple[Any, ...] = ()) -> List[Dict[str, Any]]:
        with self._lock:
            cur = self.conn.execute(sql, params)
            rows = cur.fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            d = dict(row)
            results.append({k: self._dejsonify(v) for k, v in d.items()})
        return results

    def update(self, table_name: str, data: Dict[str, Any], where: str, params: Tuple[Any, ...]) -> None:
        data2 = {k: self._jsonify(v) for k, v in data.items()}
        set_clause = ", ".join(f"{k} = ?" for k in data2.keys())
        with self._lock:
            self.conn.execute(
                f"UPDATE {table_name} SET {set_clause} WHERE {where}",
                tuple(data2.values()) + params,
            )
            self.conn.commit()

    def migrate(self) -> Dict[str, Any]:
        """
        Run schema migrations (idempotent). Returns a report of applied migrations.
        """
        # Ensure tracking list exists and is reset
        try:
            self._last_migrations_applied = []
        except Exception:
            self._last_migrations_applied = []
        # Re-run initializer to apply any pending migrations
        self._init_tables()
        # Return a shallow copy so callers can't mutate internal list
        return {"migrations": list(getattr(self, "_last_migrations_applied", []))}
