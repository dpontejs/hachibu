"""O que muda entre duas versões do plano, em frases curtas: é o que o aluno lê no card de aprovação."""

from hachibu.treino.exercicios import por_id
from hachibu.treino.modelos import CardioPlano, CorridaPlano, DiaPlano, ExercicioPlano, PlanoIn
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
    return f"{c.tipo.replace('longao', 'longão')} {c.duracao_min} min"


def _corrida_legivel(c: CorridaPlano) -> str:
    if c.progressao:
        return "Corrida e caminhada · progressão de iniciante"
    nomes = {
        "leve": "Corrida leve",
        "intervalado": "Intervalado",
        "longao": "Longão",
    }
    texto = f"{nomes.get(c.tipo, 'Corrida')} · {c.duracao_min} min"
    return texto


MODALIDADES = {
    "bicicleta": "Bicicleta",
    "eliptico": "Elíptico",
    "caminhada": "Caminhada",
    "escada": "Escada",
    "remo": "Remo",
}


def cardio_legivel(c: CardioPlano | None) -> str:
    if c is None:
        return "sem cardio"
    return f"{MODALIDADES[c.modalidade]} {c.intensidade} · {c.duracao_min} min"


def resumo_semana(plano: PlanoIn) -> list[dict]:
    """A semana em estrutura para o card: dia, nome do treino, um exercício por item e a corrida."""
    return [
        {
            "dia": DIAS[d.dia],
            "nome": d.nome,
            "itens": [
                f"{_nome(e.exercicio_id)} · {e.series} × {e.reps_min}–{e.reps_max}" for e in d.exercicios
            ],
            "corrida": _corrida_legivel(d.corrida) if d.corrida else None,
            "cardio": cardio_legivel(d.cardio) if d.cardio else None,
        }
        for d in plano.dias
    ]


def _mesma_corrida(a: CorridaPlano | None, b: CorridaPlano | None) -> bool:
    """Compara o que importa: na progressão só a marcação; fora dela tipo, duração, esforço e blocos."""
    if a is None or b is None:
        return a is b
    if a.progressao or b.progressao:
        return a.progressao == b.progressao
    campos = ("tipo", "duracao_min", "esforco_alvo", "corre_min", "anda_min", "repeticoes")
    return all(getattr(a, c) == getattr(b, c) for c in campos)


def _mesmo_dia(a: DiaPlano, b: DiaPlano) -> bool:
    return (
        a.nome == b.nome
        and a.exercicios == b.exercicios
        and _mesma_corrida(a.corrida, b.corrida)
        and a.cardio == b.cardio
    )


def _dia(antes: DiaPlano, depois: DiaPlano) -> list[str]:
    linhas: list[str] = []
    prefixo = f"{DIAS[depois.dia]}:"
    if antes.nome != depois.nome:
        linhas.append(f"{prefixo} {antes.nome} → {depois.nome}")
    # Casa pelo exercício (não pela posição): tirar um da lista não vira uma cascata de trocas falsas.
    ids_antes = [e.exercicio_id for e in antes.exercicios]
    ids_depois = [e.exercicio_id for e in depois.exercicios]
    for d in depois.exercicios:
        if d.exercicio_id in ids_antes:
            a = antes.exercicios[ids_antes.index(d.exercicio_id)]
            if (a.series, a.reps_min, a.reps_max, a.descanso_s) != (
                d.series,
                d.reps_min,
                d.reps_max,
                d.descanso_s,
            ):
                linhas.append(
                    f"{prefixo} {_nome(d.exercicio_id)}: séries {_prescricao(a)} → {_prescricao(d)}"
                    + (
                        f", descanso {a.descanso_s} → {d.descanso_s} s"
                        if a.descanso_s != d.descanso_s
                        else ""
                    )
                )
    saiu = [e for e in antes.exercicios if e.exercicio_id not in ids_depois]
    entrou = [e for e in depois.exercicios if e.exercicio_id not in ids_antes]
    if len(saiu) == len(entrou):
        for a, d in zip(saiu, entrou, strict=True):
            linhas.append(f"{prefixo} {_nome(a.exercicio_id)} → {_nome(d.exercicio_id)} ({_prescricao(d)})")
    else:
        linhas += [f"{prefixo} sai {_nome(a.exercicio_id)}" for a in saiu]
        linhas += [f"{prefixo} entra {_nome(d.exercicio_id)} ({_prescricao(d)})" for d in entrou]
    if not _mesma_corrida(antes.corrida, depois.corrida):
        linhas.append(f"{prefixo} {_corrida(antes.corrida)} → {_corrida(depois.corrida)}")
    if antes.cardio != depois.cardio:
        linhas.append(f"{prefixo} {cardio_legivel(antes.cardio)} → {cardio_legivel(depois.cardio)}")
    return linhas


def diferencas(anterior: PlanoIn | None, novo: PlanoIn) -> list[str]:
    """O que mudou em relação ao plano anterior (vazio = nada mudou). Sem anterior não há "antes": vazio, e o
    card mostra a semana (`resumo_semana`)."""
    if anterior is None:
        return []
    linhas: list[str] = []
    for a, d in zip(anterior.dias, novo.dias, strict=True):
        if _mesmo_dia(a, d):
            continue
        # Dia inteiro trazido de outro dia da semana: uma linha, não a lista de diferenças.
        origem = next((o for o in anterior.dias if o.dia != d.dia and _mesmo_dia(o, d)), None)
        if origem is not None:
            linhas.append(f"{DIAS[d.dia]}: agora é o treino de {DIAS[origem.dia]} ({d.nome})")
        else:
            linhas += _dia(a, d)
    return linhas
