"""Fontes do tema do front: toda fonte declarada existe, e cada papel usa a fonte combinada."""

import re
from pathlib import Path

WEB = Path(__file__).resolve().parents[1] / "web"
CSS = (WEB / "src" / "theme.css").read_text()


def test_toda_fonte_declarada_existe_em_public_fonts():
    urls = re.findall(r'url\("/fonts/([^"]+)"\)', CSS)
    assert urls
    faltando = [u for u in urls if not (WEB / "public" / "fonts" / u).exists()]
    assert faltando == []


def test_texto_em_oxanium_rotulos_em_press_start_e_numeros_em_vt323():
    assert re.search(r'--f-texto:\s*"Oxanium"', CSS)
    assert re.search(r'--f-pixel:\s*"Press Start 2P"', CSS)
    assert re.search(r'--f-num:\s*"VT323"', CSS)


def test_toda_fonte_em_public_fonts_tem_licenca():
    licencas = (WEB / "public" / "fonts" / "LICENSES.txt").read_text()
    for familia in ("Oxanium", "Press Start 2P", "VT323", "DotGothic16"):
        assert f"== {familia} ==" in licencas, familia
