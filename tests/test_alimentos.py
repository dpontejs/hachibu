import sqlite3

from hachibu.alimentos import carregar_taco, normalizar
from hachibu.db import connect, migrate


def test_normalizar():
    assert normalizar("  Pão, FRANCÊS!  ") == "pao frances"


def test_taco_tem_alimentos_com_kcal(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    migrate(conn)
    # 597 da TACO menos 4 sem dado de energia na fonte ("*"): iogurte de abacaxi, leite integral, leite UHT
    # desnatado e coco verde; o sal ("NA", não analisado) entra com 0.
    assert carregar_taco(conn) == 593
    assert conn.execute("SELECT COUNT(*) FROM foods WHERE kcal IS NULL").fetchone()[0] == 0


def test_arroz_integral_cozido_bate_com_a_tabela(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    migrate(conn)
    carregar_taco(conn)
    r = conn.execute("SELECT * FROM foods WHERE id = 1").fetchone()
    assert r["nome"] == "Arroz, integral, cozido"
    assert (r["kcal"], r["proteina_g"], r["carbo_g"], r["gordura_g"]) == (123.5, 2.6, 25.8, 1.0)
    assert r["nome_busca"] == "arroz integral cozido"


def test_carregar_taco_idempotente(tmp_path):
    conn = connect(str(tmp_path / "t.db"))
    migrate(conn)
    carregar_taco(conn)
    assert carregar_taco(conn) == 0
    assert conn.execute("SELECT COUNT(*) FROM foods").fetchone()[0] == 593


def test_migracao_002_preserva_dados(tmp_path):
    from hachibu.db import MIGRATIONS_DIR

    caminho = str(tmp_path / "t.db")
    conn = sqlite3.connect(caminho, isolation_level=None)
    conn.execute("CREATE TABLE schema_version (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)")
    conn.executescript((MIGRATIONS_DIR / "001_inicial.sql").read_text())
    conn.execute("INSERT INTO schema_version VALUES ('001_inicial.sql', 'x')")
    conn.execute("INSERT INTO users (id, email, senha_hash, criado_em) VALUES (1, 'a@x.com', 'h', 'x')")
    conn.execute("INSERT INTO goals VALUES (1, 2759, 144, 402, 64, 2800)")
    conn.close()
    conn = connect(caminho)
    assert migrate(conn) == ["002_alimentos.sql"]
    g = conn.execute("SELECT kcal, origem, ajustada_em FROM goals WHERE user_id = 1").fetchone()
    assert (g["kcal"], g["origem"], g["ajustada_em"]) == (2759, "formula", None)


def test_busca_arroz_integral_cozido_primeiro(make_user):
    r = make_user().get("/api/alimentos", params={"q": "arroz integral cozido"})
    assert r.status_code == 200
    assert r.json()[0]["id"] == 1
    assert set(r.json()[0]) == {"id", "nome", "categoria", "kcal", "proteina_g", "carbo_g", "gordura_g"}


def test_busca_ignora_acento_e_ordem(make_user):
    c = make_user()
    ids = [c.get("/api/alimentos", params={"q": q}).json()[0]["id"] for q in ("Pão Francês", "frances pao")]
    assert ids[0] == ids[1]


def test_busca_curta_422(make_user):
    assert make_user().get("/api/alimentos", params={"q": "a"}).status_code == 422


def test_busca_exige_login(client):
    assert client.get("/api/alimentos", params={"q": "arroz"}).status_code == 401


def test_busca_sem_resultado_lista_vazia(make_user):
    assert make_user().get("/api/alimentos", params={"q": "xyzqwerty"}).json() == []


def test_busca_limita_resultados(make_user):
    assert len(make_user().get("/api/alimentos", params={"q": "carne"}).json()) <= 20
