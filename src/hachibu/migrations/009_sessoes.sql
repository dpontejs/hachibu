CREATE TABLE sessoes (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    tipo TEXT NOT NULL CHECK (tipo IN ('musculacao', 'corrida', 'cardio')),
    data TEXT NOT NULL,
    nome TEXT NOT NULL,
    plano_id INTEGER REFERENCES planos(id),
    plano_dia INTEGER,
    local TEXT,
    iniciada_em TEXT NOT NULL,
    finalizada_em TEXT
);
CREATE INDEX sessoes_usuario ON sessoes(user_id, data);
CREATE UNIQUE INDEX sessoes_uma_aberta ON sessoes(user_id, tipo) WHERE finalizada_em IS NULL;
CREATE TABLE sessao_exercicios (
    sessao_id INTEGER NOT NULL REFERENCES sessoes(id) ON DELETE CASCADE,
    ordem INTEGER NOT NULL,
    exercicio_id TEXT NOT NULL,
    series_planejadas INTEGER NOT NULL,
    reps_min INTEGER NOT NULL,
    reps_max INTEGER NOT NULL,
    descanso_s INTEGER NOT NULL,
    PRIMARY KEY (sessao_id, ordem)
);
CREATE TABLE series (
    sessao_id INTEGER NOT NULL REFERENCES sessoes(id) ON DELETE CASCADE,
    ordem_exercicio INTEGER NOT NULL,
    ordem INTEGER NOT NULL,
    exercicio_id TEXT NOT NULL,
    carga_kg REAL,
    reps INTEGER NOT NULL,
    feita_em TEXT NOT NULL,
    PRIMARY KEY (sessao_id, ordem_exercicio, ordem)
);
CREATE INDEX series_exercicio ON series(exercicio_id, sessao_id)
