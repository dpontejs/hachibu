"""Modelo falso para testar o coach sem chamar o Gemini: respostas e tool calls roteirizadas."""

from langchain_core.language_models import GenericFakeChatModel
from langchain_core.messages import AIMessage

from hachibu.coach.foto import ItensFoto


class ModeloFalso(GenericFakeChatModel):
    itens_foto: list = []

    def bind_tools(self, tools, **kwargs):
        return self

    def with_structured_output(self, schema, **kwargs):
        modelo = self

        class _Saida:
            def invoke(self, mensagens):
                assert schema is ItensFoto
                return ItensFoto(itens=modelo.itens_foto)

        return _Saida()


def chamada(nome: str, args: dict | None = None, id_: str = "c1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": nome, "args": args or {}, "id": id_}])


def roteiro(*respostas, itens_foto=None) -> ModeloFalso:
    msgs = [AIMessage(content=r) if isinstance(r, str) else r for r in respostas]
    return ModeloFalso(messages=iter(msgs), itens_foto=itens_foto or [])
