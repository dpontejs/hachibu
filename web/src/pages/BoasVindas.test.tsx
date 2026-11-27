import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import Shell from "../layout/Shell";
import BoasVindas from "./BoasVindas";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

afterEach(() => vi.unstubAllGlobals());

describe("BoasVindas", () => {
  it("apresenta o app com os caminhos para criar conta e entrar", () => {
    render(
      <MemoryRouter>
        <BoasVindas />
      </MemoryRouter>,
    );
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("HACHIBU");
    expect(screen.getAllByRole("link", { name: /criar conta/i })[0]).toHaveAttribute("href", "/cadastro");
    expect(screen.getAllByRole("link", { name: /entrar/i })[0]).toHaveAttribute("href", "/entrar");
  });

  it("conta a história do nome e dá crédito à arte da árvore", () => {
    render(
      <MemoryRouter>
        <BoasVindas />
      </MemoryRouter>,
    );
    expect(screen.getByText(/hara hachi bu/i)).toBeInTheDocument();
    expect(screen.getByText("腹八分")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /infallible/i })).toHaveAttribute(
      "href",
      "https://infallible.itch.io/pack-of-sakura-trees",
    );
  });
});

describe("Shell sem sessão", () => {
  it("quem não está logado vê a landing em vez do login", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "nao_autenticado" }, 401)));
    render(
      <MemoryRouter initialEntries={["/"]}>
        <Routes>
          <Route path="/boas-vindas" element={<p>LANDING</p>} />
          <Route path="/entrar" element={<p>LOGIN</p>} />
          <Route element={<Shell />}>
            <Route index element={<p>HOJE</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
    expect(await screen.findByText("LANDING")).toBeInTheDocument();
    expect(screen.queryByText("HOJE")).not.toBeInTheDocument();
  });
});
