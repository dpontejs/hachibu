"""O que o coach pode fazer no estado do aluno: funções puras (db, user_id, ...).

Não sabem nada de LLM. Quem chama (tools do agente, um futuro MCP externo) decide de onde vêm db e user_id;
o modelo nunca escolhe o usuário. Erro de uso vira ErroFerramenta com mensagem em português para o modelo ler.
"""

from datetime import datetime

from hachibu import memorias
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
from hachibu.treino.base import gerar_plano_base
from hachibu.treino.diferencas import diferencas, resumo_semana
from hachibu.treino.exercicios import buscar as buscar_no_catalogo
from hachibu.treino.exercicios import por_id
from hachibu.treino.modelos import PlanoIn
from hachibu.treino.repositorio import gravar_plano, plano_ativo, semana_corrida
from hachibu.treino.validador import validar_plano

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
            f"O mínimo é {minimo} kcal. Se um nutricionista prescreveu menos, "
            "o aluno preenche a meta dele no Perfil."
        )
    maximo = round(gasto * 1.25)
    if kcal > maximo:
        raise ErroFerramenta(
            f"{kcal} kcal passa do máximo razoável ({maximo} kcal, 25% acima do gasto diário)."
        )
    for nome, valor, teto in (
        ("proteína", proteina_g, 400),
        ("carboidrato", carbo_g, 900),
        ("gordura", gordura_g, 250),
    ):
        if valor is not None and not 0 <= valor <= teto:
            raise ErroFerramenta(f"{nome} de {valor} g fora da faixa (0 a {teto} g).")
    formula = calcular_metas(perfil.model_copy(update={"meta_profissional_kcal": None}))
    proteina = proteina_g if proteina_g is not None else formula.proteina_g
    gordura = gordura_g if gordura_g is not None else formula.gordura_g
    carbo = carbo_g if carbo_g is not None else round(max((kcal - 4 * proteina - 9 * gordura) / 4, 0))
    total = 4 * proteina + 4 * carbo + 9 * gordura
    if abs(total - kcal) > 0.1 * kcal:
        raise ErroFerramenta(
            f"Os macros somam {total} kcal, longe da meta de {kcal} kcal (tolerância de 10%). Ajuste."
        )
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


def lembrar(db, user_id: int, tipo: str, texto: str) -> dict:
    try:
        texto = memorias._validar_texto(texto)
    except ValueError as e:
        raise ErroFerramenta(str(e)) from None
    try:
        memoria, criada = memorias.criar(db, user_id, tipo, texto, "coach")
    except memorias.LimiteDeMemorias as e:
        raise ErroFerramenta(
            f"o aluno já tem {memorias.LIMITES[e.tipo]} memórias desse tipo. "
            "Peça para ele revisar a lista na tela Perfil."
        ) from None
    return {"lembrado": memoria.model_dump(), "ja_existia": not criada}


def esquecer_gosto(db, user_id: int, id_: int) -> dict:
    memoria = memorias.apagar(db, user_id, id_, so_gostos=True)
    if memoria is not None:
        return {"esquecido": memoria.model_dump()}
    if memorias._ler(db, user_id, id_) is not None:
        raise ErroFerramenta(
            "restrições e condições físicas só o próprio aluno remove, na tela Perfil. "
            "Diga isso a ele e continue respeitando a restrição."
        )
    raise ErroFerramenta(f"não existe memória #{id_}. Confira os ids no bloco do aluno.")


# ---------- treino ----------


def _legenda(plano: PlanoIn) -> dict[str, str]:
    return {
        e.exercicio_id: (ex.nome if (ex := por_id(e.exercicio_id)) else e.exercicio_id)
        for d in plano.dias
        for e in d.exercicios
    }


def rascunho_plano(db, user_id: int) -> dict:
    """Plano base em código a partir do perfil, com os pontos que não seguiram a preferência do aluno."""
    plano, pontos = gerar_plano_base(_perfil(db, user_id))
    ativo = plano_ativo(db, user_id)
    return {
        "plano": plano.model_dump(),
        "legenda": _legenda(plano),
        "pontos": pontos,
        # A proposta leva esta versão em versao_base: se o plano mudar antes da aprovação, nada é gravado.
        "versao_atual": ativo[0]["versao"] if ativo else None,
    }


def ler_plano(db, user_id: int) -> dict:
    ativo = plano_ativo(db, user_id)
    if ativo is None:
        raise ErroFerramenta(
            "o aluno ainda não tem plano de treino. Use rascunho_plano para começar a conversa."
        )
    meta, plano = ativo
    semana = semana_corrida(db, user_id)
    return {
        "versao": meta["versao"],
        "plano": plano.model_dump(),
        "legenda": _legenda(plano),
        "semana_corrida": semana,
        "avisos": validar_plano(plano, _perfil(db, user_id), semana_corrida=semana),
    }


def buscar_exercicio(db, user_id: int, termo: str) -> list[dict]:
    equipamento = _perfil(db, user_id).equipamento
    return [
        {"id": e.id, "nome": e.nome, "grupo": e.grupo}
        for e in buscar_no_catalogo(termo)
        if equipamento in e.equipamentos
    ][:15]


def validar_proposta(db, user_id: int, plano: PlanoIn, versao_base: int | None = None) -> dict:
    """Valida contra o perfil e a versão de partida; devolve o que o card mostra: as mudanças (vazio no
    primeiro plano) e a semana proposta em estrutura.

    `versao_base` é a versão que o coach leu ao montar a proposta. Se o plano ativo for outro (o aluno aprovou
    outra proposta no meio), aplicar esta desfaria aquela em silêncio: recusa.
    """
    perfil = _perfil(db, user_id)
    ativo = plano_ativo(db, user_id)
    versao_ativa = ativo[0]["versao"] if ativo else None
    if versao_ativa != versao_base:
        raise ErroFerramenta(
            f"o plano mudou desde que esta proposta foi montada (agora é a versão {versao_ativa}). Nada foi "
            "gravado: leia o plano de novo (ler_plano) e proponha a partir dele."
        )
    anterior = ativo[1] if ativo else None
    # Primeiro plano: o volume de corrida não pode passar de 10% acima do rascunho em código.
    referencia = anterior or gerar_plano_base(perfil)[0]
    erros = sorted(
        {e for s in range(1, 10) for e in validar_plano(plano, perfil, anterior=referencia, semana_corrida=s)}
    )
    if erros:
        raise ErroFerramenta("a proposta não passa nas regras do plano: " + " | ".join(erros))
    mudancas = diferencas(anterior, plano)
    if anterior is not None and not mudancas:
        raise ErroFerramenta("nada muda em relação ao plano atual. Confira o que o aluno pediu.")
    return {"mudancas": mudancas, "semana": resumo_semana(plano)}


def aplicar_plano(db, user_id: int, plano: PlanoIn, versao_base: int | None = None) -> dict:
    validar_proposta(db, user_id, plano, versao_base)  # perfil ou plano podem ter mudado até a aprovação
    return {"versao": gravar_plano(db, user_id, plano, "coach")}
