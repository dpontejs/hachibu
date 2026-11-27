"""Plano pela conversa: rascunho, diferenças, proposta validada com aprovação humana e isolamento."""

from datetime import UTC, datetime

import pytest

from hachibu.coach.agente import responder
from hachibu.coach.tools import criar_tools
from hachibu.db import connect
from hachibu.metas import PerfilIn
from hachibu.treino.base import plano_base
from hachibu.treino.diferencas import diferencas
from hachibu.treino.modelos import CorridaPlano, DiaPlano, PlanoIn
from hachibu.treino.repositorio import gravar_plano, plano_ativo
from tests.coach_fake import chamada, roteiro
from tests.test_metas import BASE

AGORA = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)


@pytest.fixture
def tools(settings, aluno):
    return {t.name: t for t in criar_tools(settings.db_path, 1, lambda: AGORA)}


def base() -> PlanoIn:
    return plano_base(PerfilIn(**BASE))


def ativo(settings):
    db = connect(settings.db_path)
    try:
        return plano_ativo(db, 1)
    finally:
        db.close()


def falar(settings, modelo, mensagem=None, decisao=None):
    return responder(settings, modelo, 1, "t1", mensagem=mensagem, decisao=decisao, agora=lambda: AGORA)


# ---------- diferenças ----------


def test_diferencas_trocar_um_exercicio():
    antes = base()
    depois = antes.model_copy(deep=True)
    depois.dias[1].exercicios[0] = (
        depois.dias[1].exercicios[0].model_copy(update={"exercicio_id": "leg_press"})
    )
    linhas = diferencas(antes, depois)
    assert len(linhas) == 1
    assert "terça" in linhas[0] and "Agachamento livre com barra" in linhas[0] and "Leg press" in linhas[0]


def test_diferencas_series_e_corrida():
    antes = base()
    depois = antes.model_copy(deep=True)
    depois.dias[0].exercicios[0].series += 1
    depois.dias[6] = DiaPlano(
        dia=6,
        nome="Recuperação",
        corrida=CorridaPlano(tipo="recuperacao", duracao_min=30, esforco_alvo="1-3"),
    )
    linhas = diferencas(antes, depois)
    assert any("séries" in linha and "segunda" in linha for linha in linhas)
    assert any("domingo" in linha and "recuperação" in linha.lower() for linha in linhas)


def test_diferencas_sem_plano_anterior_resume_a_semana():
    linhas = diferencas(None, base())
    assert len(linhas) == 7 and linhas[0].startswith("segunda:")


def test_diferencas_iguais_vazio():
    assert diferencas(base(), base()) == []


# ---------- tools ----------


def test_tools_novas_sem_user_id(tools):
    for nome in ("rascunho_plano", "ler_plano", "buscar_exercicio", "propor_plano"):
        assert nome in tools
        assert not set(tools[nome].args) & {"user_id", "db", "db_path"}


def test_rascunho_traz_plano_legenda_e_pontos(settings, aluno, tools):
    aluno.put(
        "/api/perfil", json=BASE | {"dias_semana": 7, "corridas_semana": 6, "corrida_quando": "mesmo_dia"}
    )
    import json

    r = json.loads(tools["rascunho_plano"].invoke({}))
    PlanoIn.model_validate(r["plano"])
    assert r["legenda"]["agachamento_livre"].startswith("Agachamento")
    assert any("recuperação" in p for p in r["pontos"])


def test_ler_plano_sem_plano_avisa(tools):
    assert tools["ler_plano"].invoke({}).startswith("erro")


def test_buscar_exercicio_respeita_o_equipamento(aluno, tools):
    import json

    aluno.put("/api/perfil", json=BASE | {"equipamento": "peso_corporal"})
    ids = [e["id"] for e in json.loads(tools["buscar_exercicio"].invoke({"termo": "agachamento"}))]
    assert "agachamento_corporal" in ids and "agachamento_livre" not in ids


# ---------- proposta com aprovação ----------


def test_proposta_valida_pausa_e_aprovar_grava_versao_do_coach(settings, aluno):
    plano = base().model_dump()
    modelo = roteiro(
        chamada("propor_plano", {"plano": plano, "justificativa": "Seu primeiro plano."}), "Pronto!"
    )
    r = falar(settings, modelo, "monta meu plano")
    assert r.pendente is not None and r.pendente.ferramenta == "propor_plano"
    assert len(r.pendente.args["mudancas"]) == 7
    assert ativo(settings) is None  # nada gravado antes de aprovar
    r = falar(settings, modelo, decisao={"aprovar": True})
    meta, gravado = ativo(settings)
    assert meta["origem"] == "coach" and gravado == PlanoIn.model_validate(plano)


def test_proposta_recusada_nao_grava(settings, aluno):
    modelo = roteiro(chamada("propor_plano", {"plano": base().model_dump(), "justificativa": "x"}), "Ok.")
    falar(settings, modelo, "monta")
    falar(settings, modelo, decisao={"aprovar": False, "motivo": "quero mais corrida"})
    assert ativo(settings) is None


def test_proposta_invalida_nao_chega_ao_aluno(settings, aluno):
    invalido = base().model_dump()
    invalido["dias"][0]["exercicios"][0]["exercicio_id"] = "voo_do_dragao"
    modelo = roteiro(chamada("propor_plano", {"plano": invalido, "justificativa": "x"}), "Corrigi.")
    r = falar(settings, modelo, "monta")
    assert r.pendente is None and ativo(settings) is None


def test_proposta_igual_ao_plano_atual_e_recusada(settings, aluno, tools):
    db = connect(settings.db_path)
    gravar_plano(db, 1, base(), "coach")
    db.close()
    r = tools["propor_plano"].invoke({"plano": base().model_dump(), "justificativa": "x"})
    assert r.startswith("erro") and "nada muda" in r


def test_proposta_de_troca_mostra_so_a_mudanca(settings, aluno):
    db = connect(settings.db_path)
    gravar_plano(db, 1, base(), "coach")
    db.close()
    novo = base().model_dump()
    novo["dias"][1]["exercicios"][0]["exercicio_id"] = "leg_press"
    modelo = roteiro(
        chamada("propor_plano", {"plano": novo, "justificativa": "Você não gosta de agachar."}), "Ok"
    )
    r = falar(settings, modelo, "troca o agachamento")
    assert len(r.pendente.args["mudancas"]) == 1


def test_perfil_mudou_antes_de_aprovar_revalida(settings, aluno):
    modelo = roteiro(chamada("propor_plano", {"plano": base().model_dump(), "justificativa": "x"}), "Ok.")
    falar(settings, modelo, "monta")
    aluno.put("/api/perfil", json=BASE | {"equipamento": "peso_corporal"})
    falar(settings, modelo, decisao={"aprovar": True})
    assert ativo(settings) is None  # o plano de academia não vale mais para quem treina em casa


def test_plano_de_outro_usuario_fica_isolado(settings, aluno, make_user):
    outro = make_user("b@x.com")
    outro.put("/api/perfil", json=BASE)
    db = connect(settings.db_path)
    gravar_plano(db, 2, base(), "coach")
    db.close()
    tools = {t.name: t for t in criar_tools(settings.db_path, 1, lambda: AGORA)}
    assert tools["ler_plano"].invoke({}).startswith("erro")
