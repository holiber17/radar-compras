"""API de Radar de Compras. Variables de entorno: DATABASE_URL, JWT_SECRET, CODIGO_INVITACION, ORIGENES (CORS, separados por coma)."""
from __future__ import annotations

import os, re, uuid
from datetime import date
from typing import Optional

import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from psycopg.rows import dict_row
from pydantic import BaseModel, Field

import seguimiento
from security import crear_token, hash_clave, leer_token, verificar_clave

ESTADOS = ("Comprado", "En camino", "Recibido", "Publicado", "Vendido")
ASIN_RE = re.compile(r"^[A-Z0-9]{10}$")

app = FastAPI(title="Radar de Compras")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o for o in os.environ.get("ORIGENES", "").split(",") if o],
    allow_origin_regex=r"chrome-extension://.*",
    allow_methods=["*"], allow_headers=["*"],
)


def db():
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise HTTPException(500, "Servidor sin base de datos configurada")
    with psycopg.connect(url, row_factory=dict_row, autocommit=True) as conn:
        yield conn


def secreto() -> str:
    s = os.environ.get("JWT_SECRET")
    if not s or len(s) < 32:
        raise HTTPException(500, "Servidor sin JWT_SECRET válido")
    return s


def usuario(authorization: Optional[str] = Header(None)) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(401, "Falta iniciar sesión")
    uid = leer_token(authorization[7:], secreto())
    if not uid:
        raise HTTPException(401, "Sesión inválida o vencida")
    return uid


class Credenciales(BaseModel):
    correo: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    clave: str = Field(min_length=10, max_length=200)


class Registro(Credenciales):
    codigo: str


@app.get("/salud")
def salud():
    return {"ok": True}


@app.post("/registro")
def registro(r: Registro, conn=Depends(db)):
    esperado = os.environ.get("CODIGO_INVITACION")
    if not esperado or r.codigo != esperado:
        raise HTTPException(403, "Código de invitación incorrecto")
    uid = str(uuid.uuid4())
    try:
        conn.execute("INSERT INTO usuarios (id, correo, clave_hash) VALUES (%s,%s,%s)",
                     (uid, r.correo.lower(), hash_clave(r.clave)))
    except psycopg.errors.UniqueViolation:
        raise HTTPException(409, "Ese correo ya está registrado")
    conn.execute("INSERT INTO ajustes (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (uid,))
    return {"token": crear_token(uid, secreto())}


@app.post("/login")
def login(c: Credenciales, conn=Depends(db)):
    fila = conn.execute("SELECT id, clave_hash FROM usuarios WHERE correo=%s", (c.correo.lower(),)).fetchone()
    if not fila or not verificar_clave(c.clave, fila["clave_hash"]):
        raise HTTPException(401, "Correo o contraseña incorrectos")
    return {"token": crear_token(fila["id"], secreto())}


# ---- Ajustes ----
class Ajustes(BaseModel):
    impuesto_pct: float = Field(ge=0, le=30)
    empaque: float = Field(ge=0, le=100)
    canal: str = Field(max_length=40)
    comision_pct: float = Field(ge=0, le=60)
    cargo_fijo: float = Field(ge=0, le=100)
    margen_minimo: float = Field(ge=0, le=90)


@app.get("/ajustes")
def get_ajustes(uid=Depends(usuario), conn=Depends(db)):
    conn.execute("INSERT INTO ajustes (user_id) VALUES (%s) ON CONFLICT DO NOTHING", (uid,))
    return conn.execute("SELECT impuesto_pct, empaque, canal, comision_pct, cargo_fijo, margen_minimo "
                        "FROM ajustes WHERE user_id=%s", (uid,)).fetchone()


@app.put("/ajustes")
def put_ajustes(a: Ajustes, uid=Depends(usuario), conn=Depends(db)):
    conn.execute(
        """INSERT INTO ajustes (user_id, impuesto_pct, empaque, canal, comision_pct, cargo_fijo, margen_minimo)
           VALUES (%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (user_id) DO UPDATE SET impuesto_pct=EXCLUDED.impuesto_pct, empaque=EXCLUDED.empaque,
             canal=EXCLUDED.canal, comision_pct=EXCLUDED.comision_pct, cargo_fijo=EXCLUDED.cargo_fijo,
             margen_minimo=EXCLUDED.margen_minimo, actualizado_en=now()""",
        (uid, a.impuesto_pct, a.empaque, a.canal, a.comision_pct, a.cargo_fijo, a.margen_minimo))
    return a


# ---- Productos vigilados ----
class ProductoIn(BaseModel):
    asin: str
    titulo: Optional[str] = Field(None, max_length=300)
    categoria: Optional[str] = Field(None, max_length=80)
    precio_objetivo: Optional[float] = Field(None, ge=0)
    notas: Optional[str] = Field(None, max_length=1000)
    venta_est: Optional[float] = Field(None, ge=0, le=100000)
    envio_est: Optional[float] = Field(None, ge=0, le=100000)


@app.get("/productos")
def listar_productos(uid=Depends(usuario), conn=Depends(db)):
    return conn.execute(
        """SELECT p.id, p.asin, p.titulo, p.categoria, p.precio_objetivo, p.notas, p.venta_est, p.envio_est,
                  u.amazon_actual, u.amazon_prom, u.amazon_min, u.amazon_max, u.consultado_en
           FROM productos p LEFT JOIN ultimo_precio u ON u.asin = p.asin
           WHERE p.user_id=%s ORDER BY p.creado_en DESC""", (uid,)).fetchall()


@app.post("/productos")
def agregar_producto(p: ProductoIn, uid=Depends(usuario), conn=Depends(db)):
    asin = p.asin.strip().upper()
    if not ASIN_RE.match(asin):
        raise HTTPException(422, "ASIN inválido (10 letras o números)")
    # Tope para no crecer sin control la lista que consulta el recolector
    n = conn.execute("SELECT count(*) AS n FROM productos WHERE user_id=%s", (uid,)).fetchone()["n"]
    if n >= 200:
        raise HTTPException(409, "Límite de 200 productos por usuario")
    return conn.execute(
        """INSERT INTO productos (user_id, asin, titulo, categoria, precio_objetivo, notas, venta_est, envio_est)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
           ON CONFLICT (user_id, asin) DO UPDATE SET titulo=COALESCE(EXCLUDED.titulo, productos.titulo),
             categoria=COALESCE(EXCLUDED.categoria, productos.categoria),
             precio_objetivo=COALESCE(EXCLUDED.precio_objetivo, productos.precio_objetivo),
             notas=COALESCE(EXCLUDED.notas, productos.notas),
             venta_est=COALESCE(EXCLUDED.venta_est, productos.venta_est),
             envio_est=COALESCE(EXCLUDED.envio_est, productos.envio_est)
           RETURNING id, asin, titulo""",
        (uid, asin, p.titulo, p.categoria, p.precio_objetivo, p.notas, p.venta_est, p.envio_est)).fetchone()


@app.delete("/productos/{asin}")
def quitar_producto(asin: str, uid=Depends(usuario), conn=Depends(db)):
    conn.execute("DELETE FROM productos WHERE user_id=%s AND asin=%s", (uid, asin.upper()))
    return {"ok": True}


@app.get("/productos/{asin}/precios")
def historial(asin: str, uid=Depends(usuario), conn=Depends(db)):
    if not conn.execute("SELECT 1 FROM productos WHERE user_id=%s AND asin=%s", (uid, asin.upper())).fetchone():
        raise HTTPException(404, "Producto no vigilado")
    return conn.execute(
        "SELECT consultado_en, amazon_actual, nuevo_actual, usado_actual FROM precios "
        "WHERE asin=%s ORDER BY consultado_en DESC LIMIT 365", (asin.upper(),)).fetchall()


# ---- Compras ----
class CompraIn(BaseModel):
    nombre: str = Field(max_length=300)
    producto_id: Optional[int] = None
    cantidad: int = Field(1, gt=0, le=10000)
    costo_unitario: float = Field(ge=0)
    envio_comprador: float = Field(0, ge=0)
    estado: str = "Comprado"
    canal: Optional[str] = Field(None, max_length=40)
    precio_estimado: Optional[float] = Field(None, ge=0)
    precio_venta: Optional[float] = Field(None, ge=0)


@app.get("/compras")
def listar_compras(uid=Depends(usuario), conn=Depends(db)):
    return conn.execute("SELECT * FROM compras WHERE user_id=%s ORDER BY fecha DESC, id DESC", (uid,)).fetchall()


@app.post("/compras")
def crear_compra(c: CompraIn, uid=Depends(usuario), conn=Depends(db)):
    if c.estado not in ESTADOS:
        raise HTTPException(422, "Estado inválido")
    if c.producto_id and not conn.execute("SELECT 1 FROM productos WHERE id=%s AND user_id=%s", (c.producto_id, uid)).fetchone():
        raise HTTPException(404, "Producto no encontrado")
    return conn.execute(
        """INSERT INTO compras (user_id, producto_id, nombre, cantidad, costo_unitario, envio_comprador, estado,
                                canal, precio_estimado, precio_venta)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING *""",
        (uid, c.producto_id, c.nombre, c.cantidad, c.costo_unitario, c.envio_comprador, c.estado,
         c.canal, c.precio_estimado, c.precio_venta)).fetchone()


class EstadoIn(BaseModel):
    estado: str
    precio_venta: Optional[float] = Field(None, ge=0)


@app.patch("/compras/{cid}")
def cambiar_estado(cid: int, e: EstadoIn, uid=Depends(usuario), conn=Depends(db)):
    if e.estado not in ESTADOS:
        raise HTTPException(422, "Estado inválido")
    fila = conn.execute(
        "UPDATE compras SET estado=%s, precio_venta=COALESCE(%s, precio_venta) WHERE id=%s AND user_id=%s RETURNING *",
        (e.estado, e.precio_venta, cid, uid)).fetchone()
    if not fila:
        raise HTTPException(404, "Compra no encontrada")
    return fila


# ---- Envíos ----
ESTADOS_ENVIO = ("Pedido", "Por enviar", "Enviado", "En tránsito", "Entregado", "Devuelto", "Con problema")
CAMPOS_ENVIO = ("compra_id", "descripcion", "transportista", "guia", "servicio", "estado", "fecha_limite", "fecha_estimada",
                "fecha_envio", "fecha_entrega", "peso_oz", "largo_in", "ancho_in", "alto_in", "costo_envio", "ubicacion", "notas")


class EnvioIn(BaseModel):
    tipo: str
    compra_id: Optional[int] = None
    descripcion: str = Field(max_length=300)
    transportista: Optional[str] = Field(None, max_length=40)
    guia: Optional[str] = Field(None, max_length=60)
    servicio: Optional[str] = Field(None, max_length=60)
    estado: Optional[str] = None
    fecha_limite: Optional[date] = None
    fecha_estimada: Optional[date] = None
    fecha_envio: Optional[date] = None
    fecha_entrega: Optional[date] = None
    peso_oz: Optional[float] = Field(None, ge=0, le=100000)
    largo_in: Optional[float] = Field(None, ge=0, le=1000)
    ancho_in: Optional[float] = Field(None, ge=0, le=1000)
    alto_in: Optional[float] = Field(None, ge=0, le=1000)
    costo_envio: Optional[float] = Field(None, ge=0, le=100000)
    ubicacion: Optional[str] = Field(None, max_length=120)
    notas: Optional[str] = Field(None, max_length=1000)


class EnvioPatch(BaseModel):
    compra_id: Optional[int] = None
    descripcion: Optional[str] = Field(None, max_length=300)
    transportista: Optional[str] = Field(None, max_length=40)
    guia: Optional[str] = Field(None, max_length=60)
    servicio: Optional[str] = Field(None, max_length=60)
    estado: Optional[str] = None
    fecha_limite: Optional[date] = None
    fecha_estimada: Optional[date] = None
    fecha_envio: Optional[date] = None
    fecha_entrega: Optional[date] = None
    peso_oz: Optional[float] = Field(None, ge=0, le=100000)
    largo_in: Optional[float] = Field(None, ge=0, le=1000)
    ancho_in: Optional[float] = Field(None, ge=0, le=1000)
    alto_in: Optional[float] = Field(None, ge=0, le=1000)
    costo_envio: Optional[float] = Field(None, ge=0, le=100000)
    ubicacion: Optional[str] = Field(None, max_length=120)
    notas: Optional[str] = Field(None, max_length=1000)


def build_update(valores: dict, permitidos=CAMPOS_ENVIO):
    """Arma el SET de un UPDATE parcial solo con columnas permitidas (los valores van como parámetros)."""
    cols = [k for k in valores if k in permitidos]
    return ", ".join(f"{c}=%s" for c in cols), [valores[c] for c in cols]


def _revisar_envio(estado, tipo=None):
    if estado is not None and estado not in ESTADOS_ENVIO:
        raise HTTPException(422, "Estado inválido")
    if estado == "Pedido" and tipo == "saliente" or estado == "Por enviar" and tipo == "entrante":
        raise HTTPException(422, "Ese estado no corresponde a este tipo de envío")


@app.get("/envios")
def listar_envios(uid=Depends(usuario), conn=Depends(db)):
    return conn.execute("SELECT * FROM envios WHERE user_id=%s ORDER BY creado_en DESC, id DESC LIMIT 500", (uid,)).fetchall()


@app.post("/envios")
def crear_envio(e: EnvioIn, uid=Depends(usuario), conn=Depends(db)):
    if e.tipo not in ("entrante", "saliente"):
        raise HTTPException(422, "Tipo inválido")
    estado = e.estado or ("Por enviar" if e.tipo == "saliente" else "Pedido")
    _revisar_envio(estado, e.tipo)
    if e.compra_id and not conn.execute("SELECT 1 FROM compras WHERE id=%s AND user_id=%s", (e.compra_id, uid)).fetchone():
        raise HTTPException(404, "Compra no encontrada")
    n = conn.execute("SELECT count(*) AS n FROM envios WHERE user_id=%s", (uid,)).fetchone()["n"]
    if n >= 5000:
        raise HTTPException(409, "Límite de envíos alcanzado")
    datos = e.model_dump()
    datos["estado"] = estado
    cols = ["tipo"] + list(CAMPOS_ENVIO)
    return conn.execute(
        f"INSERT INTO envios (user_id, {', '.join(cols)}) VALUES (%s, {', '.join(['%s'] * len(cols))}) RETURNING *",
        [uid] + [datos[c] for c in cols]).fetchone()


@app.patch("/envios/{eid}")
def actualizar_envio(eid: int, p: EnvioPatch, uid=Depends(usuario), conn=Depends(db)):
    valores = p.model_dump(exclude_unset=True)
    fila = conn.execute("SELECT tipo FROM envios WHERE id=%s AND user_id=%s", (eid, uid)).fetchone()
    if not fila:
        raise HTTPException(404, "Envío no encontrado")
    _revisar_envio(valores.get("estado"), fila["tipo"])
    if valores.get("compra_id") and not conn.execute("SELECT 1 FROM compras WHERE id=%s AND user_id=%s", (valores["compra_id"], uid)).fetchone():
        raise HTTPException(404, "Compra no encontrada")
    if valores.get("descripcion", "x") is None:
        raise HTTPException(422, "La descripción no puede quedar vacía")
    sets, params = build_update(valores)
    if not sets:
        raise HTTPException(422, "Nada que actualizar")
    return conn.execute(f"UPDATE envios SET {sets} WHERE id=%s AND user_id=%s RETURNING *", params + [eid, uid]).fetchone()


@app.post("/envios/seguimiento")
def seguir_envios(uid=Depends(usuario), conn=Depends(db)):
    """Consulta el estado real de las guías de envíos abiertos y actualiza la tabla."""
    if not os.environ.get("TRACK17_KEY"):
        raise HTTPException(503, "Seguimiento automático no configurado (falta TRACK17_KEY en el servidor)")
    filas = conn.execute(
        """SELECT id, tipo, guia, estado FROM envios WHERE user_id=%s AND coalesce(guia,'')<>''
           AND estado IN ('Enviado','En tránsito','Con problema') ORDER BY creado_en DESC LIMIT 80""", (uid,)).fetchall()
    if not filas:
        return {"revisados": 0, "cambios": 0, "envios": []}
    try:
        datos = seguimiento.consultar(sorted({f["guia"].strip() for f in filas}))
    except Exception as ex:
        raise HTTPException(502, f"No se pudo consultar el servicio de seguimiento: {type(ex).__name__}")
    cambios = []
    for f in filas:
        d = datos.get(f["guia"].strip())
        if not d:
            continue
        nuevo = d["estado"] or f["estado"]
        if f["tipo"] == "saliente" and nuevo == "Devuelto":
            nuevo = f["estado"]
        fila = conn.execute(
            """UPDATE envios SET estado=%s, ultimo_evento=coalesce(%s, ultimo_evento), revisado_en=now(),
                 fecha_estimada=coalesce(%s::date, fecha_estimada),
                 fecha_entrega=CASE WHEN %s='Entregado' THEN coalesce(%s::date, fecha_entrega, current_date) ELSE fecha_entrega END
               WHERE id=%s AND user_id=%s RETURNING *""",
            (nuevo, d["evento"], d["fecha_estimada"], nuevo, d["entregado_en"], f["id"], uid)).fetchone()
        if nuevo != f["estado"]:
            cambios.append(fila)
    return {"revisados": len(filas), "cambios": len(cambios), "envios": cambios}


@app.delete("/envios/{eid}")
def borrar_envio(eid: int, uid=Depends(usuario), conn=Depends(db)):
    conn.execute("DELETE FROM envios WHERE id=%s AND user_id=%s", (eid, uid))
    return {"ok": True}
