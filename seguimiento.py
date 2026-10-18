"""Seguimiento automático de guías con 17TRACK (API v2.2). La clave va en la variable TRACK17_KEY (solo en el servidor)."""
from __future__ import annotations

import json, os, urllib.request
from typing import Optional

BASE = "https://api.17track.net/track/v2.2"
# estado de 17TRACK -> estado de la app
MAPA = {
    "InfoReceived": "Enviado", "InTransit": "En tránsito", "AvailableForPickup": "En tránsito",
    "OutForDelivery": "En tránsito", "Delivered": "Entregado",
    "Exception": "Con problema", "DeliveryFailure": "Con problema", "Expired": "Con problema",
}


def mapear_estado(status: Optional[str]) -> Optional[str]:
    return MAPA.get(status or "")


def _post(ruta: str, cuerpo: list, clave: str, timeout: int = 20) -> dict:
    req = urllib.request.Request(
        f"{BASE}/{ruta}", data=json.dumps(cuerpo).encode(), method="POST",
        headers={"17token": clave, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def analizar(respuesta: dict) -> dict:
    """{guia: {estado, evento, fecha_estimada, entregado_en}} a partir de la respuesta de gettrackinfo."""
    out = {}
    for it in (respuesta.get("data") or {}).get("accepted") or []:
        info = it.get("track_info") or {}
        st = (info.get("latest_status") or {}).get("status")
        ev = info.get("latest_event") or {}
        est = (((info.get("time_metrics") or {}).get("estimated_delivery_date")) or {}).get("from")
        nuevo = mapear_estado(st)
        out[it.get("number")] = {
            "estado": nuevo,
            "estado_crudo": st,
            "evento": (ev.get("description") or "")[:300] or None,
            "fecha_estimada": (est or "")[:10] or None,
            "entregado_en": (ev.get("time_iso") or "")[:10] if nuevo == "Entregado" else None,
        }
    return out


def consultar(guias: list[str], clave: Optional[str] = None, enviar=_post) -> dict:
    """Registra (si hace falta) y consulta hasta 40 guías por llamada. Devuelve {guia: datos}."""
    clave = clave or os.environ.get("TRACK17_KEY")
    if not clave:
        raise RuntimeError("Falta TRACK17_KEY")
    resultado = {}
    for i in range(0, len(guias), 40):
        lote = [{"number": g} for g in guias[i:i + 40]]
        enviar("register", lote, clave)  # si ya estaba registrada, 17TRACK la rechaza sin costo; se ignora
        resultado.update(analizar(enviar("gettrackinfo", lote, clave)))
    return resultado
