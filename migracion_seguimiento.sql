ALTER TABLE envios ADD COLUMN IF NOT EXISTS ultimo_evento text;
ALTER TABLE envios ADD COLUMN IF NOT EXISTS revisado_en timestamptz;
