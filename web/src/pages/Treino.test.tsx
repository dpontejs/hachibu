import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";
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

function renderTreino() {
  return render(
    <MemoryRouter>
      <Treino />
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.useRealTimers();
  vi.restoreAllMocks();
});

describe("Treino", () => {
  it("sem plano, oferece montar e mostra a semana depois", async () => {
    let temPlano = false;
    const chamadas = servidor((u, init) => {
      if (u === "/api/plano" && init?.method !== "POST") return temPlano ? json(PLANO) : json({ detail: "plano_inexistente" }, 404);
      if (u === "/api/plano/base" && init?.method === "POST") {
        temPlano = true;
        return json(null, 201);
      }
    });
    const user = userEvent.setup();
    renderTreino();
    await user.click(await screen.findByRole("button", { name: /montar meu plano/i }));
    expect(await screen.findAllByText("Corpo inteiro A")).not.toHaveLength(0);
    expect(chamadas.some((c) => c.url === "/api/plano/base" && c.init?.method === "POST")).toBe(true);
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

  it("perfil mudou: gerar novo plano base pede confirmação", async () => {
    const chamadas = servidor((u, init) => {
      if (u === "/api/plano" && init?.method !== "POST") return json({ ...PLANO, avisos: ["segunda: Supino precisa de outro equipamento"] });
      if (u.startsWith("/api/plano/base")) return json(null, 201);
    });
    const confirmar = vi.spyOn(window, "confirm").mockReturnValueOnce(false).mockReturnValueOnce(true);
    const user = userEvent.setup();
    renderTreino();
    expect(await screen.findByText(/precisa de outro equipamento/)).toBeInTheDocument();
    const botao = screen.getByRole("button", { name: /gerar novo plano base/i });
    await user.click(botao);
    expect(chamadas.some((c) => c.url.startsWith("/api/plano/base"))).toBe(false);
    await user.click(botao);
    await waitFor(() =>
      expect(chamadas.some((c) => c.url === "/api/plano/base?substituir=true" && c.init?.method === "POST")).toBe(true),
    );
    expect(confirmar).toHaveBeenCalledTimes(2);
  });
});
