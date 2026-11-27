"""Progressão de corrida e caminhada para quem está começando (tabela própria, por tempo e esforço).

Cada sessão tem 5 min de caminhada de aquecimento e blocos de corrida e caminhada. Os blocos de corrida
crescem até 30 min contínuos na semana 9.
"""

from hachibu.treino.modelos import CorridaPlano

AQUECIMENTO_MIN = 5
# (corre_min, anda_min, repetições)
PROGRESSAO_INICIANTE: list[tuple[float, float, int]] = [
    (1, 2, 7),
    (2, 2, 6),
    (3, 2, 5),
    (5, 2, 4),
    (8, 2, 3),
    (12, 2, 2),
    (18, 0, 1),
    (24, 0, 1),
    (30, 0, 1),
]
DURACAO_MAXIMA = max(AQUECIMENTO_MIN + (c + a) * r for c, a, r in PROGRESSAO_INICIANTE)


def corrida_da_semana(semana: int) -> CorridaPlano:
    semana = min(max(semana, 1), len(PROGRESSAO_INICIANTE))
    corre, anda, repeticoes = PROGRESSAO_INICIANTE[semana - 1]
    return CorridaPlano(
        progressao=True,
        tipo="corrida_caminhada",
        duracao_min=round(AQUECIMENTO_MIN + (corre + anda) * repeticoes),
        corre_min=corre,
        anda_min=anda,
        repeticoes=repeticoes,
        esforco_alvo="3-5",
    )
