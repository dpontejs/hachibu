"""Achados da revisão: a conversa nunca pode ficar travada, e o gasto da chave tem teto."""

from langchain_core.messages import AIMessage, ToolMessage

from hachibu.coach import tools as T
from hachibu.coach.agente import _checkpointer
from hachibu.coach.ferramentas import ErroFerramenta, validar_ajuste_metas
from hachibu.db import connect
from tests.coach_fake import chamada, roteiro
from tests.test_coach_rotas import JPEG, enviar


def _mensagens(settings, thread):
    return _checkpointer(settings).get({"configurable": {"thread_id": thread}})["channel_values"]["messages"]


def _sem_chamadas_orfas(msgs):
    respondidas = {m.tool_call_id for m in msgs if isinstance(m, ToolMessage)}
    pedidas = {c["id"] for m in msgs if isinstance(m, AIMessage) for c in m.tool_calls}
    return pedidas <= respondidas


def test_mensagem_com_aprovacao_pendente_409(app, aluno):
    app.state.modelo_coach = roteiro(chamada("ajustar_metas", {"kcal": 2400, "justificativa": "x"}), "ok")
    thread = enviar(aluno, "ajusta").json()["thread_id"]
    r = enviar(aluno, "outra coisa", thread_id=thread)
    assert (r.status_code, r.json()) == (409, {"detail": "aprovacao_pendente"})
    assert aluno.post(f"/api/coach/{thread}/decisao", json={"aprovar": True}).status_code == 200


def test_tool_que_falha_nao_trava_a_conversa(app, settings, aluno, monkeypatch):
    def quebra(*a, **k):
        raise RuntimeError("gemini 500")

    monkeypatch.setattr(T, "casar_com_taco", quebra)
    app.state.modelo_coach = roteiro(
        chamada("analisar_foto_refeicao"), "Não consegui ver a foto.", "Oi de novo!"
    )
    corpo = enviar(aluno, "foto", foto=(JPEG, "image/jpeg")).json()
    assert corpo["mensagens"][-1]["texto"] == "Não consegui ver a foto."
    r = enviar(aluno, "de novo", thread_id=corpo["thread_id"])
    assert r.status_code == 200 and r.json()["mensagens"][-1]["texto"] == "Oi de novo!"
    assert _sem_chamadas_orfas(_mensagens(settings, corpo["thread_id"]))


def test_chamada_orfa_e_remendada_antes_da_proxima_mensagem(app, settings, aluno):
    # Simula uma volta interrompida no meio (ex.: processo caiu): AIMessage com tool call sem resposta.
    app.state.modelo_coach = roteiro("Oi!", "Tudo certo.")
    thread = enviar(aluno, "oi").json()["thread_id"]
    from hachibu.coach.agente import _agente

    ag = _agente(settings, app.state.modelo_coach, 1, lambda: __import__("datetime").datetime.now())
    ag.update_state(
        {"configurable": {"thread_id": thread}},
        {"messages": [chamada("saldo_do_dia", id_="orfa")]},
        as_node="model",
    )
    r = enviar(aluno, "e aí?", thread_id=thread)
    assert r.status_code == 200
    assert _sem_chamadas_orfas(_mensagens(settings, thread))


def test_duas_propostas_na_mesma_resposta_viram_dois_cards(app, aluno):
    duas = AIMessage(
        content="",
        tool_calls=[
            {"name": "ajustar_metas", "args": {"kcal": 2400, "justificativa": "a"}, "id": "p1"},
            {"name": "ajustar_metas", "args": {"kcal": 2500, "justificativa": "b"}, "id": "p2"},
        ],
    )
    app.state.modelo_coach = roteiro(duas, "Pronto.")
    corpo = enviar(aluno, "ajusta").json()
    thread = corpo["thread_id"]
    primeiro = corpo["pendente"]["args"]["kcal"]
    r = aluno.post(f"/api/coach/{thread}/decisao", json={"aprovar": False}).json()
    assert r["pendente"] is not None and r["pendente"]["args"]["kcal"] != primeiro
    r = aluno.post(f"/api/coach/{thread}/decisao", json={"aprovar": True}).json()
    assert r["pendente"] is None
    assert aluno.get("/api/hoje").json()["metas"]["kcal"] in {2400, 2500}


def test_laco_infinito_tem_teto_e_responde(app, aluno):
    laco = [chamada("saldo_do_dia", id_=f"c{i}") for i in range(200)]
    modelo = roteiro(*laco)
    app.state.modelo_coach = modelo
    r = enviar(aluno, "oi")
    assert r.status_code == 200
    assert "reformular" in r.json()["mensagens"][-1]["texto"]
    restantes = sum(1 for _ in modelo.messages)
    assert restantes >= 180  # parou cedo, não gastou as 200 chamadas


def test_foto_grande_recusada_antes_de_ler_tudo(app, aluno):
    app.state.modelo_coach = roteiro("x")
    r = enviar(aluno, "foto", foto=(b"\xff\xd8\xff" + b"0" * (5 * 1024 * 1024), "image/jpeg"))
    assert r.status_code == 422


def test_macros_invalidos_recusados(app, settings, aluno):
    db = connect(settings.db_path)
    for kwargs in (
        {"kcal": 9000},
        {"kcal": 2400, "proteina_g": -50},
        {"kcal": 2400, "gordura_g": 900},
        {"kcal": 2400, "proteina_g": 150, "carbo_g": 50, "gordura_g": 30},
    ):
        try:
            validar_ajuste_metas(db, 1, **kwargs)
        except ErroFerramenta:
            continue
        raise AssertionError(f"aceitou {kwargs}")


def test_modelo_real_tem_timeout_e_poucas_tentativas(settings):
    from dataclasses import replace

    from hachibu.app import _modelo_coach

    m = _modelo_coach(replace(settings, gemini_api_key="chave-falsa"))
    assert m.timeout == 30 and m.max_retries == 2
