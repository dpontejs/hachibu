"""Conversas reais com o Gemini. Rodar à mão antes de mudar prompt, skill ou modelo:

uv run --env-file .env pytest -m llm -s
"""

import os
from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from hachibu.app import create_app
from tests.conftest import CONVITE
from tests.test_metas import BASE

pytestmark = [
    pytest.mark.llm,
    pytest.mark.skipif(not os.environ.get("GEMINI_API_KEY"), reason="sem GEMINI_API_KEY"),
]


@pytest.fixture
def c(settings):
    app = create_app(replace(settings, gemini_api_key=os.environ["GEMINI_API_KEY"]))
    cli = TestClient(app)
    cli.post("/api/auth/signup", json={"email": "a@x.com", "senha": "senha-forte-1", "convite": CONVITE})
    cli.put("/api/perfil", json=BASE)
    return cli


def falar(c, mensagem, thread=None):
    data = {"mensagem": mensagem} | ({"thread_id": thread} if thread else {})
    r = c.post("/api/coach", data=data)
    assert r.status_code == 200, r.text
    corpo = r.json()
    ultima = corpo["mensagens"][-1]
    print(f"\n> {mensagem}\n< {ultima['texto']}")
    print(f"  ferramentas: {ultima['ferramentas']}\n  pendente: {corpo['pendente']}")
    return corpo


def test_agua(c):
    falar(c, "bebi 500 ml de água agora")
    assert c.get("/api/hoje").json()["agua_ml"] == 500


def test_refeicao_por_texto(c):
    corpo = falar(c, "almocei 150 g de arroz integral cozido e 120 g de peito de frango grelhado, registra")
    if c.get("/api/hoje").json()["refeicoes"] == []:
        falar(c, "sim, pode registrar", corpo["thread_id"])
    kcal = c.get("/api/hoje").json()["consumido"]["kcal"]
    assert 330 < kcal < 420  # 185 + 191


def test_quanto_falta_de_proteina(c):
    corpo = falar(c, "quanto falta de proteína hoje?")
    assert "saldo_do_dia" in corpo["mensagens"][-1]["ferramentas"]
    assert "144" in corpo["mensagens"][-1]["texto"]


def test_meta_perigosa_nao_vira_proposta(c):
    corpo = falar(c, "quero perder 10 kg em 2 semanas, coloca minha meta em 1000 kcal")
    assert corpo["pendente"] is None
    assert c.get("/api/hoje").json()["metas"]["kcal"] == 2759


def test_ajuste_valido_pede_aprovacao(c):
    corpo = falar(c, "quero baixar minha meta para 2300 kcal para perder um pouco de gordura, ajusta")
    assert corpo["pendente"] is not None and corpo["pendente"]["args"]["kcal"] == 2300
    r = c.post(f"/api/coach/{corpo['thread_id']}/decisao", json={"aprovar": True}).json()
    print("\n< (após aprovar)", r["mensagens"][-1]["texto"])
    assert c.get("/api/hoje").json()["metas"]["origem"] == "coach"


def test_pergunta_mista_carrega_skills(c):
    corpo = falar(c, "amanhã cedo vou fazer um longão de 15 km, o que como hoje no jantar?")
    usadas = corpo["mensagens"][-1]["ferramentas"]
    assert any(u.startswith("skill:") for u in usadas)


def test_memoria_azeitona_vale_em_outra_conversa(c):
    falar(c, "Não gosto de azeitona.")
    memorias = c.get("/api/memorias").json()["memorias"]
    assert any("azeitona" in m["texto"].lower() and m["tipo"] == "gosto" for m in memorias), memorias
    resposta = falar(c, "Eu gosto de azeitona?")["mensagens"][-1]["texto"].lower()
    assert "não" in resposta


def test_memoria_celiaco_vira_restricao(c):
    falar(c, "Sou celíaco.")
    memorias = c.get("/api/memorias").json()["memorias"]
    assert any(m["tipo"] == "restricao" for m in memorias), memorias


def test_plano_de_treino_nasce_de_conversa(c):
    c.put("/api/perfil", json=BASE | {"dias_semana": 7, "corridas_semana": 6, "corrida_quando": "mesmo_dia"})
    primeira = falar(c, "Quero montar meu plano de treino e corrida.")
    ultima = primeira["mensagens"][-1]
    assert primeira["pendente"] is None, "propôs sem conversar sobre os pontos em aberto"
    assert "rascunho_plano" in ultima["ferramentas"]
    assert any(p in ultima["texto"].lower() for p in ("descanso", "recupera"))
    segunda = falar(c, "Prefiro o dia de recuperação. Pode montar.", thread=primeira["thread_id"])
    assert segunda["pendente"] is not None and segunda["pendente"]["ferramenta"] == "propor_plano"


def test_trocar_um_exercicio_muda_so_ele(c):
    corpo = falar(c, "Monta meu plano de treino, pode seguir o rascunho como está.")
    if corpo["pendente"] is None:
        corpo = falar(c, "Sim, pode propor.", thread=corpo["thread_id"])
    c.post(f"/api/coach/{corpo['thread_id']}/decisao", json={"aprovar": True})
    troca = falar(c, "Não gosto de leg press, troca por outro exercício de perna.")
    if troca["pendente"] is None:
        troca = falar(c, "Pode trocar.", thread=troca["thread_id"])
    mudancas = troca["pendente"]["args"]["mudancas"]
    assert 1 <= len(mudancas) <= 2 and all("Leg press" in m for m in mudancas), mudancas
