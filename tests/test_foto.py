import json
from datetime import UTC, datetime

import pytest

from hachibu.coach.foto import ItemFoto, ItensFoto, analisar_foto, casar_com_taco, validar_foto
from hachibu.coach.tools import criar_tools
from hachibu.db import connect
from tests.test_metas import BASE

AGORA = datetime(2026, 11, 27, 15, 0, tzinfo=UTC)
JPEG = b"\xff\xd8\xff" + b"0" * 100


class VisaoFalsa:
    """Imita model.with_structured_output(ItensFoto).invoke(mensagens) e guarda o que recebeu."""

    def __init__(self, itens):
        self.itens = itens
        self.recebido = None

    def with_structured_output(self, schema):
        assert schema is ItensFoto
        return self

    def invoke(self, mensagens):
        self.recebido = mensagens
        return ItensFoto(itens=self.itens)


ARROZ_FRANGO = [
    ItemFoto(nome="arroz integral cozido", gramas=150, confianca="alta"),
    ItemFoto(nome="peito de frango grelhado", gramas=120, confianca="media"),
]


def test_analisar_foto_manda_imagem_e_manda_ignorar_texto():
    visao = VisaoFalsa(ARROZ_FRANGO)
    itens = analisar_foto(visao, JPEG, "image/jpeg")
    assert itens == ARROZ_FRANGO
    sistema, humano = visao.recebido
    assert "ignore" in sistema.content.lower() and "texto" in sistema.content.lower()
    assert any(b.get("type") == "image" and b.get("mime_type") == "image/jpeg" for b in humano.content)


def test_casar_itens_com_taco(settings, app):
    db = connect(settings.db_path)
    casados = casar_com_taco(db, ARROZ_FRANGO)
    assert casados[0]["alimento_id"] == 1 and casados[0]["kcal"] == 185.3
    assert casados[1]["alimento_id"] == 410 and "Frango, peito" in casados[1]["nome_taco"]


def test_item_sem_correspondencia_fica_sem_id(settings, app):
    db = connect(settings.db_path)
    casado = casar_com_taco(db, [ItemFoto(nome="xyzqwerty", gramas=100, confianca="baixa")])[0]
    assert casado["alimento_id"] is None and casado["kcal"] is None


def test_foto_nao_registra_sozinha(settings, make_user):
    make_user().put("/api/perfil", json=BASE)
    tools = {
        t.name: t
        for t in criar_tools(
            settings.db_path, 1, lambda: AGORA, foto=(JPEG, "image/jpeg"), visao=VisaoFalsa(ARROZ_FRANGO)
        )
    }
    r = json.loads(tools["analisar_foto_refeicao"].invoke({}))
    assert [i["alimento_id"] for i in r["itens"]] == [1, 410]
    assert json.loads(tools["saldo_do_dia"].invoke({}))["refeicoes"] == []


def test_tool_de_foto_sem_foto_anexada(settings, make_user):
    make_user().put("/api/perfil", json=BASE)
    tools = {t.name: t for t in criar_tools(settings.db_path, 1, lambda: AGORA)}
    assert tools["analisar_foto_refeicao"].invoke({}).startswith("erro:")


@pytest.mark.parametrize(
    "conteudo,mime", [(b"0" * (5 * 1024 * 1024 + 1), "image/jpeg"), (b"GIF89a", "image/gif")]
)
def test_foto_grande_ou_formato_invalido(conteudo, mime):
    with pytest.raises(ValueError):
        validar_foto(conteudo, mime)
