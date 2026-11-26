CREATE TABLE users (
    id INTEGER PRIMARY KEY,
    email TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    criado_em TEXT NOT NULL
);

CREATE TABLE profiles (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    sexo TEXT NOT NULL,
    idade INTEGER NOT NULL,
    altura_cm REAL NOT NULL,
    peso_kg REAL NOT NULL,
    objetivo TEXT NOT NULL,
    nivel TEXT NOT NULL,
    dias_semana INTEGER NOT NULL,
    minutos_sessao INTEGER NOT NULL,
    equipamento TEXT NOT NULL,
    percentual_gordura REAL,
    cintura_cm REAL,
    condicoes_saude TEXT
);

CREATE TABLE goals (
    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    kcal INTEGER NOT NULL,
    proteina_g INTEGER NOT NULL,
    carbo_g INTEGER NOT NULL,
    gordura_g INTEGER NOT NULL,
    agua_ml INTEGER NOT NULL
);

CREATE TABLE meals (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    nome TEXT NOT NULL,
    kcal REAL NOT NULL,
    proteina_g REAL NOT NULL,
    carbo_g REAL NOT NULL,
    gordura_g REAL NOT NULL,
    fonte TEXT NOT NULL
);
CREATE INDEX meals_user_data ON meals(user_id, data);

CREATE TABLE water_logs (
    id INTEGER PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    criado_em TEXT NOT NULL,
    ml INTEGER NOT NULL
);
CREATE INDEX water_user_data ON water_logs(user_id, data)
