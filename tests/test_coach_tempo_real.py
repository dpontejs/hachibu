"""Coach em tempo real: passos do agente, id da conversa escolhido pelo app, foto no histórico e log."""

import logging
import threading

from hachibu.coach.agente import responder
from tests.coach_fake import chamada, roteiro
from tests.test_coach_rotas import JPEG, enviar
from tests.test_metas import BASE

ID = "a" * 32


def test_responder_avisa_cada_passo_na_ordem(settings, aluno):
    passos: list[str] = []
    modelo = roteiro(
        chamada("carregar_skill", {"nome": "nutricao"}, "c1"),
        chamada("saldo_do_dia", {}, "c2"),
        "Faltam 900 kcal.",
    )
    r = responder(settings, modelo, 1, "t1", mensagem="como estou?", ao_passo=passos.append)
    assert passos == ["skill:nutricao", "saldo_do_dia"]
    assert r.mensagens[-1].texto == "Faltam 900 kcal."


def test_mensagem_com_foto_fica_marcada_no_historico(app, aluno):
    app.state.modelo_coach = roteiro("Vi a foto.")
    corpo = enviar(aluno, "registra", foto=(JPEG, "image/jpeg")).json()
    usuario = corpo["mensagens"][0]
    assert usuario["papel"] == "usuario" and usuario["foto"] is True
    assert usuario["texto"] == "registra"
    assert corpo["mensagens"][-1]["foto"] is False


def test_id_escolhido_pelo_app_vira_conversa_nova(app, aluno):
    app.state.modelo_coach = roteiro("Oi!")
    corpo = enviar(aluno, "oi", thread_id=ID).json()
    assert corpo["thread_id"] == ID
    assert aluno.get(f"/api/coach/{ID}").json()["mensagens"][-1]["texto"] == "Oi!"
    assert [c["thread_id"] for c in aluno.get("/api/coach/conversas").json()["conversas"]] == [ID]


def test_id_em_formato_invalido_422(app, aluno):
    app.state.modelo_coach = roteiro("Oi!")
    assert enviar(aluno, "oi", thread_id="../x").status_code == 422


def test_id_de_outro_usuario_continua_404(app, aluno, make_user):
    app.state.modelo_coach = roteiro("Oi!")
    enviar(aluno, "oi", thread_id=ID)
    intruso = make_user("b@x.com")
    intruso.put("/api/perfil", json=BASE)
    assert enviar(intruso, "oi", thread_id=ID).status_code == 404


def test_falha_em_conversa_nova_com_id_do_app_nao_deixa_dono(app, aluno, make_user):
    class Quebrado:
        def bind_tools(self, *a, **k):
            return self

        def invoke(self, *a, **k):
            raise RuntimeError("fora do ar")

    app.state.modelo_coach = Quebrado()
    assert enviar(aluno, "oi", thread_id=ID).status_code == 503
    app.state.modelo_coach = roteiro("Oi!")
    assert aluno.get("/api/coach/conversas").json()["conversas"] == []
    assert aluno.get(f"/api/coach/{ID}").status_code == 404


def test_historico_diz_se_ainda_esta_processando(app, aluno):
    liberar = threading.Event()
    viu: dict = {}

    class Lento:
        def bind_tools(self, *a, **k):
            return self

        def invoke(self, *a, **k):
            viu["durante"] = aluno.get(f"/api/coach/{ID}").json()["processando"]
            liberar.set()
            from langchain_core.messages import AIMessage

            return AIMessage(content="Pronto.")

    app.state.modelo_coach = Lento()
    corpo = enviar(aluno, "oi", thread_id=ID).json()
    assert liberar.is_set() and viu["durante"] is True
    assert corpo["processando"] is False
    assert aluno.get(f"/api/coach/{ID}").json()["processando"] is False


def test_log_registra_duracao_sem_o_texto(app, aluno, caplog):
    app.state.modelo_coach = roteiro(chamada("saldo_do_dia"), "Faltam 900 kcal.")
    with caplog.at_level(logging.INFO, logger="hachibu.coach"):
        enviar(aluno, "segredo: sou hipertenso", foto=(JPEG, "image/jpeg"))
    [linha] = [r.getMessage() for r in caplog.records if r.getMessage().startswith("coach ")]
    assert "duracao=" in linha and "ferramentas=saldo_do_dia" in linha and "foto=sim" in linha
    assert "resultado=ok" in linha
    assert "hipertenso" not in linha and "900" not in linha


def test_app_de_producao_mostra_o_log_do_coach(monkeypatch, tmp_path):
    from hachibu.app import from_env

    monkeypatch.setenv("DB_PATH", str(tmp_path / "h.db"))
    monkeypatch.setenv("SESSION_SECRET", "s" * 32)
    monkeypatch.setenv("INVITE_CODE", "conv")
    from_env()
    raiz = logging.getLogger("hachibu")
    assert raiz.getEffectiveLevel() == logging.INFO
    assert raiz.handlers
