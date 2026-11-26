import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { describe, expect, it, vi } from "vitest";
import Comida, { nomePorHora } from "./Comida";

const ARROZ = {
  id: 1,
  nome: "Arroz, integral, cozido",
  categoria: "Cereais e derivados",
  kcal: 123.5,
  proteina_g: 2.6,
  carbo_g: 25.8,
  gordura_g: 1.0,
};

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderComida() {
  return render(
    <MemoryRouter initialEntries={["/comida"]}>
      <Routes>
        <Route path="/comida" element={<Comida />} />
        <Route path="/" element={<p>TELA HOJE</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

describe("Comida", () => {
  it("busca, monta o prato com 150 g e salva só id e gramas", async () => {
    const fetchMock = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      if (u.startsWith("/api/alimentos")) return json([ARROZ]);
      if (u === "/api/refeicoes" && init?.method === "POST") return json({ id: 7 }, 201);
      return json({ detail: "Not Found" }, 404);
    });
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderComida();

    await user.type(screen.getByRole("searchbox", { name: /buscar alimento/i }), "arroz integral");
    const resultado = await screen.findByRole("button", { name: /Arroz, integral, cozido/ });
    expect(resultado).toHaveTextContent("124");
    expect(fetchMock.mock.calls.some(([u]) => String(u) === "/api/alimentos?q=arroz%20integral")).toBe(true);

    await user.click(resultado);
    const gramas = screen.getByRole("spinbutton", { name: /gramas de Arroz, integral, cozido/i });
    expect(gramas).toHaveValue(100);
    await user.clear(gramas);
    await user.type(gramas, "150");

    expect(screen.getByLabelText("Total do prato")).toHaveTextContent("185");

    await user.click(screen.getByRole("button", { name: /salvar refeição/i }));
    expect(await screen.findByText("TELA HOJE")).toBeInTheDocument();

    const post = fetchMock.mock.calls.find(([u, i]) => String(u) === "/api/refeicoes" && i?.method === "POST");
    const corpo = JSON.parse(String(post?.[1]?.body));
    expect(Object.keys(corpo).sort()).toEqual(["itens", "nome"]);
    expect(typeof corpo.nome).toBe("string");
    expect(corpo.nome.length).toBeGreaterThan(0);
    expect(corpo.itens).toEqual([{ alimento_id: 1, gramas: 150 }]);
  });

  it("não busca com menos de 2 letras", async () => {
    const fetchMock = vi.fn(async () => json([]));
    vi.stubGlobal("fetch", fetchMock);
    const user = userEvent.setup();
    renderComida();
    await user.type(screen.getByRole("searchbox", { name: /buscar alimento/i }), "a");
    await new Promise((r) => setTimeout(r, 350));
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("nome padrão segue a hora de Brasília", () => {
    expect(nomePorHora(7)).toBe("Café da manhã");
    expect(nomePorHora(10)).toBe("Almoço");
    expect(nomePorHora(14)).toBe("Almoço");
    expect(nomePorHora(15)).toBe("Lanche");
    expect(nomePorHora(17)).toBe("Lanche");
    expect(nomePorHora(18)).toBe("Jantar");
    expect(nomePorHora(23)).toBe("Jantar");
  });
});
