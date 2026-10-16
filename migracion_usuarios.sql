-- Usuarios propios de la API (sin proveedor externo de inicio de sesión)
CREATE TABLE IF NOT EXISTS usuarios (
  id          text PRIMARY KEY,                 -- se usa como user_id en el resto de las tablas
  correo      text NOT NULL UNIQUE,
  clave_hash  text NOT NULL,
  creado_en   timestamptz NOT NULL DEFAULT now()
);
