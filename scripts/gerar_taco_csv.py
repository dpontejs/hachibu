"""Converte a TACO (4ª ed., NEPA-UNICAMP 2011) para o CSV do app.

Fonte do JSON: github.com/marcelosanto/tabela_taco (TACO.json).

Uso: python scripts/gerar_taco_csv.py TACO.json src/hachibu/data/taco.csv

"NA" (não analisado), "Tr" (traço) e "" viram 0. Alimentos com energia "*" (sem dado na fonte) ficam de fora,
para todo alimento do app ter kcal.
"""

import csv
import json
import sys

CAMPOS = {
    "kcal": "energy_kcal",
    "proteina_g": "protein_g",
    "carbo_g": "carbohydrate_g",
    "gordura_g": "lipid_g",
    "fibra_g": "fiber_g",
}


def numero(valor) -> float:
    return round(float(valor), 1) if isinstance(valor, int | float) else 0.0


def main(entrada: str, saida: str) -> None:
    with open(entrada, encoding="utf-8") as f:
        alimentos = json.load(f)
    with open(saida, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "nome", "categoria", *CAMPOS])
        for a in alimentos:
            if a["energy_kcal"] == "*":
                continue
            w.writerow([a["id"], a["description"], a["category"], *(numero(a[c]) for c in CAMPOS.values())])


if __name__ == "__main__":
    main(*sys.argv[1:3])
