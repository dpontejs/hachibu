import json
from datetime import UTC, datetime

import pytest

from hachibu.coach.skills import catalogo_skills, criar_tool_carregar_skill
from hachibu.coach.tools import criar_tools
from tests.test_metas import BASE

AGORA = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)


@pytest.fixture
def tools(settings, make_user):
    make_user().put("/api/perfil", json=BASE)
    return {t.name: t for t in criar_tools(settings.db_path, 1, lambda: AGORA)}


def test_tools_sem_user_id_no_schema(tools):
    for t in tools.values():
        campos = set(t.args)
        assert not campos & {"user_id", "db", "db_path", "agora"}, t.name
    assert {
        "ler_perfil",
        "saldo_do_dia",
        "buscar_alimento_taco",
        "registrar_refeicao",
        "registrar_agua",
        "ler_diagnostico",
        "ajustar_metas",
        "carregar_skill",
    } <= set(tools)


def test_tool_registrar_agua_usa_usuario_da_sessao(tools, make_user, settings):
    outro = make_user("b@x.com")
    outro.put("/api/perfil", json=BASE)
    tools["registrar_agua"].invoke({"ml": 500})
    assert json.loads(tools["saldo_do_dia"].invoke({}))["agua_ml"] == 500
    b = {t.name: t for t in criar_tools(settings.db_path, 2, lambda: AGORA)}
    assert json.loads(b["saldo_do_dia"].invoke({}))["agua_ml"] == 0


def test_tool_erro_vira_texto(tools):
    r = tools["registrar_refeicao"].invoke({"nome": "X", "itens": [{"alimento_id": 99999, "gramas": 100}]})
    assert r.startswith("erro:") and "99999" in r


def test_catalogo_lista_tres_skills():
    cat = catalogo_skills()
    for nome in ("nutricao", "musculacao", "corrida"):
        assert f"- {nome}:" in cat


def test_carregar_skill():
    t = criar_tool_carregar_skill()
    assert "10%" in t.invoke({"nome": "corrida"})
    r = t.invoke({"nome": "yoga"})
    assert r.startswith("erro:") and "corrida" in r
