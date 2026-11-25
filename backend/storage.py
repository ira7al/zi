"""Durable SQLite store for generation jobs, bot queue items and releases."""
import json
import os
import sqlite3
import threading
import time
from typing import Any

DB_PATH = os.getenv("DB_PATH", os.path.join(os.path.dirname(__file__), "data", "zi.db"))
_lock = threading.Lock()


def _conn() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    return c


def init() -> None:
    with _lock, _conn() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS jobs(
            id TEXT PRIMARY KEY, track_name TEXT, prompt TEXT, duration INTEGER,
            status TEXT, output TEXT, error TEXT, created REAL, updated REAL);
        CREATE TABLE IF NOT EXISTS releases(
            id TEXT PRIMARY KEY, job_id TEXT, status TEXT, metadata TEXT,
            package_path TEXT, routenote_ref TEXT, error TEXT, created REAL, updated REAL);
        CREATE TABLE IF NOT EXISTS queue(
            id TEXT PRIMARY KEY, brief TEXT, status TEXT, job_id TEXT, release_id TEXT,
            error TEXT, created REAL, updated REAL);
        """)
        have = {r["name"] for r in c.execute("PRAGMA table_info(jobs)")}
        for col in ("segments", "audio_path", "preview_path"):
            if col not in have:
                c.execute(f"ALTER TABLE jobs ADD COLUMN {col} TEXT")


def _row(r: sqlite3.Row | None) -> dict[str, Any] | None:
    if r is None:
        return None
    d = dict(r)
    for k in ("output", "metadata", "brief", "segments"):
        if k in d and d[k]:
            try:
                d[k] = json.loads(d[k])
            except ValueError:
                pass
    return d


def put(table: str, row: dict[str, Any]) -> None:
    row = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in row.items()}
    row["updated"] = time.time()
    row.setdefault("created", row["updated"])
    cols = ", ".join(row)
    marks = ", ".join("?" for _ in row)
    upd = ", ".join(f"{k}=excluded.{k}" for k in row if k not in ("id", "created"))
    with _lock, _conn() as c:
        c.execute(f"INSERT INTO {table}({cols}) VALUES({marks}) "
                  f"ON CONFLICT(id) DO UPDATE SET {upd}", list(row.values()))


def get(table: str, id_: str) -> dict[str, Any] | None:
    with _lock, _conn() as c:
        return _row(c.execute(f"SELECT * FROM {table} WHERE id=?", (id_,)).fetchone())


def list_(table: str, where: str = "", args: tuple = (), limit: int = 100) -> list[dict[str, Any]]:
    with _lock, _conn() as c:
        q = f"SELECT * FROM {table} {where} ORDER BY created DESC LIMIT ?"
        return [_row(r) for r in c.execute(q, (*args, limit)).fetchall()]
