"""Regras do plano em código: o que o plano base gera e o que o coach propõe passa por aqui.

Devolve a lista de problemas em português (vazia = plano válido), para o modelo ler e corrigir.
"""

from collections import Counter

from hachibu.metas import PerfilIn
from hachibu.treino.exercicios import PERNAS, por_id
from hachibu.treino.modelos import CorridaPlano, DiaPlano, PlanoIn
from hachibu.treino.progressao import corrida_da_semana

SEGUNDOS_POR_SERIE = 40
TOLERANCIA_DURACAO = 1.15
SERIES_PERNA_PESADA = 6
MAX_SERIES_GRUPO = 25
AUMENTO_MAXIMO_CORRIDA = 1.10
LONGAO_MAXIMO = 0.40
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def corrida_efetiva(corrida: CorridaPlano | None, semana_corrida: int) -> CorridaPlano | None:
    """A corrida de progressão vale como o treino da semana atual da tabela."""
    if corrida is not None and corrida.progressao:
        return corrida_da_semana(semana_corrida)
    return corrida


def minutos_musculacao(dia: DiaPlano) -> float:
    return sum(e.series * (SEGUNDOS_POR_SERIE + e.descanso_s) for e in dia.exercicios) / 60


def series_de_perna(dia: DiaPlano) -> int:
    total = 0
    for e in dia.exercicios:
        ex = por_id(e.exercicio_id)
        if ex is not None and ex.grupo in PERNAS:
            total += e.series
    return total


def perna_pesada(dia: DiaPlano) -> bool:
    return series_de_perna(dia) >= SERIES_PERNA_PESADA


def volume_corrida(plano: PlanoIn, semana_corrida: int) -> int:
    return sum(c.duracao_min for d in plano.dias if (c := corrida_efetiva(d.corrida, semana_corrida)))


def validar_plano(
    plano: PlanoIn, perfil: PerfilIn, anterior: PlanoIn | None = None, semana_corrida: int = 1
) -> list[str]:
    erros: list[str] = []
    # 1. exercícios do catálogo e do equipamento do aluno
    for dia in plano.dias:
        for e in dia.exercicios:
            ex = por_id(e.exercicio_id)
            if ex is None:
                erros.append(f"{DIAS[dia.dia]}: o exercício '{e.exercicio_id}' não existe no catálogo.")
            elif perfil.equipamento not in ex.equipamentos:
                erros.append(
                    f"{DIAS[dia.dia]}: {ex.nome} precisa de outro equipamento "
                    f"(o aluno tem {perfil.equipamento})."
                )
    # 2. descanso e dias disponíveis
    treino = [d for d in plano.dias if d.exercicios or d.corrida]
    if len(treino) == 7:
        erros.append("o plano precisa de pelo menos 1 dia de descanso total.")
    if len(treino) > perfil.dias_semana:
        erros.append(
            f"o plano usa {len(treino)} dias, mas o aluno tem {perfil.dias_semana} dias disponíveis."
        )
    # 3. duração de cada dia (musculação + corrida no mesmo dia)
    limite = perfil.minutos_sessao * TOLERANCIA_DURACAO
    for dia in plano.dias:
        corrida = corrida_efetiva(dia.corrida, semana_corrida)
        total = minutos_musculacao(dia) + (corrida.duracao_min if corrida and dia.exercicios else 0)
        if dia.exercicios and total > limite:
            erros.append(
                f"{DIAS[dia.dia]}: cerca de {total:.0f} min, "
                f"acima dos {perfil.minutos_sessao} min por sessão."
            )
    # 4. nada de intervalado ou longão no dia seguinte a perna pesada
    for dia in plano.dias:
        corrida = corrida_efetiva(dia.corrida, semana_corrida)
        anterior_dia = plano.dias[(dia.dia - 1) % 7]
        if corrida and corrida.tipo in ("intervalado", "longao") and perna_pesada(anterior_dia):
            erros.append(f"{DIAS[dia.dia]}: {corrida.tipo} no dia seguinte a um treino pesado de perna.")
    # 5. volume de corrida sobe no máximo 10% sobre a versão anterior
    volume = volume_corrida(plano, semana_corrida)
    if anterior is not None:
        antes = volume_corrida(anterior, semana_corrida)
        if antes and volume > antes * AUMENTO_MAXIMO_CORRIDA:
            erros.append(f"o volume de corrida sobe de {antes} para {volume} min: mais que 10% numa semana.")
    # 6. longão com no máximo 40% do volume semanal
    for dia in plano.dias:
        corrida = corrida_efetiva(dia.corrida, semana_corrida)
        if corrida and corrida.tipo == "longao" and volume and corrida.duracao_min > volume * LONGAO_MAXIMO:
            erros.append(f"{DIAS[dia.dia]}: o longão passa de 40% do volume semanal de corrida.")
    # 7. séries por grupo muscular na semana
    por_grupo: Counter[str] = Counter()
    for dia in plano.dias:
        for e in dia.exercicios:
            if ex := por_id(e.exercicio_id):
                por_grupo[ex.grupo] += e.series
    for grupo, series in por_grupo.items():
        if series > MAX_SERIES_GRUPO:
            erros.append(f"{grupo}: {series} séries na semana, acima de {MAX_SERIES_GRUPO}.")
    return erros
