ALTER TABLE profiles ADD COLUMN nivel_corrida TEXT;
ALTER TABLE profiles ADD COLUMN corrida_quando TEXT;
ALTER TABLE profiles ADD COLUMN corridas_semana INTEGER;
CREATE TABLE planos (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    versao INTEGER NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('base', 'coach')),
    dados TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    ativo INTEGER NOT NULL DEFAULT 1,
    UNIQUE (user_id, versao)
);
CREATE INDEX planos_ativo ON planos(user_id, ativo);
CREATE TABLE progressao_corrida (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    semana INTEGER NOT NULL DEFAULT 1,
    sessoes_desde INTEGER NOT NULL DEFAULT 0
)
