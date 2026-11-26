import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import Hoje from "./Hoje";

const HOJE = {
  data: "2026-11-26",
  metas: { kcal: 2300, proteina_g: 170, carbo_g: 250, gordura_g: 70, agua_ml: 3000 },
  consumido: { kcal: 1640, proteina_g: 128, carbo_g: 180, gordura_g: 48 },
  agua_ml: 1500,
  refeicoes: [
    { id: 1, nome: "Café da manhã", kcal: 520, criado_em: "2026-11-26T10:05:00Z" },
    { id: 2, nome: "Almoço", kcal: 1120, criado_em: "2026-11-26T15:30:00Z" },
  ],
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderHoje() {
  return render(
    <MemoryRouter initialEntries={["/"]}>
      <Hoje />
    </MemoryRouter>,
  );
}

describe("Hoje", () => {
  it("mostra kcal consumidas, restantes e 6 de 12 gotas", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => json(HOJE)),
    );
    const { container } = renderHoje();

    expect(await screen.findByText("1640")).toBeInTheDocument();
    expect(screen.getByText("660 restantes")).toBeInTheDocument();

    const gotas = container.querySelectorAll("[data-gota]");
    expect(gotas).toHaveLength(12);
    const cheias = container.querySelectorAll('[data-gota="cheia"]');
    expect(cheias).toHaveLength(6);

    expect(screen.getByText("Almoço")).toBeInTheDocument();
  });

  it("mostra a origem da meta e abre os itens da refeição ao tocar", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () =>
        json({
          ...HOJE,
          metas: { ...HOJE.metas, origem: "profissional" },
          refeicoes: [
            { ...HOJE.refeicoes[0], itens: [] },
            {
              ...HOJE.refeicoes[1],
              itens: [{ nome: "Arroz, integral, cozido", gramas: 150, kcal: 185.3 }],
            },
          ],
        }),
      ),
    );
    renderHoje();

    expect(await screen.findByText("seu nutricionista")).toBeInTheDocument();
    expect(screen.queryByText("Arroz, integral, cozido")).not.toBeInTheDocument();

    const almoco = screen.getByRole("button", { name: /Almoço/ });
    expect(almoco).toHaveAttribute("aria-expanded", "false");
    await userEvent.click(almoco);

    expect(almoco).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("Arroz, integral, cozido")).toBeInTheDocument();
    expect(screen.getByText("150 g")).toBeInTheDocument();
    // Refeição manual (sem itens) não vira botão.
    expect(screen.queryByRole("button", { name: /Café da manhã/ })).not.toBeInTheDocument();
  });

  it("registra água e recarrega o dia", async () => {
    let agua = 1500;
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      if (String(url) === "/api/agua" && init?.method === "POST") {
        agua += JSON.parse(String(init.body)).ml;
        return json({ ok: true }, 201);
      }
      return json({ ...HOJE, agua_ml: agua });
    });
    vi.stubGlobal("fetch", fetchMock);
    const { container } = renderHoje();
    await screen.findByText("1640");

    await userEvent.click(screen.getByRole("button", { name: "+500 ml" }));

    await waitFor(() =>
      expect(container.querySelectorAll('[data-gota="cheia"]')).toHaveLength(8),
    );
    const post = fetchMock.mock.calls.find(([u]) => String(u) === "/api/agua");
    expect(post?.[1]?.credentials).toBe("include");
  });
});
