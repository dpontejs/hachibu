"""Memórias do aluno: o que o coach sabe dele entre conversas (restrições, condições físicas e gostos)."""

from tests.test_metas import BASE


def memorias(c) -> list[dict]:
    r = c.get("/api/memorias")
    assert r.status_code == 200, r.text
    return r.json()["memorias"]


def test_crud_de_memorias(aluno):
    r = aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "Não gosta de azeitona"})
    assert r.status_code == 201
    criada = r.json()
    assert criada["origem"] == "aluno" and criada["tipo"] == "gosto"

    r = aluno.patch(f"/api/memorias/{criada['id']}", json={"texto": "Detesta azeitona preta"})
    assert r.status_code == 200 and r.json()["texto"] == "Detesta azeitona preta"
    assert [m["texto"] for m in memorias(aluno)] == ["Detesta azeitona preta"]

    assert aluno.delete(f"/api/memorias/{criada['id']}").status_code == 204
    assert memorias(aluno) == []


def test_restricoes_vem_antes_de_condicoes_e_gostos(aluno):
    for tipo, texto in [("gosto", "ama café"), ("condicao", "dor no joelho"), ("restricao", "celíaco")]:
        aluno.post("/api/memorias", json={"tipo": tipo, "texto": texto})
    assert [m["tipo"] for m in memorias(aluno)] == ["restricao", "condicao", "gosto"]


def test_memoria_de_outro_usuario_404(aluno, make_user):
    id_ = aluno.post("/api/memorias", json={"tipo": "restricao", "texto": "alergia a amendoim"}).json()["id"]
    intruso = make_user("b@x.com")
    intruso.put("/api/perfil", json=BASE)
    assert intruso.patch(f"/api/memorias/{id_}", json={"texto": "nada"}).status_code == 404
    assert intruso.delete(f"/api/memorias/{id_}").status_code == 404
    assert memorias(intruso) == []
    assert [m["texto"] for m in memorias(aluno)] == ["alergia a amendoim"]


def test_memoria_repetida_nao_duplica(aluno):
    a = aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "Não gosta de azeitona"})
    b = aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "  não GOSTA de   azeitona "})
    assert b.status_code in (200, 201) and b.json()["id"] == a.json()["id"]
    assert len(memorias(aluno)) == 1


def test_limite_de_memorias(aluno):
    for i in range(60):
        assert aluno.post("/api/memorias", json={"tipo": "gosto", "texto": f"gosto {i}"}).status_code == 201
    r = aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "mais um"})
    assert (r.status_code, r.json()["detail"]) == (409, "limite_de_memorias")


def test_validacao_de_memoria(aluno):
    assert aluno.post("/api/memorias", json={"tipo": "outro", "texto": "x y"}).status_code == 422
    assert aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "x"}).status_code == 422
    assert aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "x" * 201}).status_code == 422
    assert (
        aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "ok ok", "origem": "coach"}).status_code
        == 422
    )


def test_memorias_exigem_login(client):
    assert client.get("/api/memorias").status_code == 401


def test_muitos_gostos_nao_impedem_restricao(aluno):
    for i in range(60):
        aluno.post("/api/memorias", json={"tipo": "gosto", "texto": f"gosto {i}"})
    assert aluno.post("/api/memorias", json={"tipo": "restricao", "texto": "celíaco"}).status_code == 201
    assert (
        aluno.post("/api/memorias", json={"tipo": "condicao", "texto": "hérnia de disco"}).status_code == 201
    )


def test_acento_e_unicode_nao_duplicam(aluno):
    a = aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "não gosta de azeitona"}).json()["id"]
    for variante in [
        "nao gosta de azeitona",
        "nã̃o gosta de azeitona".replace("ã̃", "ã"),
        "NÃO GOSTA DE AZEITONA.",
    ]:
        r = aluno.post("/api/memorias", json={"tipo": "gosto", "texto": variante})
        assert r.json()["id"] == a, variante
    assert len(memorias(aluno)) == 1


def test_texto_invisivel_recusado(aluno):
    r = aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "​​​"})
    assert r.status_code == 422


def test_editar_para_texto_repetido_409(aluno):
    aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "ama café"})
    b = aluno.post("/api/memorias", json={"tipo": "gosto", "texto": "ama chá"}).json()["id"]
    r = aluno.patch(f"/api/memorias/{b}", json={"texto": "Ama café"})
    assert (r.status_code, r.json()["detail"]) == (409, "memoria_repetida")


def test_criar_em_paralelo_nao_falha_nem_duplica(settings, aluno):
    from concurrent.futures import ThreadPoolExecutor

    from hachibu.db import connect
    from hachibu.memorias import criar

    def gravar(_):
        db = connect(settings.db_path)
        try:
            return criar(db, 1, "restricao", "celíaco", "coach")[0].id
        finally:
            db.close()

    with ThreadPoolExecutor(8) as pool:
        ids = set(pool.map(gravar, range(16)))
    assert len(ids) == 1
    assert len(memorias(aluno)) == 1
