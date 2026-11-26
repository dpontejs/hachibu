CREATE TABLE foods (
    id INTEGER PRIMARY KEY,
    nome TEXT NOT NULL,
    nome_busca TEXT NOT NULL,
    categoria TEXT NOT NULL,
    kcal REAL NOT NULL,
    proteina_g REAL NOT NULL,
    carbo_g REAL NOT NULL,
    gordura_g REAL NOT NULL,
    fibra_g REAL NOT NULL
);

CREATE TABLE meal_items (
    id INTEGER PRIMARY KEY,
    meal_id INTEGER NOT NULL REFERENCES meals(id) ON DELETE CASCADE,
    food_id INTEGER REFERENCES foods(id),
    nome TEXT NOT NULL,
    gramas REAL NOT NULL,
    kcal REAL NOT NULL,
    proteina_g REAL NOT NULL,
    carbo_g REAL NOT NULL,
    gordura_g REAL NOT NULL
);
CREATE INDEX meal_items_meal ON meal_items(meal_id);

ALTER TABLE goals ADD COLUMN origem TEXT NOT NULL DEFAULT 'formula';
ALTER TABLE goals ADD COLUMN ajustada_em TEXT;

ALTER TABLE profiles ADD COLUMN meta_profissional_kcal INTEGER;
ALTER TABLE profiles ADD COLUMN meta_profissional_proteina_g INTEGER;
ALTER TABLE profiles ADD COLUMN meta_profissional_carbo_g INTEGER;
ALTER TABLE profiles ADD COLUMN meta_profissional_gordura_g INTEGER
