"""Plano base a partir do perfil, sem LLM: o ponto de partida que o coach ajusta depois.

É o **rascunho** que o coach usa na conversa (o aluno nunca recebe um plano gerado em silêncio):
divisão pelos dias, séries pelo nível, exercícios pelo equipamento, corrida pelas preferências.
A musculação cabe nos minutos de musculação e a corrida nos de corrida (um não desconta do outro).
O que não pôde seguir a preferência do aluno vira um ponto para o coach conversar.
"""

from hachibu.metas import PerfilIn
from hachibu.treino.modelos import CorridaPlano, DiaPlano, ExercicioPlano, PlanoIn
from hachibu.treino.progressao import DURACAO_MAXIMA, corrida_da_semana
from hachibu.treino.validador import DIAS as DIAS_NOMES
from hachibu.treino.validador import SEGUNDOS_POR_SERIE, TOLERANCIA_DURACAO, perna_pesada

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
POST_B: Slot = ("levantamento_terra", "stiff_halteres", "stiff_unilateral")
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
    5: ["Superior A", "Inferior A", "Superior B", "Inferior B", "Superior A"],
    6: ["Superior A", "Inferior A", "Superior B", "Inferior B", "Superior A", "Inferior A"],
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
RECUPERACAO_MIN = 30
# Iniciante treinando em casa: barra fixa e flexão nórdica são difíceis demais para começar.
TROCA_INICIANTE = {"barra_fixa": "superman", "flexao_nordica": "ponte_gluteo"}
LEVE = {"intermediario": 30, "avancado": 40}
LONGAO = {"intermediario": 40, "avancado": 50}


def _exercicios(nome: str, perfil: PerfilIn, alvo_s: float) -> list[ExercicioPlano]:
    series, rmin, rmax, descanso = NIVEL[perfil.nivel]
    lista: list[ExercicioPlano] = []
    for i, slot in enumerate(TREINOS[nome]):
        ex_id = slot[EQUIP[perfil.equipamento]]
        if perfil.nivel == "iniciante" and ex_id in TROCA_INICIANTE:
            ex_id = TROCA_INICIANTE[ex_id]
        if ex_id is None or any(e.exercicio_id == ex_id for e in lista):
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


def _corrida(nivel_corrida: str, tipo: str, maximo_min: int) -> CorridaPlano:
    """Corrida do tipo pedido, com no máximo `maximo_min` (o tempo que cabe na sessão)."""
    if nivel_corrida == "iniciante":
        return corrida_da_semana(1)
    padrao = {"longao": LONGAO, "intervalado": LEVE, "leve": LEVE}[tipo][nivel_corrida]
    esforco = {"longao": "3-4", "intervalado": "8-9", "leve": "3-4"}[tipo]
    return CorridaPlano(tipo=tipo, duracao_min=max(15, min(padrao, maximo_min)), esforco_alvo=esforco)


def _tipos_de_corrida(nivel_corrida: str, quantas: int, mesmo_dia: bool) -> list[str]:
    """Leves, depois intervalado e longão por último (no mesmo dia da musculação, só leves)."""
    if nivel_corrida == "iniciante" or mesmo_dia or quantas < 3:
        return ["leve"] * quantas
    if nivel_corrida == "avancado":
        return ["leve"] * (quantas - 2) + ["intervalado", "longao"]
    return ["leve"] * (quantas - 1) + ["longao"]


def _duro(dia: DiaPlano | None) -> bool:
    return bool(dia and dia.corrida and dia.corrida.tipo in ("intervalado", "longao"))


def _proteger_treinos_duros(dias: list[DiaPlano], nivel_corrida: str, maximo_min: int) -> None:
    """Intervalado e longão: nunca depois de perna pesada nem em dias seguidos. Sem lugar, viram leves."""

    def ruim(i: int) -> bool:
        return perna_pesada(dias[(i - 1) % 7]) or _duro(dias[(i - 1) % 7]) or _duro(dias[(i + 1) % 7])

    for tipo in ("longao", "intervalado"):
        for dia in dias:
            if not (dia.corrida and dia.corrida.tipo == tipo and ruim(dia.dia)):
                continue
            original, dia.corrida = dia.corrida, _corrida(nivel_corrida, "leve", maximo_min)
            livre = next(
                (
                    d
                    for d in dias
                    if d is not dia
                    and d.corrida
                    and d.corrida.tipo == "leve"
                    and not d.exercicios
                    and not ruim(d.dia)
                ),
                None,
            )
            if livre is not None:
                livre.corrida, dia.corrida = original, livre.corrida


def gerar_plano_base(perfil: PerfilIn) -> tuple[PlanoIn, list[str]]:
    """Rascunho do plano e os pontos em que ele não seguiu a preferência do aluno (para o coach perguntar)."""
    pontos: list[str] = []
    dias_treino = min(perfil.dias_semana, 6)
    nivel_corrida = perfil.nivel_corrida or "iniciante"
    pedidas = perfil.corridas_semana or 3
    quando = perfil.corrida_quando or "automatico"
    modo = _modo(perfil, dias_treino)
    if quando == "dias_separados" and modo == "mesmo_dia":
        pontos.append("Com 1 dia de treino, a corrida ficou no mesmo dia da musculação.")
    limite = perfil.minutos_corrida * TOLERANCIA_DURACAO if perfil.minutos_corrida else None
    minimo = DURACAO_MAXIMA if nivel_corrida == "iniciante" else 15
    if limite is not None and minimo > limite:
        pedidas = 0
        pontos.append(
            f"A corrida ficou de fora: com {perfil.minutos_corrida} min de corrida não cabe a sessão "
            f"(a de iniciante chega a {DURACAO_MAXIMA} min). Vale aumentar o tempo de corrida?"
        )
    maximo_corrida = int(limite) if limite is not None else 240
    if nivel_corrida == "iniciante" and pedidas > 3:
        pontos.append(
            f"Você pediu {pedidas} corridas, mas a progressão de iniciante é de 3 corridas por semana. "
            "Nos outros dias, quer uma recuperação (caminhada leve) ou só a musculação?"
        )
        pedidas = 3

    if modo == "mesmo_dia":
        n_musc = dias_treino
        n_corrida = min(pedidas, n_musc)
        posicoes = POSICOES[n_musc]
        tipos_dia = ["M"] * n_musc
        if n_corrida < pedidas:
            pontos.append(
                f"Você pediu {pedidas} corridas depois da musculação, mas são {n_musc} dias de musculação: "
                f"ficaram {n_corrida}. Quer correr em algum dia sem musculação?"
            )
    else:
        # Sobra musculação: pelo menos 2 dias quando há 4 ou mais, senão 1.
        reserva = 2 if dias_treino >= 4 else 1
        n_corrida = min(pedidas, dias_treino - reserva)
        n_musc = min(dias_treino - n_corrida, 6)
        posicoes = POSICOES[n_musc + n_corrida]
        if n_corrida < pedidas:
            pontos.append(
                f"Você pediu {pedidas} corridas em dias separados; "
                f"ficaram {n_corrida} para sobrar musculação. "
                "Prefere correr depois da musculação em alguns dias?"
            )
        # Alterna começando pela corrida: a de segunda vem depois do descanso de domingo.
        tipos_dia, c, mm = [], n_corrida, n_musc
        while c or mm:
            if c and (not tipos_dia or tipos_dia[-1] == "M" or not mm):
                tipos_dia.append("C")
                c -= 1
            else:
                tipos_dia.append("M")
                mm -= 1

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
        dia.corrida = _corrida(nivel_corrida, next(tipos), maximo_corrida) if p in com_corrida else None
        if p in musc_dias:
            dia.nome = next(nomes)
            dia.exercicios = _exercicios(dia.nome, perfil, perfil.minutos_sessao * 60)
        else:
            dia.nome = "Corrida"
    # 7 dias marcados: o dia livre vira recuperação, e o coach pergunta se o aluno prefere descanso total.
    if perfil.dias_semana == 7:
        livre = next(d for d in dias if not d.exercicios and not d.corrida)
        livre.nome = "Recuperação"
        livre.corrida = CorridaPlano(tipo="recuperacao", duracao_min=RECUPERACAO_MIN, esforco_alvo="1-3")
        pontos.append(
            f"Você marcou 7 dias: deixei {DIAS_NOMES[livre.dia]} como recuperação (caminhada leve ou "
            "mobilidade). Prefere descanso total nesse dia?"
        )
    _proteger_treinos_duros(dias, nivel_corrida, maximo_corrida)
    return PlanoIn(dias=dias), pontos


def plano_base(perfil: PerfilIn) -> PlanoIn:
    return gerar_plano_base(perfil)[0]
