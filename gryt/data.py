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

    For MVP we implement a SQLite-backed store with simple helpers
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
