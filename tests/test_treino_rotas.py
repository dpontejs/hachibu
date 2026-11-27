"""Rotas do plano de treino: gerar o plano base, ler a semana, versões, avisos e isolamento entre contas."""

from tests.test_metas import BASE


def plano(c):
    return c.get("/api/plano")


def test_sem_plano_404(aluno):
    r = plano(aluno)
    assert (r.status_code, r.json()["detail"]) == (404, "plano_inexistente")


def test_gerar_plano_base_e_ler_a_semana(aluno):
    aluno.put("/api/perfil", json=BASE | {"dias_semana": 3, "nivel": "iniciante"})
    r = aluno.post("/api/plano/base")
    assert r.status_code == 201
    corpo = plano(aluno).json()
    assert corpo["versao"] == 1 and corpo["origem"] == "base" and corpo["semana_corrida"] == 1
    assert len(corpo["dias"]) == 7 and corpo["avisos"] == []
    segunda = corpo["dias"][0]
    assert segunda["nome"] == "Corpo inteiro A"
    primeiro = segunda["exercicios"][0]
    assert primeiro["exercicio_id"] == "agachamento_livre" and primeiro["nome"].startswith("Agachamento")
    corrida = segunda["corrida"]
    assert corrida["progressao"] is True and (
        corrida["corre_min"],
        corrida["anda_min"],
        corrida["repeticoes"],
    ) == (
        1,
        2,
        7,
    )


def test_gerar_de_novo_sem_substituir_409(aluno):
    aluno.post("/api/plano/base")
    r = aluno.post("/api/plano/base")
    assert (r.status_code, r.json()["detail"]) == (409, "plano_existente")


def test_substituir_cria_versao_nova(aluno):
    aluno.post("/api/plano/base")
    aluno.put("/api/perfil", json=BASE | {"equipamento": "peso_corporal"})
    assert aluno.post("/api/plano/base?substituir=true").status_code == 201
    corpo = plano(aluno).json()
    assert corpo["versao"] == 2 and corpo["origem"] == "base"
    assert corpo["avisos"] == []


def test_perfil_mudou_plano_fica_com_avisos(aluno):
    aluno.post("/api/plano/base")
    aluno.put("/api/perfil", json=BASE | {"equipamento": "peso_corporal"})
    avisos = plano(aluno).json()["avisos"]
    assert avisos and any("equipamento" in a for a in avisos)


def test_avisa_quando_ha_condicoes_fisicas(aluno):
    aluno.post("/api/plano/base")
    assert plano(aluno).json()["tem_condicoes"] is False
    aluno.post("/api/memorias", json={"tipo": "condicao", "texto": "dor no joelho direito"})
    assert plano(aluno).json()["tem_condicoes"] is True


def test_condicao_de_saude_do_perfil_tambem_conta(aluno):
    aluno.put("/api/perfil", json=BASE | {"condicoes_saude": "hérnia de disco"})
    aluno.post("/api/plano/base")
    assert plano(aluno).json()["tem_condicoes"] is True


def test_plano_de_outro_usuario_nao_aparece(aluno, make_user):
    aluno.post("/api/plano/base")
    outro = make_user("b@x.com")
    outro.put("/api/perfil", json=BASE)
    assert plano(outro).status_code == 404


def test_sem_perfil_nao_gera_plano(make_user):
    c = make_user("c@x.com")
    r = c.post("/api/plano/base")
    assert (r.status_code, r.json()["detail"]) == (409, "perfil_incompleto")


def test_perfil_guarda_as_preferencias_de_corrida(aluno):
    prefs = {"nivel_corrida": "iniciante", "corrida_quando": "mesmo_dia", "corridas_semana": 4}
    assert aluno.put("/api/perfil", json=BASE | prefs).status_code == 200
    perfil = aluno.get("/api/perfil").json()["perfil"]
    assert {k: perfil[k] for k in prefs} == prefs


def test_buscar_exercicios(aluno):
    r = aluno.get("/api/exercicios", params={"q": "supino"})
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert "supino_reto" in ids and all("supino" in e["nome"].lower() for e in r.json())


def test_rotas_de_treino_exigem_login(client):
    assert client.get("/api/plano").status_code == 401
    assert client.post("/api/plano/base").status_code == 401
