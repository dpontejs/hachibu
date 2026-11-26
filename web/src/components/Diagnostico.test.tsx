import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Diagnostico as DadosDiagnostico } from "../api";
import Diagnostico from "./Diagnostico";

const BASE: DadosDiagnostico = {
  tmb: 1780,
  formula: "mifflin-st-jeor",
  fator_atividade: 1.55,
  gasto_diario: 2759,
  ajuste_objetivo: -500,
  relacao_cintura_altura: 0.5,
  alerta_cintura: true,
  abaixo_do_piso: false,
  metas: { kcal: 2259, proteina_g: 144, carbo_g: 250, gordura_g: 64, agua_ml: 2800, origem: "formula" },
};

describe("Diagnostico", () => {
  it("mostra TMB, fórmula, gasto e o aviso de cintura", () => {
    render(<Diagnostico dados={BASE} />);
    expect(screen.getByText("1780")).toBeInTheDocument();
    expect(screen.getByText(/Mifflin-St Jeor/)).toBeInTheDocument();
    expect(screen.getByText("2759")).toBeInTheDocument();
    expect(screen.getByText("0,50")).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(/cintura/i);
    expect(screen.queryByText(/abaixo do piso/i)).not.toBeInTheDocument();
  });

  it("sem cintura não mostra a relação; meta abaixo do piso avisa", () => {
    render(
      <Diagnostico
        dados={{
          ...BASE,
          relacao_cintura_altura: null,
          alerta_cintura: false,
          abaixo_do_piso: true,
          metas: { ...BASE.metas, kcal: 1200, origem: "profissional" },
        }}
      />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent(/abaixo do piso/i);
    expect(screen.getAllByText(/seu nutricionista/i).length).toBeGreaterThan(0);
    expect(screen.queryByText("0,50")).not.toBeInTheDocument();
  });
});
