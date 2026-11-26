from hachibu.metas import PerfilIn, calcular_metas, diagnostico
from tests.test_metas import BASE


def test_meta_profissional_substitui_formula():
    m = calcular_metas(PerfilIn(**BASE, meta_profissional_kcal=1700))
    assert (m.kcal, m.proteina_g, m.gordura_g, m.carbo_g, m.origem) == (1700, 144, 64, 137, "profissional")


def test_formula_tem_origem_formula():
    assert calcular_metas(PerfilIn(**BASE)).origem == "formula"


def test_meta_profissional_com_macros():
    m = calcular_metas(
        PerfilIn(
            **BASE,
            meta_profissional_kcal=1700,
            meta_profissional_proteina_g=160,
            meta_profissional_carbo_g=150,
            meta_profissional_gordura_g=50,
        )
    )
    assert (m.kcal, m.proteina_g, m.carbo_g, m.gordura_g) == (1700, 160, 150, 50)


def test_meta_profissional_fora_da_faixa(make_user):
    c = make_user()
    for campo, valor in [
        ("meta_profissional_kcal", 900),
        ("meta_profissional_kcal", 5001),
        ("meta_profissional_gordura_g", 301),
    ]:
        assert c.put("/api/perfil", json={**BASE, campo: valor}).status_code == 422, campo


def test_remover_meta_profissional_volta_formula(make_user):
    c = make_user()
    c.put("/api/perfil", json={**BASE, "meta_profissional_kcal": 1700})
    r = c.put("/api/perfil", json={**BASE, "meta_profissional_kcal": None})
    assert (r.json()["metas"]["kcal"], r.json()["metas"]["origem"]) == (2759, "formula")


def test_diagnostico_base():
    d = diagnostico(PerfilIn(**BASE, cintura_cm=90))
    assert (d.tmb, d.formula, d.fator_atividade, d.gasto_diario) == (1780, "mifflin-st-jeor", 1.55, 2759)
    assert (d.ajuste_objetivo, d.relacao_cintura_altura, d.alerta_cintura) == (0, 0.5, True)
    assert d.abaixo_do_piso is False and d.metas.kcal == 2759


def test_diagnostico_sem_cintura():
    d = diagnostico(PerfilIn(**BASE))
    assert d.relacao_cintura_altura is None and d.alerta_cintura is False


def test_diagnostico_katch():
    assert diagnostico(PerfilIn(**BASE, percentual_gordura=15)).formula == "katch-mcardle"


def test_diagnostico_avisa_meta_abaixo_do_piso():
    d = diagnostico(PerfilIn(**BASE, meta_profissional_kcal=1200))
    assert d.abaixo_do_piso is True and d.metas.kcal == 1200


def test_rota_diagnostico(make_user):
    c = make_user()
    assert c.get("/api/diagnostico").status_code == 409
    c.put("/api/perfil", json={**BASE, "cintura_cm": 90})
    assert c.get("/api/diagnostico").json()["alerta_cintura"] is True


def test_hoje_mostra_origem(make_user):
    c = make_user()
    c.put("/api/perfil", json={**BASE, "meta_profissional_kcal": 1700})
    assert c.get("/api/hoje").json()["metas"]["origem"] == "profissional"
    assert c.get("/api/perfil").json()["perfil"]["meta_profissional_kcal"] == 1700


def test_ajuste_e_diferenca_em_kcal_com_sinal():
    # Perder: meta 2207 contra gasto 2759 → déficit de 552 kcal (negativo), nunca um fator 0.8.
    assert diagnostico(PerfilIn(**{**BASE, "objetivo": "perder"})).ajuste_objetivo == -552
    assert diagnostico(PerfilIn(**{**BASE, "objetivo": "ganhar"})).ajuste_objetivo == 276
    assert diagnostico(PerfilIn(**BASE, meta_profissional_kcal=1700)).ajuste_objetivo == 1700 - 2759
