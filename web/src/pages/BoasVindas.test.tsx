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
    expect(screen.getAllByText(/hara hachi bu/i).length).toBeGreaterThan(0);
    expect(screen.getAllByText("腹八分").length).toBe(2); // ao lado do nome e na seção da história
    expect(screen.getByRole("link", { name: /infallible/i })).toHaveAttribute(
      "href",
      "https://infallible.itch.io/pack-of-sakura-trees",
    );
  });
});

describe("BoasVindas: conteúdo", () => {
  it("explica o app em seções: como funciona, o que faz, em breve, instalar, dados e nome", () => {
    render(
      <MemoryRouter>
        <BoasVindas />
      </MemoryRouter>,
    );
    const secoes = screen.getAllByRole("heading", { level: 2 }).map((h) => h.textContent);
    expect(secoes).toEqual([
      "DE ONDE VEM O NOME",
      "COMO FUNCIONA",
      "O QUE ELE FAZ",
      "EM BREVE",
      "NO SEU CELULAR",
      "SEUS DADOS",
      "PRONTO PARA COMECAR?",
    ]);
    expect(screen.getByText(/Adicionar à Tela de Início/)).toBeInTheDocument();
    expect(screen.getByText(/fotos não são guardadas/i)).toBeInTheDocument();
    expect(screen.queryByText(/um pixel de cada vez/i)).not.toBeInTheDocument();
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

describe("Shell: erros e sessão expirada", () => {
  function montar(inicio: string) {
    return render(
      <MemoryRouter initialEntries={[inicio]}>
        <Routes>
          <Route path="/boas-vindas" element={<p>LANDING</p>} />
          <Route path="/entrar" element={<p>LOGIN</p>} />
          <Route element={<Shell />}>
            <Route index element={<p>TELA DO HOJE</p>} />
            <Route path="comida" element={<p>COMIDA</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );
  }

  it("sessão expirada num link direto leva ao login, não à landing", async () => {
    vi.stubGlobal("fetch", vi.fn(async () => json({ detail: "nao_autenticado" }, 401)));
    montar("/comida");
    expect(await screen.findByText("LOGIN")).toBeInTheDocument();
  });

  it("falha de rede mostra erro com tentar de novo, em vez de tela vazia", async () => {
    const fetchMock = vi
      .fn()
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValue(json({ email: "a@x.com", perfil_completo: true }));
    vi.stubGlobal("fetch", fetchMock);
    montar("/");
    const botao = await screen.findByRole("button", { name: /tentar de novo/i });
    botao.click();
    expect(await screen.findByText("TELA DO HOJE")).toBeInTheDocument();
  });
});

