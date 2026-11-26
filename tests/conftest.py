import pytest
from fastapi.testclient import TestClient

from hachibu.app import create_app
from hachibu.config import Settings

CONVITE = "convite-teste"


@pytest.fixture
def settings(tmp_path):
    return Settings(
        db_path=str(tmp_path / "hachibu.db"),
        session_secret="s" * 32,
        invite_code=CONVITE,
        cookie_secure=False,
    )


@pytest.fixture
def app(settings):
    return create_app(settings)


@pytest.fixture
def client(app):
    return TestClient(app)


@pytest.fixture
def make_user(app):
    """Cria um usuário pela API e devolve um TestClient próprio, já logado."""

    def _make(email: str = "a@x.com", senha: str = "senha-forte-1") -> TestClient:
        c = TestClient(app)
        r = c.post("/api/auth/signup", json={"email": email, "senha": senha, "convite": CONVITE})
        assert r.status_code == 201, r.text
        return c

    return _make
