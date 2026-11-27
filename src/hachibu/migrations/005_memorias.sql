CREATE TABLE memorias (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('restricao', 'condicao', 'gosto')),
    texto TEXT NOT NULL,
    texto_normalizado TEXT NOT NULL,
    origem TEXT NOT NULL CHECK (origem IN ('coach', 'aluno')),
    criado_em TEXT NOT NULL,
    UNIQUE (user_id, tipo, texto_normalizado)
)
