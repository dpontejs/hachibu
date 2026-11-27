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
from langgraph.errors import GraphRecursionError
from langgraph.types import Command

from hachibu.coach.prompts import bloco_do_aluno, sistema
from hachibu.coach.skills import catalogo_skills
from hachibu.coach.tools import criar_tools
from hachibu.config import Settings
from hachibu.db import connect
from hachibu.memorias import listar as listar_memorias
from hachibu.perfil import ler_perfil

MARCA_FOTO = "\n\n[o aluno anexou uma foto: use analisar_foto_refeicao]"
# Teto de passos do grafo por mensagem (cada volta modelo → tools são 2 passos): limita o gasto da chave
# mesmo se o modelo entrar em laço. O padrão do create_agent é 9999.
LIMITE_PASSOS = 25
DESISTENCIA = "Me enrolei com essa pergunta. Pode reformular de um jeito mais direto?"


class AprovacaoPendente(Exception):
    """Há uma proposta esperando aprovar/recusar: mensagem nova quebraria a conversa."""


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


def _bloco_do_aluno(settings: Settings, user_id: int) -> str:
    """Lido a cada mensagem: o que o aluno contou em qualquer conversa vale em todas."""
    db = connect(settings.db_path)
    try:
        perfil = ler_perfil(db, user_id)
        return bloco_do_aluno(listar_memorias(db, user_id), perfil.condicoes_saude if perfil else None)
    finally:
        db.close()


def _agente(settings: Settings, modelo, user_id: int, agora: Callable[[], datetime], foto=None):
    tools = criar_tools(settings.db_path, user_id, agora, foto=foto, visao=modelo)
    return create_agent(
        modelo,
        tools=tools,
        system_prompt=sistema(catalogo_skills(), agora(), _bloco_do_aluno(settings, user_id)),
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


def _remendar_orfas(agente, config: dict, mensagens: list) -> None:
    """Responde tool calls que ficaram sem resposta (falha no meio de uma volta).

    O Gemini recusa uma conversa com function_call sem function_response: sem este remendo, a thread
    ficaria quebrada para sempre.
    """
    respondidas = {m.tool_call_id for m in mensagens if isinstance(m, ToolMessage)}
    orfas = [
        c for m in mensagens if isinstance(m, AIMessage) for c in m.tool_calls if c["id"] not in respondidas
    ]
    if orfas:
        remendos = [
            ToolMessage(
                content="erro: esta ferramenta não terminou por uma falha interna. Chame de novo se preciso.",
                tool_call_id=c["id"],
                name=c["name"],
            )
            for c in orfas
        ]
        agente.update_state(config, {"messages": remendos}, as_node="tools")


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
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": LIMITE_PASSOS}
    estado = agente.get_state(config)
    if decisao is not None:
        if not estado.interrupts:
            raise AprovacaoPendente  # não deveria acontecer: a rota confere antes
        # Retoma pelo id da pausa: com duas propostas na mesma resposta, a outra vira o próximo card.
        entrada = Command(resume={estado.interrupts[0].id: decisao})
    else:
        if estado.interrupts:
            raise AprovacaoPendente
        _remendar_orfas(agente, config, estado.values.get("messages", []))
        entrada = {"messages": [HumanMessage((mensagem or "") + (MARCA_FOTO if foto else ""))]}
    try:
        resultado = agente.invoke(entrada, config)
    except GraphRecursionError:
        historico_ = agente.get_state(config).values.get("messages", [])
        return RespostaCoach([*montar_mensagens(historico_), Mensagem("coach", DESISTENCIA)], None)
    # A proposta mostrada sai do estado salvo, a mesma fonte que a decisão usa para retomar: com duas pausas,
    # a ordem em resultado["__interrupt__"] pode diferir e o card não corresponderia à decisão.
    pausas = agente.get_state(config).interrupts
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


def primeira_fala(settings: Settings, thread_id: str) -> str | None:
    """Primeira fala do aluno na thread, lida direto do checkpointer (sem modelo). None se não há mensagem."""
    estado = _checkpointer(settings).get({"configurable": {"thread_id": thread_id}})
    falas = [
        m for m in (estado or {}).get("channel_values", {}).get("messages", []) if isinstance(m, HumanMessage)
    ]
    return falas[0].text.replace(MARCA_FOTO, "") if falas else None
