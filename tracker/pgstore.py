"""Almacenamiento en Postgres (Neon). Misma interfaz que db.py, pero escribe en las tablas del esquema compartido.

La cadena de conexión se toma de la variable de entorno DATABASE_URL. Nunca va en el código ni en el chat.
"""
from __future__ import annotations

from typing import List

from .providers.base import PriceSnapshot


def connect(url: str):
    import psycopg  # se importa aquí para que SQLite funcione sin esta dependencia
    from psycopg.rows import dict_row

    return psycopg.connect(url, row_factory=dict_row, autocommit=True)


def watched_asins(conn) -> List[str]:
    """ASIN distintos que algún usuario vigila. Cada uno se consulta una sola vez."""
    rows = conn.execute("SELECT DISTINCT asin FROM productos ORDER BY asin").fetchall()
    return [r["asin"] for r in rows]


def fetched_within(conn, asin: str, hours: float) -> bool:
    row = conn.execute(
        "SELECT EXISTS (SELECT 1 FROM precios WHERE asin = %s "
        "AND consultado_en >= now() - (%s * interval '1 hour')) AS recent",
        (asin, hours),
    ).fetchone()
    return bool(row["recent"])


def save(conn, s: PriceSnapshot) -> None:
    conn.execute(
        """INSERT INTO precios (asin, fuente, consultado_en, observado_en, amazon_actual, nuevo_actual,
           usado_actual, amazon_min, amazon_max, amazon_prom)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (s.asin, s.source, s.fetched_at, s.observed_at, s.amazon_current, s.new_current, s.used_current,
         s.amazon_lowest, s.amazon_highest, s.amazon_avg),
    )
    if s.title:
        conn.execute("UPDATE productos SET titulo = %s WHERE asin = %s AND titulo IS NULL", (s.title, s.asin))


def latest(conn, asin: str, n: int = 1):
    """Devuelve filas con los mismos nombres de columna que usa db.py (amazon_current, amazon_avg, title)."""
    return conn.execute(
        """SELECT pr.amazon_actual AS amazon_current, pr.amazon_prom AS amazon_avg,
                  pr.consultado_en AS fetched_at,
                  (SELECT p.titulo FROM productos p WHERE p.asin = pr.asin AND p.titulo IS NOT NULL LIMIT 1) AS title
           FROM precios pr WHERE pr.asin = %s ORDER BY pr.consultado_en DESC, pr.id DESC LIMIT %s""",
        (asin, n),
    ).fetchall()
