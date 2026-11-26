"""Conexão SQLite e migrações SQL versionadas (mesmo padrão do app today)."""

import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

from fastapi import Depends, Request

MIGRATIONS_DIR = Path(__file__).parent / "migrations"


def connect(path: str) -> sqlite3.Connection:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
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


def get_db(request: Request) -> Iterator[sqlite3.Connection]:
    """Dependência: uma conexão por requisição. Uma conexão compartilhada entre threads mistura transações."""
    conn = connect(request.app.state.settings.db_path)
    try:
        yield conn
    finally:
        conn.close()


Db = Annotated[sqlite3.Connection, Depends(get_db)]
