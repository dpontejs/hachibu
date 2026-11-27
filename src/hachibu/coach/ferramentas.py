"""O que o coach pode fazer no estado do aluno: funções puras (db, user_id, ...).

Não sabem nada de LLM. Quem chama (tools do agente, um futuro MCP externo) decide de onde vêm db e user_id;
o modelo nunca escolhe o usuário. Erro de uso vira ErroFerramenta com mensagem em português para o modelo ler.
"""

from datetime import datetime

from hachibu.alimentos import buscar_alimentos
from hachibu.diario import (
    MACROS,
    AlimentoInexistente,
    gravar_agua,
    gravar_refeicao,
    hoje,
    itens_da_taco,
    resumo_do_dia,
)
from hachibu.metas import PISO_KCAL, Metas, calcular_metas, diagnostico, gasto_diario
from hachibu.perfil import ler_perfil as _ler_perfil

FUSO = "America/Sao_Paulo"
DEFICIT_MAXIMO = 0.25


class ErroFerramenta(Exception):
    """Erro que o modelo deve ler e corrigir (argumento inválido, dado faltando)."""


def _perfil(db, user_id: int):
    perfil = _ler_perfil(db, user_id)
    if perfil is None:
        raise ErroFerramenta("O aluno ainda não preencheu o perfil. Peça para preencher a tela Perfil.")
    return perfil


def ler_perfil(db, user_id: int) -> dict:
    return _perfil(db, user_id).model_dump()


def ler_diagnostico(db, user_id: int) -> dict:
    return diagnostico(_perfil(db, user_id)).model_dump()


def saldo_do_dia(db, user_id: int, agora: datetime) -> dict:
    resumo = resumo_do_dia(db, user_id, hoje(FUSO, agora).isoformat())
    if resumo is None:
        raise ErroFerramenta("O aluno ainda não preencheu o perfil. Peça para preencher a tela Perfil.")
    resumo["faltam"] = {m: round(max(resumo["metas"][m] - resumo["consumido"][m], 0), 1) for m in MACROS}
    return resumo


def buscar_alimento_taco(db, user_id: int, termo: str) -> list[dict]:
    if len(termo.strip()) < 2:
        raise ErroFerramenta("Use pelo menos 2 letras na busca.")
    return buscar_alimentos(db, termo, limite=8)


def registrar_refeicao(db, user_id: int, nome: str, itens: list[dict], agora: datetime) -> dict:
    if not nome.strip() or not itens or len(itens) > 30:
        raise ErroFerramenta("Informe um nome e de 1 a 30 itens (alimento_id da TACO e gramas).")
    pares = []
    for item in itens:
        gramas = float(item.get("gramas", 0))
        if not 0 < gramas <= 2000:
            raise ErroFerramenta(f"Gramas inválidas no item {item}: use de 1 a 2000.")
        pares.append((int(item["alimento_id"]), gramas))
    try:
        calculados = itens_da_taco(db, pares)
    except AlimentoInexistente as e:
        raise ErroFerramenta(
            f"O alimento_id {e.alimento_id} não existe. Use buscar_alimento_taco para achar o id certo."
        ) from None
    totais = {m: sum(i[m] for i in calculados) for m in MACROS}
    meal_id = gravar_refeicao(
        db,
        user_id,
        hoje(FUSO, agora).isoformat(),
        agora.isoformat(),
        nome.strip(),
        calculados,
        totais,
        "taco",
    )
    return {"id": meal_id, **{m: round(v, 1) for m, v in totais.items()}}


def registrar_agua(db, user_id: int, ml: int, agora: datetime) -> dict:
    if not 1 <= ml <= 2000:
        raise ErroFerramenta("Água: informe de 1 a 2000 ml por registro.")
    gravar_agua(db, user_id, hoje(FUSO, agora).isoformat(), agora.isoformat(), ml)
    return {"ml": ml}


def validar_ajuste_metas(
    db,
    user_id: int,
    kcal: int,
    proteina_g: int | None = None,
    carbo_g: int | None = None,
    gordura_g: int | None = None,
) -> Metas:
    """Limites em código: nunca abaixo do piso e déficit de no máximo 25% do gasto diário."""
    perfil = _perfil(db, user_id)
    piso = PISO_KCAL[perfil.sexo]
    if kcal < piso:
        raise ErroFerramenta(
            f"{kcal} kcal fica abaixo do piso de segurança ({piso} kcal). Proponha outra meta."
        )
    gasto = gasto_diario(perfil)
    minimo = round(gasto * (1 - DEFICIT_MAXIMO))
    if kcal < minimo:
        raise ErroFerramenta(
            f"{kcal} kcal é um déficit maior que 25% do gasto diário ({round(gasto)} kcal). "
            f"O mínimo é {minimo} kcal, a não ser que um nutricionista tenha prescrito."
        )
    formula = calcular_metas(perfil.model_copy(update={"meta_profissional_kcal": None}))
    proteina = proteina_g if proteina_g is not None else formula.proteina_g
    gordura = gordura_g if gordura_g is not None else formula.gordura_g
    carbo = carbo_g if carbo_g is not None else round(max((kcal - 4 * proteina - 9 * gordura) / 4, 0))
    return Metas(
        kcal=kcal,
        proteina_g=proteina,
        carbo_g=carbo,
        gordura_g=gordura,
        agua_ml=formula.agua_ml,
        origem="coach",
    )


def aplicar_ajuste_metas(
    db,
    user_id: int,
    kcal: int,
    agora: datetime,
    proteina_g: int | None = None,
    carbo_g: int | None = None,
    gordura_g: int | None = None,
) -> dict:
    metas = validar_ajuste_metas(db, user_id, kcal, proteina_g, carbo_g, gordura_g)
    db.execute(
        "UPDATE goals SET kcal = ?, proteina_g = ?, carbo_g = ?, gordura_g = ?, origem = 'coach', "
        "ajustada_em = ? WHERE user_id = ?",
        (metas.kcal, metas.proteina_g, metas.carbo_g, metas.gordura_g, agora.isoformat(), user_id),
    )
    return metas.model_dump()
