"""Proveedor de CamelCamelCamel (Amazon US).

La página de producto trae una tabla de resumen por tipo de precio (Amazon, 3rd Party New,
3rd Party Used) con mínimo, máximo, actual y promedio. El historial día a día es una imagen,
así que no se puede leer: la curva propia se arma guardando una foto en cada corrida.

Estructura observada el 16-oct-2026 (si cambia, el parser falla en voz alta con ParseError):
  <title>NOMBRE | Amazon price tracker ...</title>
  <span class="pricing-date">As of Oct 11, 2026 01:37 PM</span>
  <table> ... <tr class="pt amazon" data-field="amazon">
      <td>nombre</td><td>mínimo <small>(fecha)</small></td><td>máximo <small>(fecha)</small></td>
      <td>actual <small>(fecha)</small></td><td>promedio</td></tr>
    (también data-field="new" y data-field="used")
"""
from __future__ import annotations

import re
import time
from datetime import date, datetime, timezone
from typing import Optional

import requests
from bs4 import BeautifulSoup

from .base import BlockedError, NotFoundError, ParseError, PriceSnapshot

BASE = "https://camelcamelcamel.com"
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")
MONEY_RE = re.compile(r"\$\s*([\d,]+(?:\.\d{1,2})?)")
BLOCK_MARKERS = ("just a moment", "cf-chl", "attention required", "verify you are human", "captcha")


def _money(cell) -> Optional[float]:
    if cell is None:
        return None
    m = MONEY_RE.search(cell.get_text(" ", strip=True))
    return float(m.group(1).replace(",", "")) if m else None


def _cell_date(cell) -> Optional[date]:
    if cell is None:
        return None
    small = cell.find("small")
    if small is None:
        return None
    text = small.get_text(strip=True).strip("()")
    try:
        return datetime.strptime(text, "%b %d, %Y").date()
    except ValueError:
        return None


def looks_blocked(status: int, body: str) -> bool:
    if status in (403, 429, 503):
        return True
    head = body[:4000].lower()
    return any(marker in head for marker in BLOCK_MARKERS)


def parse_product_html(asin: str, html: str, fetched_at: Optional[datetime] = None) -> PriceSnapshot:
    fetched_at = fetched_at or datetime.now(timezone.utc)
    soup = BeautifulSoup(html, "html.parser")

    table = None
    for t in soup.find_all("table"):
        if t.find("tr", attrs={"data-field": "amazon"}):
            table = t
            break
    if table is None:
        raise ParseError(f"{asin}: no se encontró la tabla de precios; la página pudo cambiar")

    rows = {}
    for tr in table.find_all("tr", attrs={"data-field": True}):
        cells = tr.find_all("td")
        if len(cells) >= 5:  # nombre, mínimo, máximo, actual, promedio
            rows[tr["data-field"]] = cells
    if "amazon" not in rows:
        raise ParseError(f"{asin}: la fila de Amazon no tiene las 5 columnas esperadas")

    def num(kind: str, idx: int) -> Optional[float]:
        cells = rows.get(kind)
        return _money(cells[idx]) if cells else None

    amazon = rows["amazon"]
    snap = PriceSnapshot(
        asin=asin,
        title=None,
        source="camelcamelcamel",
        fetched_at=fetched_at,
        amazon_lowest=_money(amazon[1]),
        amazon_highest=_money(amazon[2]),
        amazon_current=_money(amazon[3]),
        amazon_avg=_money(amazon[4]),
        amazon_lowest_date=_cell_date(amazon[1]),
        amazon_highest_date=_cell_date(amazon[2]),
        new_current=num("new", 3),
        used_current=num("used", 3),
    )

    # Si ninguna cifra se pudo leer, casi seguro cambió el formato: mejor fallar que guardar vacío.
    numbers = [snap.amazon_lowest, snap.amazon_highest, snap.amazon_current, snap.amazon_avg,
               snap.new_current, snap.used_current]
    if all(n is None for n in numbers):
        raise ParseError(f"{asin}: la tabla existe pero no se leyó ningún precio")

    if soup.title and soup.title.string:
        snap.title = soup.title.string.split(" | ")[0].strip() or None

    stamp = soup.find("span", class_="pricing-date")
    if stamp:
        m = re.search(r"As of (.+)", stamp.get_text(" ", strip=True), re.I)
        if m:
            try:
                snap.observed_at = datetime.strptime(m.group(1).strip(), "%b %d, %Y %I:%M %p")
            except ValueError:
                pass
    return snap


class CamelCamelCamelProvider:
    name = "camelcamelcamel"

    def __init__(self, contact: str = "", session: Optional[requests.Session] = None, timeout: int = 20):
        self.timeout = timeout
        self.session = session or requests.Session()
        self.user_agent = f"RadarDeCompras/0.1 (seguimiento personal de precios; {contact or 'sin contacto'})"
        self.session.headers.update({"User-Agent": self.user_agent, "Accept-Language": "en-US,en;q=0.8"})

    def fetch(self, asin: str) -> PriceSnapshot:
        asin = asin.strip().upper()
        if not ASIN_RE.match(asin):
            raise NotFoundError(f"ASIN inválido: {asin!r}")
        url = f"{BASE}/product/{asin}"
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code == 404:
            raise NotFoundError(f"{asin}: no existe en CamelCamelCamel")
        if looks_blocked(resp.status_code, resp.text):
            raise BlockedError(f"{asin}: la fuente frenó la consulta (HTTP {resp.status_code})")
        resp.raise_for_status()
        return parse_product_html(asin, resp.text)
