-- Radar de Compras: esquema para Postgres (Neon)
-- Los precios se guardan por ASIN y se comparten entre usuarios: el recolector consulta cada ASIN una sola vez.
-- Todo lo demás pertenece a un usuario (user_id lo entrega el proveedor de inicio de sesión).

CREATE TABLE IF NOT EXISTS ajustes (
  user_id        text PRIMARY KEY,
  impuesto_pct   numeric(5,2) NOT NULL DEFAULT 7,
  empaque        numeric(8,2) NOT NULL DEFAULT 1,
  canal          text         NOT NULL DEFAULT 'ebay',
  comision_pct   numeric(5,2) NOT NULL DEFAULT 13.25,
  cargo_fijo     numeric(8,2) NOT NULL DEFAULT 0.30,
  margen_minimo  numeric(5,2) NOT NULL DEFAULT 20,
  actualizado_en timestamptz  NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS productos (
  id              bigserial PRIMARY KEY,
  user_id         text        NOT NULL,
  asin            text        NOT NULL CHECK (asin ~ '^[A-Z0-9]{10}$'),
  titulo          text,
  categoria       text,
  precio_objetivo numeric(10,2),
  notas           text,
  creado_en       timestamptz NOT NULL DEFAULT now(),
  UNIQUE (user_id, asin)
);
CREATE INDEX IF NOT EXISTS idx_productos_asin ON productos (asin);

CREATE TABLE IF NOT EXISTS precios (
  id              bigserial PRIMARY KEY,
  asin            text        NOT NULL,
  fuente          text        NOT NULL,
  consultado_en   timestamptz NOT NULL,
  observado_en    timestamp,
  amazon_actual   numeric(10,2),
  nuevo_actual    numeric(10,2),
  usado_actual    numeric(10,2),
  amazon_min      numeric(10,2),
  amazon_max      numeric(10,2),
  amazon_prom     numeric(10,2)
);
CREATE INDEX IF NOT EXISTS idx_precios_asin_tiempo ON precios (asin, consultado_en DESC);

CREATE TABLE IF NOT EXISTS compras (
  id               bigserial PRIMARY KEY,
  user_id          text        NOT NULL,
  producto_id      bigint REFERENCES productos(id) ON DELETE SET NULL,
  nombre           text        NOT NULL,
  cantidad         integer     NOT NULL DEFAULT 1 CHECK (cantidad > 0),
  costo_unitario   numeric(10,2) NOT NULL,       -- precio + impuesto + empaque, con los valores del día
  envio_comprador  numeric(10,2) NOT NULL DEFAULT 0,
  fecha            date        NOT NULL DEFAULT current_date,
  estado           text        NOT NULL DEFAULT 'Comprado'
                   CHECK (estado IN ('Comprado','En camino','Recibido','Publicado','Vendido')),
  canal            text,
  precio_venta     numeric(10,2),                -- precio real cuando está vendido
  precio_estimado  numeric(10,2),
  creado_en        timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_compras_user_estado ON compras (user_id, estado);

-- Último precio conocido de cada ASIN
CREATE OR REPLACE VIEW ultimo_precio AS
SELECT DISTINCT ON (asin) *
FROM precios
ORDER BY asin, consultado_en DESC;
