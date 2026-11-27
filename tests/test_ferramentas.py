from datetime import UTC, datetime

import pytest

from hachibu.coach import ferramentas as f
from hachibu.db import connect
from tests.test_metas import BASE

AGORA = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)  # 12h em Brasília


@pytest.fixture
def ctx(app, settings, make_user):
    c = make_user()
    c.put("/api/perfil", json=BASE)
    db = connect(settings.db_path)
    yield db, 1
    db.close()


def test_ler_perfil(ctx):
    db, uid = ctx
    assert f.ler_perfil(db, uid)["peso_kg"] == 80


def test_ler_perfil_sem_perfil(app, settings, make_user):
    make_user()
    with pytest.raises(f.ErroFerramenta, match="perfil"):
        f.ler_perfil(connect(settings.db_path), 1)


def test_ler_diagnostico(ctx):
    db, uid = ctx
    assert f.ler_diagnostico(db, uid)["gasto_diario"] == 2759


def test_registrar_agua_e_saldo(ctx):
    db, uid = ctx
    f.registrar_agua(db, uid, 500, AGORA)
    saldo = f.saldo_do_dia(db, uid, AGORA)
    assert saldo["agua_ml"] == 500 and saldo["metas"]["kcal"] == 2759
    assert saldo["faltam"]["kcal"] == 2759


def test_registrar_agua_invalida(ctx):
    db, uid = ctx
    with pytest.raises(f.ErroFerramenta):
        f.registrar_agua(db, uid, 0, AGORA)


def test_buscar_alimento_taco(ctx):
    db, uid = ctx
    r = f.buscar_alimento_taco(db, uid, "arroz integral cozido")
    assert r[0]["id"] == 1 and len(r) <= 8


def test_registrar_refeicao_calcula_e_soma(ctx):
    db, uid = ctx
    r = f.registrar_refeicao(db, uid, "Almoço", [{"alimento_id": 1, "gramas": 150}], AGORA)
    assert r["kcal"] == 185.3
    assert f.saldo_do_dia(db, uid, AGORA)["consumido"]["kcal"] == 185.3


def test_registrar_refeicao_alimento_inexistente(ctx):
    db, uid = ctx
    with pytest.raises(f.ErroFerramenta, match="99999"):
        f.registrar_refeicao(db, uid, "X", [{"alimento_id": 99999, "gramas": 100}], AGORA)
    assert f.saldo_do_dia(db, uid, AGORA)["refeicoes"] == []


def test_validar_ajuste_abaixo_do_piso(ctx):
    db, uid = ctx
    with pytest.raises(f.ErroFerramenta, match="piso"):
        f.validar_ajuste_metas(db, uid, kcal=1400)


def test_validar_ajuste_deficit_acima_de_25(ctx):
    db, uid = ctx
    with pytest.raises(f.ErroFerramenta, match="25%"):
        f.validar_ajuste_metas(db, uid, kcal=2068)
    assert f.validar_ajuste_metas(db, uid, kcal=2069).kcal == 2069


def test_validar_ajuste_completa_macros_pela_formula(ctx):
    db, uid = ctx
    m = f.validar_ajuste_metas(db, uid, kcal=2400)
    assert (m.proteina_g, m.gordura_g, m.carbo_g, m.origem) == (144, 64, 312, "coach")


def test_aplicar_ajuste_grava_origem_coach(ctx):
    db, uid = ctx
    f.aplicar_ajuste_metas(db, uid, kcal=2400, agora=AGORA)
    saldo = f.saldo_do_dia(db, uid, AGORA)
    assert (saldo["metas"]["kcal"], saldo["metas"]["origem"]) == (2400, "coach")
    assert db.execute("SELECT ajustada_em FROM goals WHERE user_id = 1").fetchone()[0] == AGORA.isoformat()
