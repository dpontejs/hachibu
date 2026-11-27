"""Treino sem banco: catálogo, progressão da corrida, plano base e validador (regras em código, sem LLM)."""

import itertools

import pytest

from hachibu.metas import PerfilIn
from hachibu.treino.base import gerar_plano_base, plano_base
from hachibu.treino.exercicios import CATALOGO, PERNAS, buscar, por_id
from hachibu.treino.modelos import CorridaPlano, DiaPlano, ExercicioPlano, PlanoIn
from hachibu.treino.progressao import PROGRESSAO_INICIANTE, corrida_da_semana
from hachibu.treino.validador import validar_plano
from tests.test_metas import BASE


def perfil(**mudancas) -> PerfilIn:
    return PerfilIn(**{**BASE, **mudancas})


def dias_com(plano: PlanoIn, cond) -> list[DiaPlano]:
    return [d for d in plano.dias if cond(d)]


# ---------- catálogo ----------


def test_catalogo_tem_ids_unicos_e_cobre_cada_equipamento():
    ids = [e.id for e in CATALOGO]
    assert len(ids) == len(set(ids)) and len(ids) >= 50
    for equipamento in ("academia", "casa_halteres", "peso_corporal"):
        grupos = {e.grupo for e in CATALOGO if equipamento in e.equipamentos}
        assert {"peito", "costas", "ombros", "quadriceps", "posterior", "core"} <= grupos, equipamento


def test_busca_ignora_acento_e_caixa():
    assert "agachamento_livre" in [e.id for e in buscar("AGACHAMENTO")]
    assert por_id("supino_reto").nome.startswith("Supino")
    assert {"quadriceps", "posterior", "gluteos", "panturrilha"} == PERNAS


# ---------- progressão da corrida ----------


def test_progressao_comeca_alternando_e_termina_continua():
    assert len(PROGRESSAO_INICIANTE) == 9
    s1, s9 = corrida_da_semana(1), corrida_da_semana(9)
    assert (s1.corre_min, s1.anda_min, s1.repeticoes) == (1, 2, 7)
    assert s1.duracao_min == 5 + 7 * 3  # aquecimento + blocos
    assert (s9.corre_min, s9.anda_min, s9.repeticoes) == (25, 0, 1)
    assert all(corrida_da_semana(n).tipo == "corrida_caminhada" for n in range(1, 10))


def test_progressao_fora_da_faixa_fica_nas_pontas():
    assert corrida_da_semana(0) == corrida_da_semana(1)
    assert corrida_da_semana(12) == corrida_da_semana(9)


# ---------- plano base ----------


def test_plano_base_iniciante_3_dias():
    p = perfil(dias_semana=3, minutos_sessao=60, nivel="iniciante")
    plano = plano_base(p)
    musc = dias_com(plano, lambda d: d.exercicios)
    assert [d.nome for d in musc] == ["Corpo inteiro A", "Corpo inteiro B", "Corpo inteiro A"]
    corridas = dias_com(plano, lambda d: d.corrida)
    assert len(corridas) == 3 and all(d.exercicios for d in corridas)  # mesmo dia (automático, < 5 dias)
    assert all(d.corrida.progressao and d.corrida.tipo == "corrida_caminhada" for d in corridas)
    assert len(dias_com(plano, lambda d: not d.exercicios and not d.corrida)) == 4
    assert validar_plano(plano, p) == []


def test_plano_base_cardio_todo_treino():
    p = perfil(dias_semana=4, corrida_quando="mesmo_dia", corridas_semana=4)
    plano = plano_base(p)
    assert all(d.corrida for d in plano.dias if d.exercicios)
    assert len(dias_com(plano, lambda d: d.corrida)) == 4


def test_plano_base_dias_separados():
    p = perfil(dias_semana=6, corrida_quando="dias_separados")
    plano = plano_base(p)
    assert not dias_com(plano, lambda d: d.exercicios and d.corrida)
    assert len(dias_com(plano, lambda d: d.corrida)) == 3
    assert validar_plano(plano, p) == []


def test_plano_base_automatico_com_5_dias_separa():
    plano = plano_base(perfil(dias_semana=5))
    assert not dias_com(plano, lambda d: d.exercicios and d.corrida)


def test_plano_base_respeita_equipamento():
    plano = plano_base(perfil(equipamento="peso_corporal"))
    for dia in plano.dias:
        for ex in dia.exercicios:
            assert "peso_corporal" in por_id(ex.exercicio_id).equipamentos


def test_plano_base_nivel_muda_series():
    ini = plano_base(perfil(nivel="iniciante", corridas_semana=1))
    ava = plano_base(perfil(nivel="avancado", corridas_semana=1))
    total = lambda pl: sum(e.series for d in pl.dias for e in d.exercicios)  # noqa: E731
    assert total(ava) > total(ini)


def test_corredor_intermediario_tem_leves_e_longao():
    plano = plano_base(perfil(nivel_corrida="intermediario", dias_semana=6, corrida_quando="dias_separados"))
    tipos = sorted(d.corrida.tipo for d in plano.dias if d.corrida)
    assert tipos == ["leve", "leve", "longao"]
    assert not any(d.corrida.progressao for d in plano.dias if d.corrida)


@pytest.mark.parametrize(
    "dias,equipamento,nivel,quando,minutos,nivel_corrida",
    list(
        itertools.product(
            range(1, 8),
            ["academia", "casa_halteres", "peso_corporal"],
            ["iniciante", "intermediario", "avancado"],
            ["automatico", "mesmo_dia", "dias_separados"],
            [15, 20, 30, 45, 60, 90],
            [None, "intermediario", "avancado"],
        )
    ),
)
def test_todo_perfil_razoavel_gera_plano_valido(dias, equipamento, nivel, quando, minutos, nivel_corrida):
    p = perfil(
        dias_semana=dias,
        equipamento=equipamento,
        nivel=nivel,
        corrida_quando=quando,
        minutos_sessao=minutos,
        nivel_corrida=nivel_corrida,
    )
    plano, _ = gerar_plano_base(p)
    for semana in (1, 9):
        assert validar_plano(plano, p, semana_corrida=semana) == []
    for dia in plano.dias:
        ids = [e.exercicio_id for e in dia.exercicios]
        assert len(ids) == len(set(ids)), dia.nome


# ---------- validador ----------


def plano_de(*dias: DiaPlano) -> PlanoIn:
    porDia = {d.dia: d for d in dias}
    return PlanoIn(dias=[porDia.get(i, DiaPlano(dia=i, nome="Descanso")) for i in range(7)])


def perna(dia: int) -> DiaPlano:
    return DiaPlano(
        dia=dia,
        nome="Inferior",
        exercicios=[
            ExercicioPlano(exercicio_id="agachamento_livre", series=4, reps_min=8, reps_max=10),
            ExercicioPlano(exercicio_id="stiff_barra", series=3, reps_min=8, reps_max=10),
        ],
    )


def corrida(dia: int, tipo="leve", minutos=30) -> DiaPlano:
    return DiaPlano(
        dia=dia, nome="Corrida", corrida=CorridaPlano(tipo=tipo, duracao_min=minutos, esforco_alvo="3-4")
    )


def test_validador_intervalado_depois_de_perna():
    erros = validar_plano(plano_de(perna(0), corrida(1, "intervalado")), perfil())
    assert any("perna" in e for e in erros)
    assert validar_plano(plano_de(perna(0), corrida(1, "leve")), perfil()) == []


def test_validador_volume_de_corrida_sobe_no_maximo_10_por_cento():
    anterior = plano_de(corrida(1, minutos=30), corrida(3, minutos=30), corrida(5, minutos=40))
    mais_15 = plano_de(corrida(1, minutos=35), corrida(3, minutos=35), corrida(5, minutos=45))
    assert any("10%" in e for e in validar_plano(mais_15, perfil(), anterior=anterior))
    mais_10 = plano_de(corrida(1, minutos=33), corrida(3, minutos=33), corrida(5, minutos=44))
    assert validar_plano(mais_10, perfil(), anterior=anterior) == []


def test_validador_exige_descanso():
    plano = PlanoIn(dias=[corrida(i) for i in range(7)])
    assert any("descanso" in e for e in validar_plano(plano, perfil(dias_semana=7)))


def test_validador_dias_acima_do_disponivel():
    plano = plano_de(corrida(0), corrida(2), corrida(4), corrida(6))
    assert any("dias" in e for e in validar_plano(plano, perfil(dias_semana=3)))


def test_validador_duracao_estourada():
    longo = DiaPlano(
        dia=0,
        nome="Longo",
        exercicios=[
            ExercicioPlano(exercicio_id="supino_reto", series=10, reps_min=8, reps_max=10, descanso_s=180)
        ]
        * 3,
    )
    assert any("min" in e for e in validar_plano(plano_de(longo), perfil(minutos_sessao=45)))


def test_validador_exercicio_inexistente_ou_sem_equipamento():
    inventado = DiaPlano(
        dia=0,
        nome="X",
        exercicios=[ExercicioPlano(exercicio_id="voo_do_dragao", series=3, reps_min=8, reps_max=10)],
    )
    assert any("voo_do_dragao" in e for e in validar_plano(plano_de(inventado), perfil()))
    maquina = DiaPlano(
        dia=0,
        nome="X",
        exercicios=[ExercicioPlano(exercicio_id="leg_press", series=3, reps_min=8, reps_max=10)],
    )
    assert any(
        "equipamento" in e for e in validar_plano(plano_de(maquina), perfil(equipamento="peso_corporal"))
    )


def test_validador_longao_grande_demais():
    plano = plano_de(corrida(1, minutos=20), corrida(3, minutos=20), corrida(5, "longao", 60))
    assert any("longão" in e for e in validar_plano(plano, perfil()))


def test_plano_precisa_de_7_dias_distintos():
    with pytest.raises(ValueError):
        PlanoIn(dias=[DiaPlano(dia=0, nome="A")] * 7)


# ---------- achados da revisão ----------


def test_progressao_sem_saltos_grandes():
    corridos = [c * r for c, a, r in PROGRESSAO_INICIANTE]
    assert all(b <= a * 1.5 for a, b in zip(corridos, corridos[1:], strict=False)), corridos


def test_pouco_tempo_tira_a_corrida_e_avisa():
    p = perfil(dias_semana=1, minutos_sessao=30)
    plano, avisos = gerar_plano_base(p)
    assert validar_plano(plano, p) == [] and validar_plano(plano, p, semana_corrida=9) == []
    assert any("corrida" in a for a in avisos)


def test_dia_so_de_corrida_respeita_os_minutos():
    assert any("min" in e for e in validar_plano(plano_de(corrida(1, minutos=60)), perfil(minutos_sessao=30)))


def test_corridas_nao_comem_a_musculacao():
    for p in (
        perfil(dias_semana=4, corrida_quando="dias_separados", corridas_semana=3),
        perfil(dias_semana=7, corridas_semana=7),
    ):
        plano, avisos = gerar_plano_base(p)
        assert len([d for d in plano.dias if d.exercicios]) >= 2
        assert any("corridas" in a for a in avisos)


def test_preferencia_trocada_vira_aviso():
    _, avisos = gerar_plano_base(perfil(dias_semana=4, minutos_sessao=30, corrida_quando="mesmo_dia"))
    assert any("dias separados" in a for a in avisos)


def test_treinos_duros_de_corrida_nao_ficam_em_dias_seguidos():
    plano = plano_de(corrida(3, "intervalado", 30), corrida(4, "longao", 30), corrida(0, minutos=30))
    assert any("seguidos" in e for e in validar_plano(plano, perfil()))


def test_iniciante_em_casa_sem_exercicios_dificeis_demais():
    plano = plano_base(perfil(nivel="iniciante", equipamento="peso_corporal", dias_semana=4))
    ids = {e.exercicio_id for d in plano.dias for e in d.exercicios}
    assert not ids & {"barra_fixa", "flexao_nordica"}


def test_cinco_dias_sem_perna_pesada_em_dias_seguidos():
    from hachibu.treino.validador import perna_pesada

    plano = plano_base(perfil(dias_semana=5, corridas_semana=1))
    pesados = [perna_pesada(d) for d in plano.dias]
    assert not any(a and b for a, b in zip(pesados, pesados[1:] + pesados[:1], strict=True))


def test_validador_exercicio_repetido_no_mesmo_dia():
    dia = DiaPlano(
        dia=0,
        nome="X",
        exercicios=[ExercicioPlano(exercicio_id="supino_reto", series=3, reps_min=8, reps_max=10)] * 2,
    )
    assert any("repetido" in e for e in validar_plano(plano_de(dia), perfil()))
