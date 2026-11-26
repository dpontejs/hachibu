import pytest
from fastapi.testclient import TestClient

from hachibu.app import create_app


@pytest.fixture
def spa(settings, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text('<div id="root"></div>')
    (dist / "manifest.webmanifest").write_text('{"display": "standalone"}')
    (dist / "assets" / "app.js").write_text("console.log(1)")
    from dataclasses import replace

    return TestClient(create_app(replace(settings, static_dir=str(dist))))


def test_raiz_serve_index(spa):
    r = spa.get("/")
    assert r.status_code == 200 and 'id="root"' in r.text


def test_rota_do_react_serve_index(spa):
    assert 'id="root"' in spa.get("/treino").text


def test_arquivos_estaticos(spa):
    assert spa.get("/manifest.webmanifest").json() == {"display": "standalone"}
    assert spa.get("/assets/app.js").text == "console.log(1)"


def test_api_desconhecida_nao_vira_index(spa):
    r = spa.get("/api/nao-existe")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}


def test_nao_sai_da_pasta(spa):
    assert 'id="root"' in spa.get("/..%2f..%2fetc/passwd").text


def test_sem_build_nao_serve_spa(client):
    assert client.get("/").status_code == 404


def test_asset_inexistente_da_404_e_nao_html(spa):
    # Um PWA aberto com o index antigo pede um asset de hash velho: tem de falhar, não virar HTML.
    r = spa.get("/assets/index-velho123.js")
    assert r.status_code == 404


def test_index_sem_cache_e_assets_imutaveis(spa):
    assert spa.get("/").headers["cache-control"] == "no-cache"
    assert spa.get("/treino").headers["cache-control"] == "no-cache"
    assert "immutable" in spa.get("/assets/app.js").headers["cache-control"]
