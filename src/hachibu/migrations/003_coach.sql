CREATE TABLE coach_threads (
    thread_id TEXT PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    criado_em TEXT NOT NULL
);
CREATE INDEX coach_threads_user ON coach_threads(user_id);

CREATE TABLE coach_uso (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    data TEXT NOT NULL,
    mensagens INTEGER NOT NULL,
    PRIMARY KEY (user_id, data)
)
