"""Plano base a partir do perfil, sem LLM: o ponto de partida que o coach ajusta depois.

Divisão pelos dias, séries pelo nível, exercícios pelo equipamento, corrida pelas preferências. A musculação
encolhe (acessórios saem primeiro) para caber nos minutos da sessão junto com a corrida do mesmo dia.
"""

from hachibu.metas import PerfilIn
from hachibu.treino.modelos import CorridaPlano, DiaPlano, ExercicioPlano, PlanoIn
from hachibu.treino.progressao import DURACAO_MAXIMA, corrida_da_semana
from hachibu.treino.validador import SEGUNDOS_POR_SERIE, perna_pesada

# Um slot = o mesmo papel no treino em cada equipamento (academia, casa_halteres, peso_corporal).
Slot = tuple[str | None, str | None, str | None]
EQUIP = {"academia": 0, "casa_halteres": 1, "peso_corporal": 2}

QUAD_A: Slot = ("agachamento_livre", "agachamento_goblet", "agachamento_corporal")
QUAD_B: Slot = ("leg_press", "bulgaro_halteres", "bulgaro")
QUAD_ISO: Slot = ("cadeira_extensora", "afundo_halteres", "afundo")
AFUNDO: Slot = ("afundo_halteres", "afundo_halteres", "afundo")
PEITO_A: Slot = ("supino_reto", "supino_halteres", "flexao")
PEITO_B: Slot = ("supino_inclinado_halteres", "supino_inclinado_halteres", "flexao_declinada")
COSTAS_H: Slot = ("remada_curvada", "remada_unilateral", "remada_invertida")
COSTAS_H2: Slot = ("remada_baixa", "remada_unilateral", "remada_invertida")
COSTAS_V: Slot = ("puxada_frente", "pullover_halter", "barra_fixa")
POST_A: Slot = ("stiff_barra", "stiff_halteres", "stiff_unilateral")
POST_B: Slot = ("levantamento_terra", "stiff_halteres", "flexao_nordica")
POST_ISO: Slot = ("mesa_flexora", "flexao_nordica", "flexao_nordica")
GLUTEO: Slot = ("elevacao_quadril_barra", "elevacao_quadril_halter", "ponte_gluteo")
OMBRO: Slot = ("desenvolvimento_barra", "desenvolvimento_halteres", "flexao_pike")
OMBRO_LAT: Slot = ("elevacao_lateral", "elevacao_lateral", "flexao_pike")
BICEPS: Slot = ("rosca_direta", "rosca_halteres", None)
BICEPS2: Slot = ("rosca_martelo", "rosca_martelo", None)
TRICEPS: Slot = ("triceps_corda", "triceps_testa", "mergulho_banco")
TRICEPS2: Slot = ("triceps_frances", "triceps_frances", "flexao_diamante")
PANTURRILHA: Slot = ("panturrilha_em_pe", "panturrilha_halter", "panturrilha_degrau")
CORE: Slot = ("prancha", "prancha", "prancha")
CORE2: Slot = ("abdominal_polia", "abdominal_infra", "dead_bug")

# Os 4 primeiros de cada treino são compostos; os 2 últimos, acessórios (saem primeiro se faltar tempo).
TREINOS: dict[str, list[Slot]] = {
    "Corpo inteiro A": [QUAD_A, PEITO_A, COSTAS_H, POST_A, OMBRO, CORE],
    "Corpo inteiro B": [QUAD_B, COSTAS_V, PEITO_B, GLUTEO, OMBRO_LAT, TRICEPS],
    "Superior A": [PEITO_A, COSTAS_H, OMBRO, COSTAS_V, BICEPS, TRICEPS],
    "Superior B": [PEITO_B, COSTAS_H2, OMBRO_LAT, COSTAS_V, BICEPS2, TRICEPS2],
    "Inferior A": [QUAD_A, POST_A, QUAD_ISO, POST_ISO, PANTURRILHA, CORE],
    "Inferior B": [QUAD_B, POST_B, AFUNDO, GLUTEO, PANTURRILHA, CORE2],
}
DIVISAO = {
    1: ["Corpo inteiro A"],
    2: ["Corpo inteiro A", "Corpo inteiro B"],
    3: ["Corpo inteiro A", "Corpo inteiro B", "Corpo inteiro A"],
    4: ["Superior A", "Inferior A", "Superior B", "Inferior B"],
    5: ["Superior A", "Inferior A", "Superior B", "Inferior B", "Corpo inteiro A"],
}
# Dias da semana usados (0 = segunda), espalhando o descanso. Sempre sobra ao menos o domingo.
POSICOES = {
    1: [0],
    2: [0, 3],
    3: [0, 2, 4],
    4: [0, 1, 3, 4],
    5: [0, 1, 2, 4, 5],
    6: [0, 1, 2, 3, 4, 5],
}
# (séries, reps mín, reps máx, descanso) dos compostos; acessórios: uma série a menos, 10–15, 60 s.
NIVEL = {"iniciante": (3, 10, 15, 75), "intermediario": (3, 8, 12, 90), "avancado": (4, 6, 10, 120)}
MIN_MUSCULACAO_S = 600
LEVE = {"intermediario": 30, "avancado": 40}
LONGAO = {"intermediario": 40, "avancado": 50}


def _exercicios(nome: str, perfil: PerfilIn, alvo_s: float) -> list[ExercicioPlano]:
    series, rmin, rmax, descanso = NIVEL[perfil.nivel]
    lista: list[ExercicioPlano] = []
    for i, slot in enumerate(TREINOS[nome]):
        ex_id = slot[EQUIP[perfil.equipamento]]
        if ex_id is None:
            continue
        if i < 4:
            lista.append(
                ExercicioPlano(
                    exercicio_id=ex_id, series=series, reps_min=rmin, reps_max=rmax, descanso_s=descanso
                )
            )
        else:
            lista.append(
                ExercicioPlano(
                    exercicio_id=ex_id, series=max(series - 1, 2), reps_min=10, reps_max=15, descanso_s=60
                )
            )

    def segundos() -> float:
        return sum(e.series * (SEGUNDOS_POR_SERIE + e.descanso_s) for e in lista)

    while segundos() > alvo_s and len(lista) > 3:
        lista.pop()
    while segundos() > alvo_s:
        reduzivel = [e for e in lista if e.series > 2]
        if not reduzivel:
            break
        reduzivel[-1].series -= 1
    return lista


def _modo(perfil: PerfilIn, dias: int) -> str:
    quando = perfil.corrida_quando or "automatico"
    if quando == "automatico":
        quando = "dias_separados" if dias >= 5 else "mesmo_dia"
    if quando == "dias_separados" and dias < 2:
        return "mesmo_dia"
    return quando


def _corrida(nivel_corrida: str, tipo: str, maximo_min: int | None = None) -> CorridaPlano:
    if nivel_corrida == "iniciante":
        return corrida_da_semana(1)
    if maximo_min is not None:
        # No mesmo dia da musculação, a leve encurta para caber (mínimo de 15 min).
        return CorridaPlano(
            tipo="leve", duracao_min=max(15, min(LEVE[nivel_corrida], maximo_min)), esforco_alvo="3-4"
        )
    if tipo == "longao":
        return CorridaPlano(tipo="longao", duracao_min=LONGAO[nivel_corrida], esforco_alvo="3-4")
    if tipo == "intervalado":
        return CorridaPlano(tipo="intervalado", duracao_min=LEVE[nivel_corrida], esforco_alvo="8-9")
    return CorridaPlano(tipo="leve", duracao_min=LEVE[nivel_corrida], esforco_alvo="3-4")


def _tipos_de_corrida(nivel_corrida: str, quantas: int, mesmo_dia: bool) -> list[str]:
    """Leves, depois intervalado e longão por último (no mesmo dia da musculação, só leves)."""
    if nivel_corrida == "iniciante" or mesmo_dia or quantas < 3:
        return ["leve"] * quantas
    if nivel_corrida == "avancado":
        return ["leve"] * (quantas - 2) + ["intervalado", "longao"]
    return ["leve"] * (quantas - 1) + ["longao"]


def _proteger_dia_seguinte_a_perna(dias: list[DiaPlano], nivel_corrida: str) -> None:
    """Intervalado e longão vão para um dia que não venha depois de perna pesada; sem lugar, viram leves."""
    for tipo in ("longao", "intervalado"):
        for dia in dias:
            if not (dia.corrida and dia.corrida.tipo == tipo and perna_pesada(dias[(dia.dia - 1) % 7])):
                continue
            livre = next(
                (
                    d
                    for d in dias
                    if d.corrida
                    and d.corrida.tipo == "leve"
                    and not d.exercicios
                    and not perna_pesada(dias[(d.dia - 1) % 7])
                ),
                None,
            )
            if livre is not None:
                livre.corrida, dia.corrida = dia.corrida, livre.corrida
            else:
                dia.corrida = _corrida(nivel_corrida, "leve")


def plano_base(perfil: PerfilIn) -> PlanoIn:
    dias_livres = min(perfil.dias_semana, 6)
    nivel_corrida = perfil.nivel_corrida or "iniciante"
    pedidas = perfil.corridas_semana or 3
    modo = _modo(perfil, dias_livres)
    duracao_corrida = DURACAO_MAXIMA if nivel_corrida == "iniciante" else LEVE[nivel_corrida]
    # No mesmo dia, a corrida e um mínimo de musculação precisam caber; senão, separa (se houver dias).
    if (
        modo == "mesmo_dia"
        and perfil.minutos_sessao * 60 - duracao_corrida * 60 < MIN_MUSCULACAO_S
        and dias_livres >= 2
    ):
        modo = "dias_separados"

    if modo == "mesmo_dia":
        n_musc = min(dias_livres, 5)
        n_corrida = min(pedidas, n_musc)
        posicoes = POSICOES[n_musc]
        tipos_dia = ["M"] * n_musc
    else:
        n_corrida = min(pedidas, dias_livres - 1)
        n_musc = min(dias_livres - n_corrida, 5)
        posicoes = POSICOES[n_musc + n_corrida]
        # Alterna começando pela corrida: a de segunda vem depois do descanso de domingo.
        tipos_dia, c, m = [], n_corrida, n_musc
        while c or m:
            if c and (not tipos_dia or tipos_dia[-1] == "M" or not m):
                tipos_dia.append("C")
                c -= 1
            else:
                tipos_dia.append("M")
                m -= 1

    dias = [DiaPlano(dia=i, nome="Descanso") for i in range(7)]
    nomes = iter(DIVISAO[n_musc]) if n_musc else iter(())
    musc_dias = [p for p, t in zip(posicoes, tipos_dia, strict=True) if t == "M"]
    if modo == "mesmo_dia":
        # Corridas espalhadas entre os dias de musculação.
        com_corrida = (
            {musc_dias[round(i * n_musc / n_corrida)] for i in range(n_corrida)} if n_corrida else set()
        )
    else:
        com_corrida = {p for p, t in zip(posicoes, tipos_dia, strict=True) if t == "C"}
    tipos = iter(_tipos_de_corrida(nivel_corrida, n_corrida, modo == "mesmo_dia"))
    for p in posicoes:
        dia = dias[p]
        maximo = perfil.minutos_sessao - MIN_MUSCULACAO_S // 60 - 5 if p in musc_dias else None
        corrida = _corrida(nivel_corrida, next(tipos), maximo) if p in com_corrida else None
        if p in musc_dias:
            dia.nome = next(nomes)
            reservado = (
                (DURACAO_MAXIMA if corrida and corrida.progressao else corrida.duracao_min) if corrida else 0
            )
            dia.exercicios = _exercicios(dia.nome, perfil, perfil.minutos_sessao * 60 - reservado * 60)
        else:
            dia.nome = "Corrida"
        dia.corrida = corrida
    _proteger_dia_seguinte_a_perna(dias, nivel_corrida)
    return PlanoIn(dias=dias)
