# Radar de Compras

- `main.py`, `security.py`: API (FastAPI) que se publica en Vercel.
- `tracker/`: recolector de precios (CamelCamelCamel); corre en GitHub Actions (`.github/workflows/recolector.yml`).
- `schema.sql`, `migracion_usuarios.sql`: tablas ya creadas en Neon.

## Variables de entorno (Vercel → Settings → Environment Variables)
`DATABASE_URL` (cadena de Neon), `JWT_SECRET` (32+ caracteres al azar), `CODIGO_INVITACION`, `ORIGENES` (dominios web permitidos, separados por coma).

## Recolector (GitHub → Settings → Secrets and variables → Actions)
Secret `DATABASE_URL`; variable `CONTACTO` (tu correo). No activar el horario sin revisar los términos de CamelCamelCamel.

## Pruebas
`python -m unittest discover -s tests` y `python -m unittest discover -s tests_recolector`
