"""Conexão SQLite e migrações SQL versionadas (mesmo padrão do app today)."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def migrate(conn: sqlite3.Connection) -> list[str]:
    """Aplica as migrações pendentes em ordem, cada uma na sua transação. Devolve os nomes aplicados."""
    conn.execute(
        "CREATE TABLE IF NOT EXISTS schema_version (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
    )
    feitas = {row["name"] for row in conn.execute("SELECT name FROM schema_version")}
    aplicadas = []
    for arquivo in sorted(MIGRATIONS_DIR.glob("*.sql")):
        if arquivo.name in feitas:
            continue
        conn.execute("BEGIN")
        try:
            for comando in arquivo.read_text().split(";"):
                if comando.strip():
                    conn.execute(comando)
            conn.execute(
                "INSERT INTO schema_version (name, applied_at) VALUES (?, ?)",
                (arquivo.name, datetime.now(UTC).isoformat()),
            )
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        aplicadas.append(arquivo.name)
    return aplicadas
