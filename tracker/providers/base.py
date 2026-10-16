"""Contrato común para cualquier fuente de precios (CamelCamelCamel, Keepa, etc.)."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional, Protocol


class ProviderError(Exception):
    """Error genérico de un proveedor de precios."""


class NotFoundError(ProviderError):
    """El producto no existe en la fuente (404)."""


class BlockedError(ProviderError):
    """La fuente rechazó o frenó la consulta (403, 429, 503 o página de verificación).

    Cuando esto pasa se detiene toda la corrida. No se reintenta ni se intenta saltar la protección.
    """


class ParseError(ProviderError):
    """La página cambió de estructura y no se pudieron leer los precios."""


@dataclass
class PriceSnapshot:
    """Foto del precio de un producto en un momento dado."""

    asin: str
    title: Optional[str]
    source: str
    fetched_at: datetime  # cuándo consultamos (UTC)
    observed_at: Optional[datetime] = None  # cuándo la fuente dice haber revisado el precio
    amazon_current: Optional[float] = None
    new_current: Optional[float] = None  # 3rd party nuevo
    used_current: Optional[float] = None  # 3rd party usado
    amazon_lowest: Optional[float] = None
    amazon_highest: Optional[float] = None
    amazon_avg: Optional[float] = None
    amazon_lowest_date: Optional[date] = None
    amazon_highest_date: Optional[date] = None


class PriceProvider(Protocol):
    """Cualquier fuente de precios implementa esto, así se puede cambiar por Keepa sin tocar el resto."""

    name: str

    def fetch(self, asin: str) -> PriceSnapshot: ...
