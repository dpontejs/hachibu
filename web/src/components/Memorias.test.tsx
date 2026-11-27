import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Memorias from "./Memorias";

function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const BASE = [
  { id: 1, tipo: "restricao", texto: "celíaco", origem: "coach", criado_em: "2026-11-28T10:00:00Z" },
  { id: 2, tipo: "condicao", texto: "dor no joelho direito", origem: "aluno", criado_em: "2026-11-28T10:00:00Z" },
  { id: 3, tipo: "gosto", texto: "não gosta de azeitona", origem: "coach", criado_em: "2026-11-28T10:00:00Z" },
];

type Chamada = { url: string; method: string; body?: unknown };

function servidor(inicial = BASE) {
  let lista = [...inicial];
  const chamadas: Chamada[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      chamadas.push({ url: u, method, body });
      if (u === "/api/memorias" && method === "GET") return json({ memorias: lista });
      if (u === "/api/memorias" && method === "POST") {
        const nova = { id: 9, origem: "aluno", criado_em: "2026-11-28T11:00:00Z", ...body };
        lista = [...lista, nova];
        return json(nova, 201);
      }
      const id = Number(u.split("/").pop());
      if (method === "PATCH") {
        lista = lista.map((m) => (m.id === id ? { ...m, ...body } : m));
        return json(lista.find((m) => m.id === id));
      }
      if (method === "DELETE") {
        lista = lista.filter((m) => m.id !== id);
        return json(null, 204);
      }
      return json({ detail: "Not Found" }, 404);
    }),
  );
  return chamadas;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe("Memorias", () => {
  it("mostra o que o coach sabe, com as restrições primeiro", async () => {
    servidor();
    render(<Memorias />);
    const restricoes = await screen.findByRole("list", { name: /restrições/i });
    expect(within(restricoes).getByText("celíaco")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: /condições físicas/i })).getByText("dor no joelho direito")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: /gostos/i })).getByText("não gosta de azeitona")).toBeInTheDocument();
    const listas = screen.getAllByRole("list").map((l) => l.getAttribute("aria-label"));
    expect(listas.indexOf("Restrições")).toBeLessThan(listas.indexOf("Gostos"));
  });

  it("adiciona uma memória escrita pelo aluno", async () => {
    const chamadas = servidor([]);
    const user = userEvent.setup();
    render(<Memorias />);
    await screen.findAllByText(/nada ainda/i);
    await user.selectOptions(screen.getByRole("combobox", { name: /tipo/i }), "restricao");
    await user.type(screen.getByRole("textbox", { name: /o que o coach deve saber/i }), "vegetariano");
    await user.click(screen.getByRole("button", { name: /adicionar/i }));
    expect(await within(screen.getByRole("list", { name: /restrições/i })).findByText("vegetariano")).toBeInTheDocument();
    expect(chamadas.find((c) => c.method === "POST")?.body).toEqual({ tipo: "restricao", texto: "vegetariano" });
  });

  it("apagar uma restrição pede confirmação", async () => {
    const chamadas = servidor();
    const confirmar = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const user = userEvent.setup();
    render(<Memorias />);
    await user.click(await screen.findByRole("button", { name: /apagar celíaco/i }));
    expect(confirmar).toHaveBeenCalledTimes(1);
    expect(chamadas.some((c) => c.method === "DELETE")).toBe(false);

    await user.click(screen.getByRole("button", { name: /apagar celíaco/i }));
    await waitFor(() => expect(screen.queryByText("celíaco")).not.toBeInTheDocument());
    expect(chamadas.some((c) => c.method === "DELETE" && c.url === "/api/memorias/1")).toBe(true);
  });

  it("apagar um gosto não pede confirmação", async () => {
    servidor();
    const confirmar = vi.spyOn(window, "confirm");
    const user = userEvent.setup();
    render(<Memorias />);
    await user.click(await screen.findByRole("button", { name: /apagar não gosta de azeitona/i }));
    await waitFor(() => expect(screen.queryByText("não gosta de azeitona")).not.toBeInTheDocument());
    expect(confirmar).not.toHaveBeenCalled();
  });

  it("edita o texto de uma memória", async () => {
    const chamadas = servidor();
    const user = userEvent.setup();
    render(<Memorias />);
    await user.click(await screen.findByRole("button", { name: /editar não gosta de azeitona/i }));
    const campo = screen.getByRole("textbox", { name: /editar memória/i });
    await user.clear(campo);
    await user.type(campo, "detesta azeitona preta");
    await user.click(screen.getByRole("button", { name: /salvar/i }));
    expect(await screen.findByText("detesta azeitona preta")).toBeInTheDocument();
    expect(chamadas.find((c) => c.method === "PATCH")?.body).toEqual({ texto: "detesta azeitona preta" });
  });
});
