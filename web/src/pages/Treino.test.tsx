import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
import { EVENTO_PLANO } from "../coach/abrir";
import Treino from "./Treino";

function json(body: unknown, status = 200): Response {
  return new Response(status === 201 ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const DESCANSO = (dia: number) => ({ dia, nome: "Descanso", exercicios: [], corrida: null });
const PLANO = {
  versao: 1,
  origem: "base",
  criado_em: "2026-11-28T10:00:00Z",
  semana_corrida: 1,
  avisos: [] as string[],
  tem_condicoes: false,
  dias: [
    {
      dia: 0,
      nome: "Corpo inteiro A",
      exercicios: [
        { exercicio_id: "agachamento_livre", nome: "Agachamento livre com barra", grupo: "quadriceps", series: 3, reps_min: 10, reps_max: 15, descanso_s: 75 },
        { exercicio_id: "supino_reto", nome: "Supino reto com barra", grupo: "peito", series: 3, reps_min: 10, reps_max: 15, descanso_s: 75 },
      ],
      corrida: { progressao: true, tipo: "corrida_caminhada", duracao_min: 26, corre_min: 1, anda_min: 2, repeticoes: 7, esforco_alvo: "3-5" },
    },
    DESCANSO(1),
    { dia: 2, nome: "Corpo inteiro B", exercicios: [], corrida: null },
    DESCANSO(3),
    { dia: 4, nome: "Corrida", exercicios: [], corrida: { progressao: false, tipo: "longao", duracao_min: 40, corre_min: null, anda_min: null, repeticoes: null, esforco_alvo: "3-4" } },
    DESCANSO(5),
    DESCANSO(6),
  ],
};

type Chamada = { url: string; init?: RequestInit };

function servidor(rotas: (u: string, init?: RequestInit) => Response | undefined) {
  const chamadas: Chamada[] = [];
  vi.stubGlobal(
    "fetch",
    vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
      const u = String(url);
      chamadas.push({ url: u, init });
      return rotas(u, init) ?? json({ detail: "Not Found" }, 404);
    }),
  );
  return chamadas;
}

function Destino() {
  const { search } = useLocation();
  return <p data-testid="destino">{new URLSearchParams(search).get("msg")}</p>;
}

function SessaoDestino() {
  const { pathname } = useLocation();
  return <p data-testid="sessao">{pathname.split("/").pop()}</p>;
}

function renderTreino() {
  return render(
    <MemoryRouter initialEntries={["/treino"]}>
      <Routes>
        <Route path="/treino" element={<Treino />} />
        <Route path="/coach" element={<Destino />} />
        <Route path="/treino/sessao/:id" element={<SessaoDestino />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("Treino", () => {
  it("sem plano, monta com o coach (nunca gera direto)", async () => {
    const chamadas = servidor((u) => (u === "/api/plano" ? json({ detail: "plano_inexistente" }, 404) : undefined));
    const user = userEvent.setup();
    renderTreino();
    await user.click(await screen.findByRole("button", { name: /montar com o coach/i }));
    expect(screen.getByTestId("destino")).toHaveTextContent(/montar meu plano de treino/i);
    expect(chamadas.some((c) => c.init?.method === "POST")).toBe(false);
  });

  it("destaca o treino de hoje com os exercícios e a corrida da semana", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-30T10:00:00") }); // segunda
    servidor((u) => (u === "/api/plano" ? json(PLANO) : undefined));
    renderTreino();
    const hoje = await screen.findByRole("region", { name: /hoje/i });
    expect(within(hoje).getByText("Corpo inteiro A")).toBeInTheDocument();
    expect(within(hoje).getByText("Supino reto com barra")).toBeInTheDocument();
    expect(within(hoje).getAllByText(/3 × 10–15/)).toHaveLength(2);
    expect(within(hoje).getByText(/1 min correndo \+ 2 min andando × 7/)).toBeInTheDocument();
    expect(screen.getByText(/semana 1 de 9/i)).toBeInTheDocument();
  });

  it("descreve corridas fixas e dias de descanso na semana", async () => {
    servidor((u) => (u === "/api/plano" ? json(PLANO) : undefined));
    renderTreino();
    const semana = await screen.findByRole("list", { name: /semana/i });
    expect(within(semana).getAllByText(/longão · 40 min/i).length).toBeGreaterThan(0);
    expect(within(semana).getAllByText("Descanso").length).toBeGreaterThanOrEqual(4);
  });

  it("avisa quando há condições físicas registradas", async () => {
    servidor((u) => (u === "/api/plano" ? json({ ...PLANO, tem_condicoes: true }) : undefined));
    renderTreino();
    expect(await screen.findByText(/condições físicas registradas/i)).toBeInTheDocument();
  });

  it("perfil mudou: oferece ajustar com o coach", async () => {
    servidor((u) =>
      u === "/api/plano" ? json({ ...PLANO, avisos: ["segunda: Supino precisa de outro equipamento"] }) : undefined,
    );
    const user = userEvent.setup();
    renderTreino();
    expect(await screen.findByText(/precisa de outro equipamento/)).toBeInTheDocument();
    expect(screen.getByText(/o plano não cabe no seu perfil atual/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /ajustar com o coach/i }));
    expect(screen.getByTestId("destino")).toHaveTextContent(/não cabe mais no meu perfil/i);
  });

  it("recarrega quando um plano é aprovado no coach", async () => {
    let versao = 1;
    servidor((u) => (u === "/api/plano" ? json({ ...PLANO, versao, dias: PLANO.dias }) : undefined));
    renderTreino();
    await screen.findByRole("region", { name: /hoje/i });
    versao = 2;
    const antes = (globalThis.fetch as unknown as { mock: { calls: unknown[] } }).mock.calls.length;
    window.dispatchEvent(new Event(EVENTO_PLANO));
    await new Promise((r) => setTimeout(r, 10));
    expect((globalThis.fetch as unknown as { mock: { calls: unknown[] } }).mock.calls.length).toBeGreaterThan(antes);
  });

  it("se carregar falhar, oferece tentar de novo", async () => {
    let falhar = true;
    servidor((u) => (u === "/api/plano" ? (falhar ? json({ detail: "x" }, 500) : json(PLANO)) : undefined));
    const user = userEvent.setup();
    renderTreino();
    const tentar = await screen.findByRole("button", { name: /tentar de novo/i });
    falhar = false;
    await user.click(tentar);
    expect(await screen.findByRole("region", { name: /hoje/i })).toBeInTheDocument();
  });

  it("marca o dia de hoje e atualiza ao voltar depois da meia-noite", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-30T23:59:00") }); // segunda
    servidor((u) => (u === "/api/plano" ? json(PLANO) : undefined));
    renderTreino();
    expect(await screen.findByText(/HOJE · SEG/)).toBeInTheDocument();
    expect(screen.getByRole("list", { name: /semana/i }).querySelector('[aria-current="date"]')).toHaveTextContent(
      "SEG",
    );
    vi.setSystemTime(new Date("2026-12-01T08:00:00")); // terça
    document.dispatchEvent(new Event("visibilitychange"));
    expect(await screen.findByText(/HOJE · TER/)).toBeInTheDocument();
  });

  it("recomeçar pede confirmação, apaga o plano e volta para montar com o coach", async () => {
    let temPlano = true;
    const chamadas = servidor((u, init) => {
      if (u === "/api/plano" && init?.method === "DELETE") {
        temPlano = false;
        return new Response(null, { status: 204 });
      }
      if (u === "/api/plano") return temPlano ? json(PLANO) : json({ detail: "plano_inexistente" }, 404);
    });
    vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const user = userEvent.setup();
    renderTreino();
    const botao = await screen.findByRole("button", { name: /recomeçar plano/i });
    await user.click(botao);
    expect(chamadas.some((c) => c.init?.method === "DELETE")).toBe(false);
    await user.click(botao);
    expect(await screen.findByRole("button", { name: /montar com o coach/i })).toBeInTheDocument();
  });

  it("mostra o cardio do dia separado da corrida", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-30T10:00:00") }); // segunda
    const dias = PLANO.dias.map((d) =>
      d.dia === 0 ? { ...d, cardio: { modalidade: "bicicleta", duracao_min: 20, intensidade: "leve" } } : d,
    );
    servidor((u) => (u === "/api/plano" ? json({ ...PLANO, dias }) : undefined));
    renderTreino();
    const hoje = await screen.findByRole("region", { name: /hoje/i });
    expect(within(hoje).getByText(/bicicleta leve · 20 min/i)).toBeInTheDocument();
  });

  it("iniciar o treino de hoje abre a sessão", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-30T10:00:00") }); // segunda
    const chamadas = servidor((u, init) => {
      if (u === "/api/plano") return json(PLANO);
      if (u === "/api/sessoes/aberta") return json({ detail: "sem_sessao_aberta" }, 404);
      if (u.startsWith("/api/sessoes?")) return json([]);
      if (u === "/api/sessoes" && init?.method === "POST") return json({ id: 9 }, 200);
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderTreino();
    await user.click(await screen.findByRole("button", { name: /iniciar treino/i }));
    expect(JSON.parse(String(chamadas.find((c) => c.init?.method === "POST")!.init!.body))).toEqual({ plano_dia: 0 });
    expect(await screen.findByTestId("sessao")).toHaveTextContent("9");
  });

  it("com uma sessão aberta, oferece continuar", async () => {
    servidor((u) => {
      if (u === "/api/plano") return json(PLANO);
      if (u === "/api/sessoes/aberta") {
        const d = new Date();
        const data = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
        return json({ id: 4, nome: "Superior A", data });
      }
      if (u.startsWith("/api/sessoes?")) return json([]);
    });
    renderTreino();
    expect(await screen.findByRole("button", { name: /continuar treino/i })).toBeInTheDocument();
    expect(screen.getByText(/em andamento: superior a/i)).toBeInTheDocument();
  });

  it("dia com treino finalizado aparece como feito", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-30T10:00:00") }); // segunda
    servidor((u) => {
      if (u === "/api/plano") return json(PLANO);
      if (u === "/api/sessoes/aberta") return json({ detail: "x" }, 404);
      if (u.startsWith("/api/sessoes?")) return json([{ id: 1, data: "2026-11-30", nome: "Corpo inteiro A", plano_dia: 0, local: null, series: 12 }]);
    });
    renderTreino();
    const hoje = await screen.findByRole("region", { name: /hoje/i });
    expect(await within(hoje).findByText(/feito/i)).toBeInTheDocument();
  });

  it("sessão esquecida de outro dia oferece finalizar ou descartar antes do treino de hoje", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-12-02T10:00:00") }); // quarta
    const chamadas = servidor((u, init) => {
      if (u === "/api/plano") return json(PLANO);
      if (u === "/api/sessoes/aberta") return json({ id: 4, nome: "Corpo inteiro A", data: "2026-11-30" });
      if (u.startsWith("/api/sessoes?")) return json([]);
      if (u === "/api/sessoes/4/finalizar" && init?.method === "POST") return json({ duracao_min: 50, series: 3, volume_kg: 900 });
    });
    const user = userEvent.setup({ advanceTimers: vi.advanceTimersByTime });
    renderTreino();
    expect(await screen.findByText(/treino aberto de 30\/11/i)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /finalizar esse/i }));
    await waitFor(() => expect(chamadas.some((c) => c.url === "/api/sessoes/4/finalizar")).toBe(true));
  });

  it("sem plano, ainda dá para fazer um treino livre", async () => {
    servidor((u) => {
      if (u === "/api/plano") return json({ detail: "plano_inexistente" }, 404);
      if (u === "/api/sessoes/aberta") return json({ detail: "x" }, 404);
      if (u.startsWith("/api/sessoes?")) return json([]);
    });
    renderTreino();
    expect(await screen.findByRole("button", { name: /treino livre/i })).toBeInTheDocument();
  });

  it("sessão finalizada sem séries não marca o dia como feito", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true, now: new Date("2026-11-30T10:00:00") }); // segunda
    servidor((u) => {
      if (u === "/api/plano") return json(PLANO);
      if (u === "/api/sessoes/aberta") return json({ detail: "x" }, 404);
      if (u.startsWith("/api/sessoes?")) return json([{ id: 1, data: "2026-11-30", nome: "Corpo inteiro A", plano_dia: 0, local: null, series: 0 }]);
    });
    renderTreino();
    const hoje = await screen.findByRole("region", { name: /hoje/i });
    await new Promise((r) => setTimeout(r, 20));
    expect(within(hoje).queryByText(/feito/i)).not.toBeInTheDocument();
  });
});

