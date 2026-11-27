from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from hachibu.app import create_app
from hachibu.coach.agente import mensagens_da_thread
from hachibu.coach.foto import ItemFoto
from tests.coach_fake import chamada, roteiro
from tests.conftest import CONVITE
from tests.test_metas import BASE

JPEG = b"\xff\xd8\xff" + b"0" * 50


@pytest.fixture
def aluno(app, make_user):
    c = make_user()
    c.put("/api/perfil", json=BASE)
    return c


def enviar(c, mensagem="oi", thread_id=None, foto=None):
    data = {"mensagem": mensagem} | ({"thread_id": thread_id} if thread_id else {})
    files = {"foto": ("prato.jpg", foto[0], foto[1])} if foto else None
    return c.post("/api/coach", data=data, files=files)


def test_conversa_basica(app, aluno):
    app.state.modelo_coach = roteiro(chamada("registrar_agua", {"ml": 300}), "Anotado!")
    r = enviar(aluno, "bebi 300 ml")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["thread_id"] and corpo["pendente"] is None
    assert corpo["mensagens"][-1] == {
        "papel": "coach",
        "texto": "Anotado!",
        "ferramentas": ["registrar_agua"],
    }
    h = aluno.get(f"/api/coach/{corpo['thread_id']}").json()
    assert h["mensagens"] == corpo["mensagens"]


def test_thread_de_outro_usuario_recusada(app, aluno, make_user):
    app.state.modelo_coach = roteiro(chamada("ajustar_metas", {"kcal": 2400, "justificativa": "x"}), "ok")
    thread = enviar(aluno, "ajusta").json()["thread_id"]
    intruso = make_user("b@x.com")
    intruso.put("/api/perfil", json=BASE)
    assert enviar(intruso, "oi", thread_id=thread).status_code == 404
    assert intruso.post(f"/api/coach/{thread}/decisao", json={"aprovar": True}).status_code == 404
    assert intruso.get(f"/api/coach/{thread}").status_code == 404
    assert aluno.get("/api/hoje").json()["metas"]["kcal"] == 2759


def test_aprovacao_e_recusa_pela_rota(app, settings, aluno):
    app.state.modelo_coach = roteiro(
        chamada("ajustar_metas", {"kcal": 2400, "justificativa": "x"}),
        "Mantive.",
    )
    corpo = enviar(aluno, "ajusta").json()
    assert corpo["pendente"]["args"]["kcal"] == 2400
    thread = corpo["thread_id"]
    r = aluno.post(f"/api/coach/{thread}/decisao", json={"aprovar": False, "motivo": "agora não"})
    assert r.status_code == 200 and r.json()["pendente"] is None
    assert aluno.get("/api/hoje").json()["metas"]["kcal"] == 2759
    assert any("agora não" in m for m in mensagens_da_thread(settings, thread))


def test_decisao_sem_pendencia_409(app, aluno):
    app.state.modelo_coach = roteiro("Oi!")
    thread = enviar(aluno).json()["thread_id"]
    assert aluno.post(f"/api/coach/{thread}/decisao", json={"aprovar": True}).status_code == 409


def test_cota_diaria_429(settings, make_user):
    app = create_app(replace(settings, coach_limite_diario=2))
    c = TestClient(app)
    c.post("/api/auth/signup", json={"email": "a@x.com", "senha": "senha-forte-1", "convite": CONVITE})
    c.put("/api/perfil", json=BASE)
    app.state.modelo_coach = roteiro("1", "2", "3")
    assert [enviar(c).status_code for _ in range(3)] == [200, 200, 429]
    assert enviar(c).json() == {"detail": "cota_do_coach"}


def test_coach_sem_modelo_503(app, aluno):
    app.state.modelo_coach = None
    r = enviar(aluno)
    assert (r.status_code, r.json()) == (503, {"detail": "coach_indisponivel"})


def test_coach_com_modelo_falhando_503(app, aluno):
    class Quebrado:
        def bind_tools(self, *a, **k):
            return self

        def invoke(self, *a, **k):
            raise RuntimeError("API key not valid")

    app.state.modelo_coach = Quebrado()
    assert enviar(aluno).status_code == 503


def test_coach_exige_login(client):
    assert enviar(client).status_code == 401


def test_foto_pela_rota_chega_a_tool(app, settings, aluno):
    app.state.modelo_coach = roteiro(
        chamada("analisar_foto_refeicao"),
        "Vi arroz, 150 g. Confirma?",
        itens_foto=[ItemFoto(nome="arroz integral cozido", gramas=150, confianca="alta")],
    )
    corpo = enviar(aluno, "registra", foto=(JPEG, "image/jpeg")).json()
    assert corpo["mensagens"][0]["texto"] == "registra"
    assert any("Arroz, integral, cozido" in m for m in mensagens_da_thread(settings, corpo["thread_id"]))


def test_foto_invalida_422(app, aluno):
    app.state.modelo_coach = roteiro("x")
    assert enviar(aluno, foto=(b"GIF89a", "image/gif")).status_code == 422


def test_mensagem_vazia_422(app, aluno):
    app.state.modelo_coach = roteiro("x")
    assert enviar(aluno, mensagem="").status_code == 422
