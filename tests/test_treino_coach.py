"""Plano pela conversa: rascunho, diferenças, proposta validada com aprovação humana e isolamento."""

from datetime import UTC, datetime

import pytest

from hachibu.coach.agente import responder
from hachibu.coach.tools import criar_tools
from hachibu.db import connect
from hachibu.metas import PerfilIn
from hachibu.treino.base import plano_base
from hachibu.treino.diferencas import diferencas
from hachibu.treino.modelos import CardioPlano, CorridaPlano, DiaPlano, PlanoIn
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
        cardio=CardioPlano(modalidade="caminhada", duracao_min=30, intensidade="leve"),
    )
    linhas = diferencas(antes, depois)
    assert any("séries" in linha and "segunda" in linha for linha in linhas)
    assert any("domingo" in linha and "caminhada" in linha.lower() for linha in linhas)


def test_resumo_da_semana_em_estrutura():
    from hachibu.treino.diferencas import resumo_semana

    semana = resumo_semana(base())
    assert len(semana) == 7
    descanso = next(d for d in semana if d["nome"] == "Descanso")
    assert descanso["itens"] == [] and descanso["corrida"] is None


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
    semana = r.pendente.args["semana"]
    assert r.pendente.args["mudancas"] == []  # primeiro plano: não há "antes", o card mostra a semana
    assert [d["dia"] for d in semana] == [
        "segunda",
        "terça",
        "quarta",
        "quinta",
        "sexta",
        "sábado",
        "domingo",
    ]
    segunda = semana[0]
    assert segunda["nome"] == "Superior A"
    assert segunda["itens"][0] == "Supino reto com barra · 3 × 8–12"
    assert segunda["corrida"].startswith("Corrida e caminhada")
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
    r = tools["propor_plano"].invoke({"plano": base().model_dump(), "justificativa": "x", "versao_base": 1})
    assert r.startswith("erro") and "nada muda" in r


def test_proposta_de_troca_mostra_so_a_mudanca(settings, aluno):
    db = connect(settings.db_path)
    gravar_plano(db, 1, base(), "coach")
    db.close()
    novo = base().model_dump()
    novo["dias"][1]["exercicios"][0]["exercicio_id"] = "leg_press"
    modelo = roteiro(
        chamada("propor_plano", {"plano": novo, "justificativa": "Não gosta de agachar.", "versao_base": 1}),
        "Ok",
    )
    r = falar(settings, modelo, "troca o agachamento")
    assert len(r.pendente.args["mudancas"]) == 1
    assert len(r.pendente.args["semana"]) == 7  # a semana inteira vai junto, para ver se quiser


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


# ---------- achados da revisão ----------


def test_progressao_so_vale_para_corrida_e_caminhada():
    with pytest.raises(ValueError):
        CorridaPlano(progressao=True, tipo="leve", duracao_min=30, esforco_alvo="3-4")


def test_campos_de_bloco_sao_ignorados_fora_da_corrida_e_caminhada():
    c = CorridaPlano(tipo="leve", duracao_min=30, corre_min=0, anda_min=0, repeticoes=1, esforco_alvo="3-4")
    assert (c.corre_min, c.anda_min, c.repeticoes) == (None, None, None)


def test_diferenca_ignora_enchimento_da_corrida():
    antes = base()
    depois = antes.model_copy(deep=True)
    for dia in depois.dias:
        if dia.corrida and dia.corrida.progressao:
            dia.corrida = dia.corrida.model_copy(update={"duracao_min": 99, "corre_min": 9.0})
    assert diferencas(antes, depois) == []


def test_diferenca_tirar_um_exercicio_nao_vira_cascata():
    antes = base()
    depois = antes.model_copy(deep=True)
    saiu = depois.dias[0].exercicios.pop(0)
    linhas = diferencas(antes, depois)
    assert len(linhas) == 1 and "sai" in linhas[0]
    assert diferencas(antes, depois)[0].endswith(diferencas(antes, depois)[0].split("sai ")[-1])
    assert saiu.exercicio_id  # o supino saiu e é isso que a linha diz


def test_diferenca_dias_trocados_vira_uma_linha_por_dia():
    antes = base()
    depois = antes.model_copy(deep=True)
    seg, ter = depois.dias[0], depois.dias[1]
    depois.dias[0] = ter.model_copy(update={"dia": 0})
    depois.dias[1] = seg.model_copy(update={"dia": 1})
    linhas = diferencas(antes, depois)
    assert len(linhas) == 2 and all("treino de" in linha for linha in linhas)


def test_aprovar_proposta_velha_nao_desfaz_outra(settings, aluno):
    from langchain_core.messages import AIMessage

    v1 = base()
    db = connect(settings.db_path)
    gravar_plano(db, 1, v1, "coach")
    db.close()
    troca_a = v1.model_dump()
    troca_a["dias"][0]["exercicios"][0]["exercicio_id"] = "supino_halteres"
    troca_b = v1.model_dump()
    troca_b["dias"][1]["exercicios"][0]["exercicio_id"] = "leg_press"
    # O Gemini pede as duas propostas na mesma resposta, ambas a partir da versão 1.
    duas = AIMessage(
        content="",
        tool_calls=[
            {
                "name": "propor_plano",
                "args": {"plano": troca_a, "justificativa": "a", "versao_base": 1},
                "id": "c1",
            },
            {
                "name": "propor_plano",
                "args": {"plano": troca_b, "justificativa": "b", "versao_base": 1},
                "id": "c2",
            },
        ],
    )
    modelo = roteiro(duas, "Pronto.")
    r = falar(settings, modelo, "troca o supino e o agachamento")
    assert r.pendente is not None
    r = falar(settings, modelo, decisao={"aprovar": True})
    assert ativo(settings)[0]["versao"] == 2 and r.pendente is not None
    falar(settings, modelo, decisao={"aprovar": True})
    meta, gravado = ativo(settings)
    # A segunda partiu da v1: aplicá-la desfaria a primeira. Nada é gravado; o coach propõe de novo.
    assert meta["versao"] == 2
    assert gravado.dias[0].exercicios[0].exercicio_id == "supino_halteres"


def test_primeiro_plano_tem_teto_de_corrida(settings, aluno, tools):
    exagero = base().model_dump()
    for i in (1, 3, 5):
        exagero["dias"][i]["corrida"] = {"tipo": "leve", "duracao_min": 90, "esforco_alvo": "3-4"}
    r = tools["propor_plano"].invoke({"plano": exagero, "justificativa": "x"})
    assert r.startswith("erro")


def test_iniciante_corre_pela_progressao(settings, aluno, tools):
    trocado = base().model_dump()
    for dia in trocado["dias"]:
        if dia["corrida"]:
            dia["corrida"] = {"tipo": "leve", "duracao_min": 25, "esforco_alvo": "3-4"}
    r = tools["propor_plano"].invoke({"plano": trocado, "justificativa": "x"})
    assert r.startswith("erro") and "progress" in r


def test_proposta_confere_todas_as_semanas_da_progressao(settings, aluno, tools):
    aluno.put("/api/perfil", json=BASE | {"minutos_corrida": 27})
    plano = base().model_dump()  # progressão chega a 33 min na semana 5
    plano["dias"][1]["corrida"] = plano["dias"][0]["corrida"] or {
        "progressao": True,
        "tipo": "corrida_caminhada",
        "duracao_min": 26,
        "esforco_alvo": "3-5",
    }
    r = tools["propor_plano"].invoke({"plano": plano, "justificativa": "x"})
    assert r.startswith("erro") and "corrida" in r


def test_aprovado_mas_nao_gravado_diz_isso(settings, aluno, monkeypatch):
    from hachibu.coach import ferramentas

    modelo = roteiro(chamada("propor_plano", {"plano": base().model_dump(), "justificativa": "x"}), "Ok.")
    falar(settings, modelo, "monta")

    def falha(*a, **k):
        raise ferramentas.ErroFerramenta("banco ocupado")

    monkeypatch.setattr(ferramentas, "aplicar_plano", falha)
    from hachibu.coach.agente import mensagens_da_thread

    falar(settings, modelo, decisao={"aprovar": True})
    assert any(m.startswith("aprovado, mas nada foi gravado") for m in mensagens_da_thread(settings, "t1"))


def test_cardio_leve_nao_conta_como_dia_de_treino():
    from hachibu.treino.validador import validar_plano

    p = PerfilIn(**BASE | {"dias_semana": 4})
    plano = base().model_copy(deep=True)
    plano.dias[6] = DiaPlano(
        dia=6,
        nome="Recuperação",
        cardio=CardioPlano(modalidade="caminhada", duracao_min=30, intensidade="leve"),
    )
    assert validar_plano(plano, p) == []
