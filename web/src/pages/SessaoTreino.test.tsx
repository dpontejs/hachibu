import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import SessaoTreino from "./SessaoTreino";

function json(body: unknown, status = 200): Response {
  return new Response(status === 204 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const SUPINO = {
  ordem: 0,
  exercicio_id: "supino_reto",
  nome: "Supino reto com barra",
  series_planejadas: 3,
  reps_min: 8,
  reps_max: 12,
  descanso_s: 90,
  feitas: [] as { ordem: number; carga_kg: number | null; reps: number }[],
  ultima: { data: "2026-11-25", local: "Smart Fit", series: [{ carga_kg: 30, reps: 10 }, { carga_kg: 30, reps: 9 }] },
};

const SESSAO = {
  id: 7,
  data: "2026-11-28",
  nome: "Superior A",
  plano_dia: 0,
  local: "Smart Fit",
  iniciada_em: new Date().toISOString(),
  finalizada_em: null,
  exercicios: [SUPINO],
};

type Chamada = { url: string; method: string; body?: unknown };

function servidor(rotas: (u: string, method: string, body: unknown) => Response | undefined) {
  const chamadas: Chamada[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      const method = init?.method ?? "GET";
      const body = init?.body ? JSON.parse(String(init.body)) : undefined;
      chamadas.push({ url: u, method, body });
      if (u === "/api/locais") return json(["Smart Fit"]);
      return rotas(u, method, body) ?? json({ detail: "Not Found" }, 404);
    }),
  );
  return chamadas;
}

function renderSessao() {
  return render(
    <MemoryRouter initialEntries={["/treino/sessao/7"]}>
      <Routes>
        <Route path="/treino/sessao/:id" element={<SessaoTreino />} />
        <Route path="/treino" element={<p>tela do treino</p>} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("SessaoTreino", () => {
  it("mostra a última vez e já preenche as séries com ela", async () => {
    servidor((u) => (u === "/api/sessoes/7" ? json(SESSAO) : undefined));
    renderSessao();
    const ex = await screen.findByRole("region", { name: "Supino reto com barra" });
    expect(within(ex).getByText(/última vez: 30 kg × 10, 30 kg × 9/i)).toBeInTheDocument();
    const cargas = within(ex).getAllByRole("textbox", { name: /carga/i });
    expect(cargas).toHaveLength(3);
    expect(cargas[0]).toHaveValue("30");
    expect(within(ex).getAllByRole("spinbutton", { name: /reps/i })[1]).toHaveValue(9);
  });

  it("marcar a série salva na hora e começa o descanso", async () => {
    const chamadas = servidor((u, method, body) => {
      if (u === "/api/sessoes/7" && method === "GET") return json(SESSAO);
      if (u === "/api/sessoes/7/series" && method === "PUT") {
        const b = body as { ordem: number; carga_kg: number; reps: number };
        return json({ ...SESSAO, exercicios: [{ ...SUPINO, feitas: [{ ordem: b.ordem, carga_kg: b.carga_kg, reps: b.reps }] }] });
      }
    });
    const user = userEvent.setup();
    renderSessao();
    const ex = await screen.findByRole("region", { name: "Supino reto com barra" });
    const carga = within(ex).getAllByRole("textbox", { name: /carga/i })[0];
    await user.clear(carga);
    await user.type(carga, "32.5");
    await user.click(within(ex).getAllByRole("button", { name: /marcar série/i })[0]);
    await waitFor(() => expect(chamadas.some((c) => c.method === "PUT")).toBe(true));
    expect(chamadas.find((c) => c.method === "PUT")!.body).toEqual({ ordem_exercicio: 0, ordem: 0, carga_kg: 32.5, reps: 10 });
    expect(await screen.findByRole("timer", { name: /descanso/i })).toHaveTextContent("1:30");
    expect(within(ex).getAllByRole("button", { name: /desmarcar série/i })).toHaveLength(1);
  });

  it("desmarcar apaga a série", async () => {
    const feita = { ...SUPINO, feitas: [{ ordem: 0, carga_kg: 30, reps: 10 }] };
    const chamadas = servidor((u, method) => {
      if (u === "/api/sessoes/7" && method === "GET") return json({ ...SESSAO, exercicios: [feita] });
      if (u === "/api/sessoes/7/series/0/0" && method === "DELETE") return json(SESSAO);
    });
    const user = userEvent.setup();
    renderSessao();
    await user.click(await screen.findByRole("button", { name: /desmarcar série/i }));
    await waitFor(() => expect(chamadas.some((c) => c.method === "DELETE")).toBe(true));
  });

  it("+ série acrescenta uma linha", async () => {
    servidor((u) => (u === "/api/sessoes/7" ? json(SESSAO) : undefined));
    const user = userEvent.setup();
    renderSessao();
    const ex = await screen.findByRole("region", { name: "Supino reto com barra" });
    await user.click(within(ex).getByRole("button", { name: /\+ série/i }));
    expect(within(ex).getAllByRole("textbox", { name: /carga/i })).toHaveLength(4);
  });

  it("trocar o exercício só no dia", async () => {
    const chamadas = servidor((u, method) => {
      if (u === "/api/sessoes/7" && method === "GET") return json(SESSAO);
      if (u.startsWith("/api/exercicios?q=")) return json([{ id: "supino_halteres", nome: "Supino reto com halteres", grupo: "peito", equipamentos: [] }]);
      if (u === "/api/sessoes/7/exercicios/0" && method === "PUT")
        return json({ ...SESSAO, exercicios: [{ ...SUPINO, exercicio_id: "supino_halteres", nome: "Supino reto com halteres", ultima: null }] });
    });
    const user = userEvent.setup();
    renderSessao();
    const ex = await screen.findByRole("region", { name: "Supino reto com barra" });
    await user.click(within(ex).getByRole("button", { name: /trocar/i }));
    await user.type(screen.getByRole("searchbox", { name: /buscar exercício/i }), "supino");
    await user.click(await screen.findByRole("button", { name: "Supino reto com halteres" }));
    expect(await screen.findByRole("region", { name: "Supino reto com halteres" })).toBeInTheDocument();
    expect(chamadas.find((c) => c.method === "PUT")!.body).toEqual({ exercicio_id: "supino_halteres" });
  });

  it("finalizar mostra o resumo", async () => {
    servidor((u, method) => {
      if (u === "/api/sessoes/7" && method === "GET") return json(SESSAO);
      if (u === "/api/sessoes/7/finalizar" && method === "POST") return json({ duracao_min: 52, series: 14, volume_kg: 4320 });
    });
    vi.spyOn(window, "confirm").mockReturnValue(true); // nenhuma série marcada: o app confirma antes
    const user = userEvent.setup();
    renderSessao();
    await user.click(await screen.findByRole("button", { name: /finalizar/i }));
    const resumo = await screen.findByRole("region", { name: /treino concluído/i });
    expect(resumo).toHaveTextContent("52 min");
    expect(resumo).toHaveTextContent("14 séries");
    expect(resumo).toHaveTextContent("4.320 kg");
  });

  it("aceita carga com vírgula", async () => {
    const chamadas = servidor((u, method) => {
      if (u === "/api/sessoes/7" && method === "GET") return json(SESSAO);
      if (u === "/api/sessoes/7/series" && method === "PUT") return json(SESSAO);
    });
    const user = userEvent.setup();
    renderSessao();
    const ex = await screen.findByRole("region", { name: "Supino reto com barra" });
    const carga = within(ex).getAllByRole("textbox", { name: /carga/i })[0];
    await user.clear(carga);
    await user.type(carga, "32,5");
    await user.click(within(ex).getAllByRole("button", { name: /marcar série 1/i })[0]);
    await waitFor(() => expect(chamadas.find((c) => c.method === "PUT")?.body).toMatchObject({ carga_kg: 32.5 }));
  });

  it("carga inválida não vira peso do corpo: o ✓ fica bloqueado", async () => {
    servidor((u) => (u === "/api/sessoes/7" ? json(SESSAO) : undefined));
    const user = userEvent.setup();
    renderSessao();
    const ex = await screen.findByRole("region", { name: "Supino reto com barra" });
    const carga = within(ex).getAllByRole("textbox", { name: /carga/i })[0];
    await user.clear(carga);
    await user.type(carga, "3x");
    expect(within(ex).getAllByRole("button", { name: /marcar série 1/i })[0]).toBeDisabled();
  });

  it("marcar a série extra não cria mais uma linha", async () => {
    servidor((u, method, body) => {
      if (u === "/api/sessoes/7" && method === "GET") return json(SESSAO);
      if (u === "/api/sessoes/7/series" && method === "PUT") {
        const b = body as { ordem: number; carga_kg: number; reps: number };
        return json({ ...SESSAO, exercicios: [{ ...SUPINO, feitas: [{ ordem: b.ordem, carga_kg: b.carga_kg, reps: b.reps }] }] });
      }
    });
    const user = userEvent.setup();
    renderSessao();
    const ex = await screen.findByRole("region", { name: "Supino reto com barra" });
    await user.click(within(ex).getByRole("button", { name: /\+ série/i }));
    await user.click(within(ex).getByRole("button", { name: /marcar série 4/i }));
    await within(ex).findByRole("button", { name: /desmarcar série 4/i });
    expect(within(ex).getAllByRole("textbox", { name: /carga/i })).toHaveLength(4);
  });

  it("sessão finalizada é só leitura", async () => {
    const feita = { ...SUPINO, feitas: [{ ordem: 0, carga_kg: 30, reps: 10 }] };
    servidor((u) =>
      u === "/api/sessoes/7" ? json({ ...SESSAO, finalizada_em: "2026-11-28T12:00:00Z", exercicios: [feita] }) : undefined,
    );
    renderSessao();
    expect(await screen.findByText(/treino finalizado/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /finalizar/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /marcar série/i })).not.toBeInTheDocument();
  });
});

