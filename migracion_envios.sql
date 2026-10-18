-- Módulo de envíos (fase 1): entrantes (Amazon a ti) y salientes (tú al comprador)
CREATE TABLE IF NOT EXISTS envios (
  id            bigserial PRIMARY KEY,
  user_id       text NOT NULL,
  tipo          text NOT NULL CHECK (tipo IN ('entrante','saliente')),
  compra_id     bigint REFERENCES compras(id) ON DELETE SET NULL,
  descripcion   text NOT NULL,
  transportista text,
  guia          text,
  servicio      text,
  estado        text NOT NULL CHECK (estado IN ('Pedido','Por enviar','Enviado','En tránsito','Entregado','Devuelto','Con problema')),
  fecha_limite  date,           -- saliente: último día para despachar
  fecha_estimada date,          -- entrante: llegada estimada
  fecha_envio   date,
  fecha_entrega date,
  peso_oz       numeric(8,2),
  largo_in      numeric(6,2),
  ancho_in      numeric(6,2),
  alto_in       numeric(6,2),
  costo_envio   numeric(10,2),  -- costo real pagado (saliente)
  ubicacion     text,           -- dónde queda el stock (entrante)
  notas         text,
  creado_en     timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_envios_user_tipo_estado ON envios (user_id, tipo, estado);
