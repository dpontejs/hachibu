from tests.test_metas import BASE


def test_put_perfil_grava_metas(make_user):
    c = make_user()
    r = c.put("/api/perfil", json=BASE)
    assert r.status_code == 200
    assert r.json()["metas"]["kcal"] == 2759
    g = c.get("/api/perfil")
    assert g.status_code == 200
    assert g.json()["perfil"]["peso_kg"] == 80
    assert g.json()["metas"]["agua_ml"] == 2800


def test_perfil_sem_opcionais_aceito(make_user):
    r = make_user().put("/api/perfil", json=BASE)
    assert r.json()["perfil"]["percentual_gordura"] is None


def test_perfil_com_opcionais(make_user):
    c = make_user()
    r = c.put(
        "/api/perfil",
        json={
            **BASE,
            "percentual_gordura": 15,
            "cintura_cm": 84,
            "condicoes_saude": "dor no joelho esquerdo",
        },
    )
    assert r.json()["metas"]["kcal"] == 2850
    assert c.get("/api/perfil").json()["perfil"]["condicoes_saude"] == "dor no joelho esquerdo"


def test_put_perfil_atualiza(make_user):
    c = make_user()
    c.put("/api/perfil", json=BASE)
    r = c.put("/api/perfil", json={**BASE, "peso_kg": 90})
    assert r.json()["perfil"]["peso_kg"] == 90


def test_perfil_fora_da_faixa(make_user):
    c = make_user()
    for campo, valor in [
        ("altura_cm", 0),
        ("peso_kg", 500),
        ("idade", 10),
        ("dias_semana", 8),
        ("objetivo", "secar"),
        ("percentual_gordura", 80),
        ("condicoes_saude", "x" * 501),
    ]:
        assert c.put("/api/perfil", json={**BASE, campo: valor}).status_code == 422, campo


def test_get_perfil_inexistente(make_user):
    assert make_user().get("/api/perfil").status_code == 404


def test_me_perfil_completo_vira_true(make_user):
    c = make_user()
    c.put("/api/perfil", json=BASE)
    assert c.get("/api/me").json()["perfil_completo"] is True


def test_perfil_exige_login(client):
    assert client.put("/api/perfil", json=BASE).status_code == 401


def test_perfil_isolado_por_usuario(make_user):
    a, b = make_user("a@x.com"), make_user("b@x.com")
    a.put("/api/perfil", json=BASE)
    assert b.get("/api/perfil").status_code == 404


def test_perfis_em_paralelo_nao_quebram_transacao(make_user):
    from concurrent.futures import ThreadPoolExecutor

    clientes = [make_user(f"u{i}@x.com") for i in range(8)]
    with ThreadPoolExecutor(8) as ex:
        status = list(ex.map(lambda c: c.put("/api/perfil", json=BASE).status_code, clientes * 5))
    assert set(status) == {200}
