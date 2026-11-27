ALTER TABLE coach_threads ADD COLUMN titulo TEXT NOT NULL DEFAULT '';
ALTER TABLE coach_threads ADD COLUMN atualizado_em TEXT;
UPDATE coach_threads SET atualizado_em = criado_em;
CREATE INDEX coach_threads_recentes ON coach_threads(user_id, atualizado_em)
