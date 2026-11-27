"""Tools do agente: as funções puras de `ferramentas` com db, usuário e relógio fechados na requisição.

O schema que o modelo vê só tem os argumentos da tarefa. O usuário vem da sessão, nunca do modelo.
"""

import json
import logging
from collections.abc import Callable
from datetime import datetime

from langchain_core.tools import BaseTool, tool
from langgraph.types import interrupt
from pydantic import BaseModel, Field

from hachibu.coach import ferramentas as f
from hachibu.coach.foto import analisar_foto, casar_com_taco
from hachibu.coach.skills import criar_tool_carregar_skill
from hachibu.db import connect

log = logging.getLogger("hachibu.coach")


class ItemRefeicao(BaseModel):
    alimento_id: int = Field(description="id do alimento na TACO (use buscar_alimento_taco)")
    gramas: float = Field(description="porção em gramas")


def _json(valor) -> str:
    return json.dumps(valor, ensure_ascii=False, default=str)


def criar_tools(
    db_path: str,
    user_id: int,
    agora: Callable[[], datetime],
    foto: tuple[bytes, str] | None = None,
    visao=None,
) -> list[BaseTool]:
    """`foto` é a imagem anexada à mensagem atual (bytes, mime); `visao`, o modelo que a analisa."""

    def rodar(funcao, *args, **kwargs) -> str:
        db = connect(db_path)
        try:
            return _json(funcao(db, user_id, *args, **kwargs))
        except f.ErroFerramenta as e:
            return f"erro: {e}"
        except Exception:
            # Falha inesperada (banco travado, bug): o modelo recebe texto e a conversa não trava.
            log.exception("tool %s falhou", funcao.__name__)
            return "erro: a ferramenta falhou agora. Tente de novo ou siga sem ela."
        finally:
            db.close()

    @tool
    def ler_perfil() -> str:
        """Perfil do aluno: sexo, idade, altura, peso, objetivo, nível, dias e minutos de treino, equipamento,
        % de gordura, cintura, condições de saúde e meta do nutricionista, se houver."""
        return rodar(f.ler_perfil)

    @tool
    def ler_diagnostico() -> str:
        """Taxa basal, gasto diário, relação cintura/altura (alerta a partir de 0,5) e metas com a origem."""
        return rodar(f.ler_diagnostico)

    @tool
    def saldo_do_dia() -> str:
        """Metas, quanto o aluno já consumiu hoje, quanto falta, água e as refeições do dia."""
        return rodar(f.saldo_do_dia, agora())

    @tool
    def buscar_alimento_taco(termo: str) -> str:
        """Busca alimentos na TACO pelo nome (ex.: "frango grelhado"). Devolve id e valores por 100 g."""
        return rodar(f.buscar_alimento_taco, termo)

    @tool
    def registrar_refeicao(nome: str, itens: list[ItemRefeicao]) -> str:
        """Registra uma refeição no diário de hoje. Cada item é um alimento da TACO (alimento_id) com gramas.
        As calorias e macros são calculados pelo sistema. Use só depois que o aluno confirmar os itens."""
        return rodar(f.registrar_refeicao, nome, [i.model_dump() for i in itens], agora())

    @tool
    def registrar_agua(ml: int) -> str:
        """Registra água bebida agora, em ml (1 a 2000)."""
        return rodar(f.registrar_agua, ml, agora())

    @tool
    def ajustar_metas(
        kcal: int,
        justificativa: str,
        proteina_g: int | None = None,
        carbo_g: int | None = None,
        gordura_g: int | None = None,
    ) -> str:
        """Propõe uma nova meta diária. O aluno vê a proposta e a justificativa e aprova antes de valer.
        Macros omitidos são completados pela fórmula. Metas abaixo do piso ou com déficit acima de 25% do
        gasto diário são recusadas pelo sistema."""
        db = connect(db_path)
        try:
            # Valida antes de pedir aprovação: proposta inválida nunca chega ao aluno.
            proposta = f.validar_ajuste_metas(db, user_id, kcal, proteina_g, carbo_g, gordura_g)
            atual = f.saldo_do_dia(db, user_id, agora())["metas"]
        except f.ErroFerramenta as e:
            return f"erro: {e}"
        finally:
            db.close()
        decisao = interrupt(
            {
                "ferramenta": "ajustar_metas",
                "args": {
                    **proposta.model_dump(exclude={"agua_ml", "origem"}),
                    "justificativa": justificativa,
                },
                "descricao": (
                    f"Meta diária de {atual['kcal']} kcal para {proposta.kcal} kcal "
                    f"(proteína {proposta.proteina_g} g, carbo {proposta.carbo_g} g, "
                    f"gordura {proposta.gordura_g} g). Motivo: {justificativa}"
                ),
            }
        )
        if not decisao.get("aprovar"):
            motivo = decisao.get("motivo") or "sem motivo informado"
            return f"recusado pelo aluno, nada mudou. Motivo: {motivo}"
        return "aprovado e aplicado: " + rodar(
            f.aplicar_ajuste_metas, kcal, agora(), proteina_g, carbo_g, gordura_g
        )

    @tool
    def analisar_foto_refeicao() -> str:
        """Analisa a foto de prato anexada à mensagem atual: lista os alimentos com gramas estimadas, já
        casados com a TACO (alimento_id e kcal). Não registra nada: mostre a lista ao aluno e só chame
        registrar_refeicao depois que ele confirmar ou corrigir."""
        if foto is None or visao is None:
            return "erro: nenhuma foto foi anexada nesta mensagem. Peça para o aluno enviar a foto."
        db = connect(db_path)
        try:
            itens = analisar_foto(visao, *foto)
            return _json({"itens": casar_com_taco(db, itens)})
        except Exception:
            log.exception("análise de foto falhou")
            return "erro: não consegui analisar a foto. Peça outra foto ou que o aluno descreva o prato."
        finally:
            db.close()

    return [
        ler_perfil,
        ler_diagnostico,
        saldo_do_dia,
        buscar_alimento_taco,
        registrar_refeicao,
        registrar_agua,
        ajustar_metas,
        analisar_foto_refeicao,
        criar_tool_carregar_skill(),
    ]
