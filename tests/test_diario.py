from datetime import UTC, datetime

from hachibu.diario import hoje
from tests.test_metas import BASE

ALMOCO = {"nome": "Almoço", "kcal": 700, "proteina_g": 45, "carbo_g": 80, "gordura_g": 20}
LANCHE = {"nome": "Iogurte", "kcal": 150.5, "proteina_g": 10, "carbo_g": 15, "gordura_g": 4}


def com_perfil(make_user, email="a@x.com"):
    c = make_user(email)
    c.put("/api/perfil", json=BASE)
    return c


def test_hoje_funcao_usa_fuso():
    # 02:30 UTC do dia 27 ainda é dia 26 em Brasília (UTC-3).
    assert hoje("America/Sao_Paulo", datetime(2026, 11, 27, 2, 30, tzinfo=UTC)).isoformat() == "2026-11-26"
    assert hoje("America/Sao_Paulo", datetime(2026, 11, 27, 3, 30, tzinfo=UTC)).isoformat() == "2026-11-27"


def test_saldo_do_dia(make_user):
    c = com_perfil(make_user)
    assert c.post("/api/refeicoes", json=ALMOCO).status_code == 201
    assert c.post("/api/refeicoes", json=LANCHE).status_code == 201
    assert c.post("/api/agua", json={"ml": 500}).status_code == 201
    assert c.post("/api/agua", json={"ml": 250}).status_code == 201
    h = c.get("/api/hoje").json()
    assert h["metas"]["kcal"] == 2759
    assert h["consumido"] == {"kcal": 850.5, "proteina_g": 55, "carbo_g": 95, "gordura_g": 24}
    assert h["agua_ml"] == 750
    assert [r["nome"] for r in h["refeicoes"]] == ["Almoço", "Iogurte"]


def test_hoje_vazio(make_user):
    h = com_perfil(make_user).get("/api/hoje").json()
    assert h["consumido"] == {"kcal": 0, "proteina_g": 0, "carbo_g": 0, "gordura_g": 0}
    assert h["agua_ml"] == 0 and h["refeicoes"] == []


def test_hoje_usa_fuso_de_sao_paulo(app, make_user):
    c = com_perfil(make_user)
    app.state.agora = lambda: datetime(2026, 11, 27, 2, 50, tzinfo=UTC)  # 23:50 do dia 26 em Brasília
    c.post("/api/refeicoes", json=ALMOCO)
    app.state.agora = lambda: datetime(2026, 11, 27, 3, 10, tzinfo=UTC)  # 00:10 do dia 27
    c.post("/api/refeicoes", json=LANCHE)
    h = c.get("/api/hoje").json()
    assert h["data"] == "2026-11-27"
    assert [r["nome"] for r in h["refeicoes"]] == ["Iogurte"]


def test_hoje_sem_perfil(make_user):
    r = make_user().get("/api/hoje")
    assert r.status_code == 409
    assert r.json() == {"detail": "perfil_incompleto"}


def test_usuario_nao_ve_diario_de_outro(make_user):
    a = com_perfil(make_user, "a@x.com")
    b = com_perfil(make_user, "b@x.com")
    b.post("/api/refeicoes", json=ALMOCO)
    b.post("/api/agua", json={"ml": 500})
    h = a.get("/api/hoje").json()
    assert h["refeicoes"] == [] and h["agua_ml"] == 0 and h["consumido"]["kcal"] == 0


def test_valores_invalidos(make_user):
    c = com_perfil(make_user)
    assert c.post("/api/agua", json={"ml": 0}).status_code == 422
    assert c.post("/api/agua", json={"ml": 2001}).status_code == 422
    assert c.post("/api/refeicoes", json={**ALMOCO, "kcal": 5001}).status_code == 422
    assert c.post("/api/refeicoes", json={**ALMOCO, "proteina_g": -1}).status_code == 422
    assert c.post("/api/refeicoes", json={**ALMOCO, "nome": ""}).status_code == 422


def test_user_id_no_corpo_e_ignorado(make_user):
    a = com_perfil(make_user, "a@x.com")
    b = com_perfil(make_user, "b@x.com")
    a.post("/api/refeicoes", json={**ALMOCO, "user_id": 2})
    assert b.get("/api/hoje").json()["refeicoes"] == []


def test_rotas_exigem_login(client):
    for metodo, rota in [
        ("get", "/api/me"),
        ("get", "/api/perfil"),
        ("put", "/api/perfil"),
        ("get", "/api/hoje"),
        ("post", "/api/refeicoes"),
        ("post", "/api/agua"),
    ]:
        assert client.request(metodo.upper(), rota, json={}).status_code == 401, rota
