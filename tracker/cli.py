"""Línea de comandos: `python -m tracker run` consulta los productos; `python -m tracker report` los resume."""
from __future__ import annotations

import argparse
import os
import random
import sys
import time
from urllib.robotparser import RobotFileParser

from . import db
from .providers.base import BlockedError, NotFoundError, ParseError
from .providers.camelcamelcamel import BASE, CamelCamelCamelProvider


def read_asins(path: str) -> list[str]:
    out, seen = [], set()
    with open(path, encoding="utf-8") as f:
        for line in f:
            asin = line.split("#")[0].strip().upper()
            if asin and asin not in seen:
                seen.add(asin)
                out.append(asin)
    return out


def robots_allows(provider: CamelCamelCamelProvider, asin: str) -> bool:
    """Lee robots.txt del sitio y respeta lo que diga. Si no se puede leer, no se consulta nada."""
    resp = provider.session.get(f"{BASE}/robots.txt", timeout=15)
    if resp.status_code in (403, 429) or resp.status_code >= 500:
        raise BlockedError(f"robots.txt no disponible (HTTP {resp.status_code})")
    rp = RobotFileParser()
    if resp.status_code == 200:
        rp.parse(resp.text.splitlines())
    else:  # 404 u otro 4xx: no hay reglas publicadas
        rp.parse([])
    return rp.can_fetch(provider.user_agent, f"{BASE}/product/{asin}")


def open_store(args):
    """Postgres (Neon) si hay DATABASE_URL; si no, SQLite local. Devuelve (módulo, conexión, lista de ASIN)."""
    if args.database_url:
        from . import pgstore

        conn = pgstore.connect(args.database_url)
        return pgstore, conn, pgstore.watched_asins(conn)
    return db, db.connect(args.db), read_asins(args.asins)


def cmd_run(args) -> int:
    store, conn, asins = open_store(args)
    asins = asins[: args.max]
    if not asins:
        print("No hay productos para consultar.")
        return 1
    provider = CamelCamelCamelProvider(contact=args.contact)

    try:
        if not robots_allows(provider, asins[0]):
            print("robots.txt no permite consultar las páginas de producto. Se cancela la corrida.")
            return 2
    except BlockedError as e:
        print("Se cancela la corrida:", e)
        return 2

    ok = skipped = 0
    failures: list[str] = []
    first = True
    for asin in asins:
        if store.fetched_within(conn, asin, args.min_hours):
            skipped += 1
            continue
        if not first:
            time.sleep(random.uniform(args.min_delay, args.max_delay))
        first = False
        try:
            snap = provider.fetch(asin)
        except BlockedError as e:
            print("PARADA: la fuente frenó las consultas.", e)
            print("No se reintenta. Espera varias horas o cambia a una API (por ejemplo Keepa).")
            return 2
        except NotFoundError as e:
            failures.append(f"{asin}: no encontrado")
            print("AVISO", e)
            continue
        except ParseError as e:
            failures.append(f"{asin}: formato cambiado")
            print("ERROR", e)
            continue
        except Exception as e:  # red, timeout, etc.
            failures.append(f"{asin}: {type(e).__name__}")
            print("ERROR", asin, e)
            continue
        store.save(conn, snap)
        ok += 1
        print(f"OK {asin} actual={snap.amazon_current} promedio={snap.amazon_avg} {snap.title or ''}")

    print(f"\nListo: {ok} guardados, {skipped} omitidos (consultados hace menos de {args.min_hours} h), {len(failures)} con problemas.")
    if failures:
        print("Problemas:", "; ".join(failures))
        if sum("formato" in f for f in failures) >= max(2, len(asins) // 2):
            print("Muchos productos fallaron por formato: la página probablemente cambió. Hay que actualizar el parser.")
        return 1
    return 0


def cmd_report(args) -> int:
    store, conn, asins = open_store(args)
    rows = []
    for asin in asins:
        snaps = store.latest(conn, asin, 2)
        if not snaps:
            continue
        cur, prev = snaps[0], (snaps[1] if len(snaps) > 1 else None)
        price, avg = cur["amazon_current"], cur["amazon_avg"]
        vs_avg = (1 - price / avg) * 100 if price and avg else None
        vs_prev = (1 - price / prev["amazon_current"]) * 100 if price and prev and prev["amazon_current"] else None
        rows.append((vs_avg if vs_avg is not None else -999, asin, cur["title"], price, avg, vs_avg, vs_prev))
    rows.sort(reverse=True)
    for _, asin, title, price, avg, vs_avg, vs_prev in rows:
        flag = "OFERTA " if vs_avg is not None and vs_avg >= args.threshold else "       "
        avg_txt = f"-{vs_avg:.0f}% vs promedio" if vs_avg is not None else "sin promedio"
        prev_txt = f", {vs_prev:+.0f}% vs consulta anterior" if vs_prev is not None else ""
        price_txt = f"${price:.2f}" if price else "sin precio de Amazon"
        print(f"{flag}{asin}  {price_txt}  {avg_txt}{prev_txt}  {(title or '')[:60]}")
    if not rows:
        print("Todavía no hay datos. Corre primero: python -m tracker run")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="tracker", description="Seguimiento de precios de Amazon US vía CamelCamelCamel")
    p.add_argument("--db", default="prices.db", help="archivo SQLite (solo si no hay DATABASE_URL)")
    p.add_argument("--database-url", default=os.environ.get("DATABASE_URL"),
                   help="Postgres de Neon; por defecto se lee de la variable de entorno DATABASE_URL")
    p.add_argument("--asins", default="asins.txt")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="consultar los productos de la lista")
    r.add_argument("--contact", default="", help="correo o sitio para identificarte en el User-Agent")
    r.add_argument("--max", type=int, default=100, help="máximo de productos por corrida")
    r.add_argument("--min-hours", type=float, default=12, help="no repetir un producto consultado hace menos de N horas")
    r.add_argument("--min-delay", type=float, default=8, help="pausa mínima entre consultas (segundos)")
    r.add_argument("--max-delay", type=float, default=15, help="pausa máxima entre consultas (segundos)")
    r.set_defaults(func=cmd_run)

    s = sub.add_parser("report", help="resumen de lo guardado")
    s.add_argument("--threshold", type=float, default=25, help="% bajo el promedio para marcar oferta")
    s.set_defaults(func=cmd_report)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
