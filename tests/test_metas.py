from hachibu.metas import Metas, PerfilIn, calcular_metas

BASE = dict(
    sexo="M",
    idade=30,
    altura_cm=180,
    peso_kg=80,
    objetivo="manter",
    nivel="intermediario",
    dias_semana=4,
    minutos_sessao=60,
    equipamento="academia",
)


def test_metas_homem_manter():
    assert calcular_metas(PerfilIn(**BASE)) == Metas(
        kcal=2759, proteina_g=144, carbo_g=402, gordura_g=64, agua_ml=2800
    )


def test_metas_piso_feminino():
    p = PerfilIn(
        **{
            **BASE,
            "sexo": "F",
            "idade": 50,
            "altura_cm": 150,
            "peso_kg": 45,
            "dias_semana": 1,
            "objetivo": "perder",
        }
    )
    assert calcular_metas(p).kcal == 1200


def test_metas_piso_masculino():
    p = PerfilIn(
        **{**BASE, "idade": 80, "altura_cm": 150, "peso_kg": 45, "dias_semana": 1, "objetivo": "perder"}
    )
    assert calcular_metas(p).kcal == 1500


def test_metas_com_percentual_gordura():
    m = calcular_metas(PerfilIn(**BASE, percentual_gordura=15))
    assert (m.kcal, m.proteina_g, m.gordura_g, m.carbo_g) == (2850, 144, 64, 425)


def test_metas_ganhar_e_perder_mudam_kcal_e_proteina():
    ganhar = calcular_metas(PerfilIn(**{**BASE, "objetivo": "ganhar"}))
    perder = calcular_metas(PerfilIn(**{**BASE, "objetivo": "perder"}))
    assert ganhar.kcal == round(2759 * 1.10)
    assert perder.kcal == round(2759 * 0.80)
    assert (ganhar.proteina_g, perder.proteina_g) == (160, 176)


def test_carbo_nunca_negativo():
    p = PerfilIn(
        **{
            **BASE,
            "sexo": "F",
            "idade": 80,
            "altura_cm": 150,
            "peso_kg": 120,
            "dias_semana": 1,
            "objetivo": "perder",
        }
    )
    assert calcular_metas(p).carbo_g >= 0
