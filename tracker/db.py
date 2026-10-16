"""Almacenamiento en SQLite. Cada corrida agrega una foto por producto; con el tiempo forman la curva propia."""
from __future__ import annotations

import sqlite3
from datetime import datetime, timedelta, timezone
from typing import Optional

from .providers.base import PriceSnapshot

SCHEMA = """
CREATE TABLE IF NOT EXISTS snapshots (
  id INTEGER PRIMARY KEY,
  asin TEXT NOT NULL,
  title TEXT,
  source TEXT NOT NULL,
  fetched_at TEXT NOT NULL,
  observed_at TEXT,
  amazon_current REAL,
  new_current REAL,
  used_current REAL,
  amazon_lowest REAL,
  amazon_highest REAL,
  amazon_avg REAL
);
CREATE INDEX IF NOT EXISTS idx_snapshots_asin_time ON snapshots (asin, fetched_at);
"""


def connect(path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.executescript(SCHEMA)
    return conn


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat(timespec="seconds") if dt else None


def save(conn: sqlite3.Connection, s: PriceSnapshot) -> None:
    conn.execute(
        """INSERT INTO snapshots (asin,title,source,fetched_at,observed_at,amazon_current,new_current,
           used_current,amazon_lowest,amazon_highest,amazon_avg) VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
        (s.asin, s.title, s.source, _iso(s.fetched_at), _iso(s.observed_at), s.amazon_current,
         s.new_current, s.used_current, s.amazon_lowest, s.amazon_highest, s.amazon_avg),
    )
    conn.commit()


def latest(conn: sqlite3.Connection, asin: str, n: int = 1):
    return conn.execute(
        "SELECT * FROM snapshots WHERE asin=? ORDER BY fetched_at DESC, id DESC LIMIT ?", (asin, n)
    ).fetchall()


def fetched_within(conn: sqlite3.Connection, asin: str, hours: float) -> bool:
    rows = latest(conn, asin, 1)
    if not rows:
        return False
    last = datetime.fromisoformat(rows[0]["fetched_at"])
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    return last >= datetime.now(timezone.utc) - timedelta(hours=hours)
