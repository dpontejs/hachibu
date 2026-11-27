"""O que muda entre duas versões do plano, em frases curtas: é o que o aluno lê no card de aprovação."""

from hachibu.treino.exercicios import por_id
from hachibu.treino.modelos import CorridaPlano, DiaPlano, ExercicioPlano, PlanoIn
from hachibu.treino.validador import DIAS


def _nome(exercicio_id: str) -> str:
    ex = por_id(exercicio_id)
    return ex.nome if ex else exercicio_id


def _prescricao(e: ExercicioPlano) -> str:
    return f"{e.series}×{e.reps_min}–{e.reps_max}"


def _corrida(c: CorridaPlano | None) -> str:
    if c is None:
        return "sem corrida"
    if c.progressao:
        return "corrida e caminhada (progressão de iniciante)"
    if c.tipo == "recuperacao":
        return f"recuperação {c.duracao_min} min"
    return f"{c.tipo.replace('longao', 'longão')} {c.duracao_min} min"


def _resumo(dia: DiaPlano) -> str:
    partes = [_nome(e.exercicio_id) + f" {_prescricao(e)}" for e in dia.exercicios]
    if dia.corrida:
        partes.append(_corrida(dia.corrida))
    return f"{DIAS[dia.dia]}: {dia.nome}" + (f" ({'; '.join(partes)})" if partes else "")


def _dia(antes: DiaPlano, depois: DiaPlano) -> list[str]:
    linhas: list[str] = []
    prefixo = f"{DIAS[depois.dia]}:"
    if antes.nome != depois.nome:
        linhas.append(f"{prefixo} {antes.nome} → {depois.nome}")
    # Exercícios pela posição: trocar o 1º por outro é "troca", não "sai e entra".
    for i in range(max(len(antes.exercicios), len(depois.exercicios))):
        a = antes.exercicios[i] if i < len(antes.exercicios) else None
        d = depois.exercicios[i] if i < len(depois.exercicios) else None
        if a and d and a.exercicio_id != d.exercicio_id:
            linhas.append(f"{prefixo} {_nome(a.exercicio_id)} → {_nome(d.exercicio_id)} ({_prescricao(d)})")
        elif (
            a
            and d
            and (a.series, a.reps_min, a.reps_max, a.descanso_s)
            != (
                d.series,
                d.reps_min,
                d.reps_max,
                d.descanso_s,
            )
        ):
            linhas.append(
                f"{prefixo} {_nome(d.exercicio_id)}: séries {_prescricao(a)} → {_prescricao(d)}"
                + (f", descanso {a.descanso_s} → {d.descanso_s} s" if a.descanso_s != d.descanso_s else "")
            )
        elif a and not d:
            linhas.append(f"{prefixo} sai {_nome(a.exercicio_id)}")
        elif d and not a:
            linhas.append(f"{prefixo} entra {_nome(d.exercicio_id)} ({_prescricao(d)})")
    if antes.corrida != depois.corrida:
        linhas.append(f"{prefixo} {_corrida(antes.corrida)} → {_corrida(depois.corrida)}")
    return linhas


def diferencas(anterior: PlanoIn | None, novo: PlanoIn) -> list[str]:
    """Sem plano anterior, o resumo de cada dia; com anterior, só o que mudou (vazio = nada mudou)."""
    if anterior is None:
        return [_resumo(d) for d in novo.dias]
    return [linha for a, d in zip(anterior.dias, novo.dias, strict=True) for linha in _dia(a, d)]
