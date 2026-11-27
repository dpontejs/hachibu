"""O coach: agente único (create_agent) com as tools do aluno, skills e aprovação humana.

A aprovação usa interrupt() dentro da tool ajustar_metas: a proposta é validada antes de pausar, e a
conversa fica salva no checkpointer até o aluno aprovar ou recusar, mesmo entre duas requisições HTTP.
"""

import sqlite3
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from langchain.agents import create_agent
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from hachibu.coach.prompts import sistema
from hachibu.coach.skills import catalogo_skills
from hachibu.coach.tools import criar_tools
from hachibu.config import Settings

MARCA_FOTO = "\n\n[o aluno anexou uma foto: use analisar_foto_refeicao]"


@dataclass
class Mensagem:
    papel: str
    texto: str
    ferramentas: list[str] = field(default_factory=list)


@dataclass
class Pendente:
    ferramenta: str
    args: dict
    descricao: str


@dataclass
class RespostaCoach:
    mensagens: list[Mensagem]
    pendente: Pendente | None


_savers: dict[str, SqliteSaver] = {}
_lock = threading.Lock()


def _checkpointer(settings: Settings) -> SqliteSaver:
    caminho = str(Path(settings.db_path).with_name("coach-checkpoints.db"))
    with _lock:
        if caminho not in _savers:
            _savers[caminho] = SqliteSaver(sqlite3.connect(caminho, check_same_thread=False))
        return _savers[caminho]


def _agente(settings: Settings, modelo, user_id: int, agora: Callable[[], datetime], foto=None):
    tools = criar_tools(settings.db_path, user_id, agora, foto=foto, visao=modelo)
    return create_agent(
        modelo,
        tools=tools,
        system_prompt=sistema(catalogo_skills(), agora()),
        checkpointer=_checkpointer(settings),
    )


def _nome_ferramenta(chamada: dict) -> str:
    if chamada["name"] == "carregar_skill":
        return f"skill:{chamada['args'].get('nome', '?')}"
    return chamada["name"]


def montar_mensagens(historico: list) -> list[Mensagem]:
    """Conversa para a tela: falas do aluno e do coach, com as ferramentas usadas em cada resposta."""
    mensagens: list[Mensagem] = []
    usadas: list[str] = []
    for m in historico:
        if isinstance(m, HumanMessage):
            mensagens.append(Mensagem("usuario", m.text.replace(MARCA_FOTO, "")))
            usadas = []
        elif isinstance(m, AIMessage):
            usadas += [_nome_ferramenta(c) for c in m.tool_calls]
            if m.text.strip():
                mensagens.append(Mensagem("coach", m.text, usadas))
                usadas = []
    return mensagens


def responder(
    settings: Settings,
    modelo,
    user_id: int,
    thread_id: str,
    mensagem: str | None = None,
    foto: tuple[bytes, str] | None = None,
    decisao: dict | None = None,
    agora: Callable[[], datetime] | None = None,
) -> RespostaCoach:
    relogio = agora or (lambda: datetime.now(UTC))
    agente = _agente(settings, modelo, user_id, relogio, foto)
    config = {"configurable": {"thread_id": thread_id}}
    if decisao is not None:
        entrada = Command(resume=decisao)
    else:
        entrada = {"messages": [HumanMessage((mensagem or "") + (MARCA_FOTO if foto else ""))]}
    resultado = agente.invoke(entrada, config)
    pausas = resultado.get("__interrupt__") or []
    pendente = Pendente(**pausas[0].value) if pausas else None
    return RespostaCoach(montar_mensagens(resultado["messages"]), pendente)


def mensagens_da_thread(settings: Settings, thread_id: str) -> list[str]:
    """Textos das mensagens de ferramenta da thread (para auditoria e testes)."""
    estado = _checkpointer(settings).get({"configurable": {"thread_id": thread_id}})
    if estado is None:
        return []
    return [m.text for m in estado["channel_values"].get("messages", []) if isinstance(m, ToolMessage)]


def historico(settings: Settings, modelo, user_id: int, thread_id: str) -> RespostaCoach:
    """Conversa salva e proposta pendente, sem chamar o modelo."""
    agente = _agente(settings, modelo, user_id, lambda: datetime.now(UTC))
    estado = agente.get_state({"configurable": {"thread_id": thread_id}})
    pendente = Pendente(**estado.interrupts[0].value) if estado.interrupts else None
    return RespostaCoach(montar_mensagens(estado.values.get("messages", [])), pendente)
