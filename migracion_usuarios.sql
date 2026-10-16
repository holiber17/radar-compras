-- Usuarios propios de la API (sin proveedor externo de inicio de sesión)
CREATE TABLE IF NOT EXISTS usuarios (
  id          text PRIMARY KEY,                 -- se usa como user_id en el resto de las tablas
  correo      text NOT NULL UNIQUE,
  clave_hash  text NOT NULL,
  creado_en   timestamptz NOT NULL DEFAULT now()
);

-- Precio de venta y envío estimados por producto (para calcular oportunidades)
ALTER TABLE productos ADD COLUMN IF NOT EXISTS venta_est numeric(10,2);
ALTER TABLE productos ADD COLUMN IF NOT EXISTS envio_est numeric(10,2);
