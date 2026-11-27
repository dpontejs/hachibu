"""Skills do coach: catálogo curto no prompt de sistema e tool que carrega o SKILL.md sob demanda."""

from pathlib import Path

from langchain_core.tools import BaseTool, tool

PASTA = Path(__file__).parent / "skills"


def _front_matter(texto: str) -> dict:
    cabecalho = texto.split("---", 2)[1]
    return dict(linha.split(":", 1) for linha in cabecalho.strip().splitlines() if ":" in linha)


def _skills() -> list[dict]:
    return [
        {k.strip(): v.strip() for k, v in _front_matter(p.read_text(encoding="utf-8")).items()}
        for p in sorted(PASTA.glob("*/SKILL.md"))
    ]


def catalogo_skills() -> str:
    """Uma linha por skill (nome: quando usar), para o prompt de sistema."""
    return "\n".join(f"- {s['name']}: {s['description']}" for s in _skills())


def criar_tool_carregar_skill() -> BaseTool:
    @tool
    def carregar_skill(nome: str) -> str:
        """Carrega as orientações de um domínio (nutricao, musculacao ou corrida) antes de aconselhar.

        Numa pergunta que mistura domínios, carregue as skills de cada um."""
        caminho = PASTA / nome.strip().lower() / "SKILL.md"
        if not caminho.is_file():
            nomes = ", ".join(s["name"] for s in _skills())
            return f"erro: a skill '{nome}' não existe. Disponíveis: {nomes}"
        return caminho.read_text(encoding="utf-8").split("---", 2)[2].strip()

    return carregar_skill
