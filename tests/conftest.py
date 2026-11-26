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
