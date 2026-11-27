from hachibu.db import connect, migrate
from tests.conftest import MIGRACOES

TABELAS = {"users", "profiles", "goals", "meals", "water_logs"}


def tabelas(conn):
    return {r["name"] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}


def test_migrate_cria_tabelas(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    migrate(conn)
    assert tabelas(conn) >= TABELAS


def test_migrate_idempotente(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    assert migrate(conn) == MIGRACOES
    assert migrate(conn) == []
    versoes = [r["name"] for r in conn.execute("SELECT name FROM schema_version")]
    assert versoes == MIGRACOES


def test_foreign_keys_ligadas(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_banco_que_ja_tinha_a_006_antiga_ganha_a_coluna_nova(tmp_path):
    """Produção aplicou a 006 sem minutos_corrida: a 007 acrescenta a coluna sem refazer a 006."""
    conn = connect(str(tmp_path / "t.db"))
    migrate(conn)
    colunas = {r["name"] for r in conn.execute("PRAGMA table_info(profiles)")}
    assert "minutos_corrida" in colunas
