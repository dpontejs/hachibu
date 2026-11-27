"""Rotas do plano de treino: ler a semana, versões, avisos e isolamento entre contas.

O plano não é gerado por rota: nasce da conversa com o coach (rascunho + proposta aprovada). Aqui os testes
gravam o plano direto pelo repositório.
"""

import sqlite3
from concurrent.futures import ThreadPoolExecutor

import pytest

from hachibu.db import connect
from hachibu.metas import PerfilIn
from hachibu.treino.base import gerar_plano_base
from hachibu.treino.repositorio import PlanoExistente, gravar_plano
from tests.test_metas import BASE


def plano(c):
    return c.get("/api/plano")


def semear(settings, perfil: dict, user_id: int = 1, substituir: bool = True) -> int:
    rascunho, pontos = gerar_plano_base(PerfilIn(**perfil))
    db = connect(settings.db_path)
    try:
        return gravar_plano(db, user_id, rascunho, "coach", pontos, substituir=substituir)
    finally:
        db.close()


def test_sem_plano_404(aluno):
    r = plano(aluno)
    assert (r.status_code, r.json()["detail"]) == (404, "plano_inexistente")


def test_ler_a_semana(settings, aluno):
    aluno.put("/api/perfil", json=BASE | {"dias_semana": 3, "nivel": "iniciante"})
    semear(settings, BASE | {"dias_semana": 3, "nivel": "iniciante"})
    corpo = plano(aluno).json()
    assert corpo["versao"] == 1 and corpo["origem"] == "coach" and corpo["semana_corrida"] == 1
    assert len(corpo["dias"]) == 7 and corpo["avisos"] == []
    segunda = corpo["dias"][0]
    assert segunda["nome"] == "Corpo inteiro A"
    primeiro = segunda["exercicios"][0]
    assert primeiro["exercicio_id"] == "agachamento_livre" and primeiro["nome"].startswith("Agachamento")
    corrida = segunda["corrida"]
    assert corrida["progressao"] is True
    assert (corrida["corre_min"], corrida["anda_min"], corrida["repeticoes"]) == (1, 2, 7)


def test_versao_nova_substitui_a_ativa(settings, aluno):
    semear(settings, BASE)
    assert semear(settings, BASE | {"equipamento": "peso_corporal"}) == 2
    assert plano(aluno).json()["versao"] == 2


def test_perfil_mudou_plano_fica_com_avisos(settings, aluno):
    semear(settings, BASE)
    aluno.put("/api/perfil", json=BASE | {"equipamento": "peso_corporal"})
    avisos = plano(aluno).json()["avisos"]
    assert avisos and any("equipamento" in a for a in avisos)


def test_pontos_do_rascunho_ficam_com_a_versao(settings, aluno):
    perfil = BASE | {"dias_semana": 7, "corridas_semana": 6, "corrida_quando": "mesmo_dia"}
    aluno.put("/api/perfil", json=perfil)
    semear(settings, perfil)
    assert any("recuperação" in n for n in plano(aluno).json()["notas"])


def test_avisa_quando_ha_condicoes_fisicas(settings, aluno):
    semear(settings, BASE)
    assert plano(aluno).json()["tem_condicoes"] is False
    aluno.post("/api/memorias", json={"tipo": "condicao", "texto": "dor no joelho direito"})
    assert plano(aluno).json()["tem_condicoes"] is True


def test_condicao_de_saude_do_perfil_tambem_conta(settings, aluno):
    aluno.put("/api/perfil", json=BASE | {"condicoes_saude": "hérnia de disco"})
    semear(settings, BASE)
    assert plano(aluno).json()["tem_condicoes"] is True


def test_plano_de_outro_usuario_nao_aparece(settings, aluno, make_user):
    semear(settings, BASE)
    outro = make_user("b@x.com")
    outro.put("/api/perfil", json=BASE)
    assert plano(outro).status_code == 404


def test_perfil_guarda_as_preferencias_de_corrida(aluno):
    prefs = {
        "nivel_corrida": "iniciante",
        "corrida_quando": "mesmo_dia",
        "corridas_semana": 4,
        "minutos_corrida": 35,
    }
    assert aluno.put("/api/perfil", json=BASE | prefs).status_code == 200
    perfil = aluno.get("/api/perfil").json()["perfil"]
    assert {k: perfil[k] for k in prefs} == prefs


def test_nao_existe_rota_que_gera_plano_sem_conversa(aluno):
    assert aluno.post("/api/plano/base").status_code in (404, 405)


def test_buscar_exercicios(aluno):
    r = aluno.get("/api/exercicios", params={"q": "supino"})
    assert r.status_code == 200
    ids = [e["id"] for e in r.json()]
    assert "supino_reto" in ids and all("supino" in e["nome"].lower() for e in r.json())


def test_rotas_de_treino_exigem_login(client):
    assert client.get("/api/plano").status_code == 401


def test_gravar_sem_substituir_recusa_e_e_atomico(settings, aluno):
    with ThreadPoolExecutor(4) as pool:
        resultados = list(pool.map(lambda _: _tentar(settings), range(4)))
    assert sorted(resultados) == ["existe", "existe", "existe", "ok"]
    assert plano(aluno).json()["versao"] == 1


def _tentar(settings) -> str:
    try:
        semear(settings, BASE, substituir=False)
        return "ok"
    except PlanoExistente:
        return "existe"


def test_banco_garante_um_plano_ativo_por_usuario(settings, aluno):
    semear(settings, BASE)
    with sqlite3.connect(settings.db_path) as conn, pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO planos (user_id, versao, origem, dados, criado_em, ativo) "
            "VALUES (1, 9, 'base', '{}', 'x', 1)"
        )
