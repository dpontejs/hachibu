import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { describe, expect, it } from "vitest";
import Entrar from "./Entrar";

describe("Entrar", () => {
  it("mostra o lema sem a referência explícita ao 80%", () => {
    render(
      <MemoryRouter>
        <Entrar />
      </MemoryRouter>,
    );
    expect(screen.getByText("treino e dieta, um dia de cada vez")).toBeInTheDocument();
    expect(screen.queryByText(/80%/)).not.toBeInTheDocument();
  });
});
