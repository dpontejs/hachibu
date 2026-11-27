import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { beforeEach, describe, expect, it, vi } from "vitest";
import Coach, { CHAVE_THREAD } from "./Coach";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const HOJE = {
  data: "2026-11-26",
  metas: { kcal: 2200, proteina_g: 150, carbo_g: 240, gordura_g: 70, agua_ml: 2800, origem: "formula" },
  consumido: { kcal: 0, proteina_g: 0, carbo_g: 0, gordura_g: 0 },
  agua_ml: 0,
  refeicoes: [],
};

const PENDENTE = {
  ferramenta: "ajustar_metas",
  args: { kcal: 2000, proteina_g: 160, justificativa: "Três semanas sem perder peso com a meta atual." },
  descricao: "Ajustar a meta para 2000 kcal e 160 g de proteína.",
};

type Chamada = { url: string; init?: RequestInit };

function mockFetch(rotas: (url: string, init?: RequestInit) => Response | undefined) {
  const chamadas: Chamada[] = [];
  const fn = vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
    const u = String(url);
    chamadas.push({ url: u, init });
    return rotas(u, init) ?? (u === "/api/hoje" ? json(HOJE) : json({ detail: "Not Found" }, 404));
  });
  vi.stubGlobal("fetch", fn);
  return chamadas;
}

function renderCoach() {
  return render(
    <MemoryRouter>
      <Coach />
    </MemoryRouter>,
  );
}

beforeEach(() => {
  localStorage.clear();
});

describe("Coach", () => {
  it("envia a mensagem e mostra a resposta com os chips das ferramentas", async () => {
    const chamadas = mockFetch((u, init) => {
      if (u === "/api/coach" && init?.method === "POST")
        return json({
          thread_id: "t-1",
          mensagens: [
            { papel: "usuario", texto: "como está meu dia?", ferramentas: [] },
            {
              papel: "coach",
              texto: "Faltam 900 kcal. Bora de frango no jantar.",
              ferramentas: ["ler_dia", "skill:corrida"],
            },
          ],
          pendente: null,
        });
    });
    const user = userEvent.setup();
    renderCoach();

    await user.type(screen.getByRole("textbox", { name: /mensagem para o coach/i }), "como está meu dia?");
    await user.click(screen.getByRole("button", { name: /enviar/i }));

    expect(await screen.findByText("Faltam 900 kcal. Bora de frango no jantar.")).toBeInTheDocument();
    const chips = screen.getByRole("list", { name: /ferramentas usadas/i });
    expect(within(chips).getByText("ler dia")).toBeInTheDocument();
    const skill = within(chips).getByText("skill corrida");
    expect(skill.closest("li")).toHaveClass("chip--skill");

    const post = chamadas.find((c) => c.url === "/api/coach");
    expect(post?.init?.body).toBeInstanceOf(FormData);
    expect((post!.init!.body as FormData).get("mensagem")).toBe("como está meu dia?");
    expect(localStorage.getItem(CHAVE_THREAD)).toBe("t-1");
  });

  it("anexa a foto e manda foto e mensagem padrão no multipart", async () => {
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:previa", revokeObjectURL: () => {} }));
    const chamadas = mockFetch((u, init) => {
      if (u === "/api/coach" && init?.method === "POST")
        return json({
          thread_id: "t-2",
          mensagens: [
            { papel: "usuario", texto: "Registra essa refeição", ferramentas: [] },
            { papel: "coach", texto: "Vi arroz, feijão e frango. Confere?", ferramentas: ["analisar_foto"] },
          ],
          pendente: null,
        });
    });
    const user = userEvent.setup();
    renderCoach();

    const foto = new File(["jpeg"], "prato.jpg", { type: "image/jpeg" });
    await user.upload(screen.getByLabelText(/foto da refeição/i), foto);
    expect(screen.getByRole("img", { name: /prévia da foto/i })).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /enviar/i }));
    expect(await screen.findByText("Vi arroz, feijão e frango. Confere?")).toBeInTheDocument();

    const corpo = chamadas.find((c) => c.url === "/api/coach")!.init!.body as FormData;
    expect(corpo).toBeInstanceOf(FormData);
    expect(corpo.get("mensagem")).toBe("Registra essa refeição");
    expect((corpo.get("foto") as File).name).toBe("prato.jpg");
    expect(screen.queryByRole("img", { name: /prévia da foto/i })).not.toBeInTheDocument();
  });

  it("recarrega a conversa salva e manda o thread_id junto", async () => {
    localStorage.setItem(CHAVE_THREAD, "t-velho");
    const chamadas = mockFetch((u, init) => {
      if (u === "/api/coach/t-velho" && (!init?.method || init.method === "GET"))
        return json({
          thread_id: "t-velho",
          mensagens: [{ papel: "coach", texto: "Ontem você bateu a proteína.", ferramentas: [] }],
          pendente: null,
        });
      if (u === "/api/coach" && init?.method === "POST")
        return json({ thread_id: "t-velho", mensagens: [], pendente: null });
    });
    const user = userEvent.setup();
    renderCoach();

    expect(await screen.findByText("Ontem você bateu a proteína.")).toBeInTheDocument();
    await user.type(screen.getByRole("textbox", { name: /mensagem para o coach/i }), "e hoje?");
    await user.click(screen.getByRole("button", { name: /enviar/i }));
    await waitFor(() => expect(chamadas.some((c) => c.url === "/api/coach")).toBe(true));
    const corpo = chamadas.find((c) => c.url === "/api/coach")!.init!.body as FormData;
    expect(corpo.get("thread_id")).toBe("t-velho");
  });

  it("thread de outro usuário (404) vira conversa nova", async () => {
    localStorage.setItem(CHAVE_THREAD, "t-alheio");
    mockFetch(() => undefined);
    renderCoach();
    await waitFor(() => expect(localStorage.getItem(CHAVE_THREAD)).toBeNull());
  });

  it("nova conversa limpa o thread", async () => {
    localStorage.setItem(CHAVE_THREAD, "t-1");
    mockFetch((u) => {
      if (u === "/api/coach/t-1")
        return json({
          thread_id: "t-1",
          mensagens: [{ papel: "coach", texto: "Oi de novo.", ferramentas: [] }],
          pendente: null,
        });
    });
    const user = userEvent.setup();
    renderCoach();
    expect(await screen.findByText("Oi de novo.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /nova conversa/i }));
    expect(screen.queryByText("Oi de novo.")).not.toBeInTheDocument();
    expect(localStorage.getItem(CHAVE_THREAD)).toBeNull();
  });

  describe("aprovação", () => {
    function comPendencia(depois: (corpo: unknown) => Response) {
      localStorage.setItem(CHAVE_THREAD, "t-9");
      return mockFetch((u, init) => {
        if (u === "/api/coach/t-9")
          return json({
            thread_id: "t-9",
            mensagens: [{ papel: "coach", texto: "Proponho baixar a meta.", ferramentas: ["ler_historico"] }],
            pendente: PENDENTE,
          });
        if (u === "/api/coach/t-9/decisao" && init?.method === "POST") return depois(JSON.parse(String(init.body)));
      });
    }

    it("mostra meta atual → proposta e Aprovar manda {aprovar:true}", async () => {
      const chamadas = comPendencia(() =>
        json({
          thread_id: "t-9",
          mensagens: [
            { papel: "coach", texto: "Proponho baixar a meta.", ferramentas: ["ler_historico"] },
            { papel: "coach", texto: "Meta ajustada para 2000 kcal.", ferramentas: ["ajustar_metas"] },
          ],
          pendente: null,
        }),
      );
      const user = userEvent.setup();
      renderCoach();

      const card = await screen.findByRole("region", { name: /pedido de ajuste/i });
      expect(within(card).getByText("Três semanas sem perder peso com a meta atual.")).toBeInTheDocument();
      expect(await within(card).findByLabelText("kcal atual")).toHaveTextContent("2200");
      expect(within(card).getByLabelText("kcal proposta")).toHaveTextContent("2000");
      expect(screen.getByRole("textbox", { name: /mensagem para o coach/i })).toBeDisabled();

      await user.click(within(card).getByRole("button", { name: /^aprovar$/i }));

      expect(await screen.findByText("Meta ajustada para 2000 kcal.")).toBeInTheDocument();
      const decisao = chamadas.find((c) => c.url === "/api/coach/t-9/decisao");
      expect(JSON.parse(String(decisao!.init!.body))).toEqual({ aprovar: true });
      expect(screen.queryByRole("region", { name: /pedido de ajuste/i })).not.toBeInTheDocument();
    });

    it("Recusar com motivo manda {aprovar:false, motivo}", async () => {
      const chamadas = comPendencia(() =>
        json({
          thread_id: "t-9",
          mensagens: [{ papel: "coach", texto: "Beleza, mantive a meta.", ferramentas: [] }],
          pendente: null,
        }),
      );
      const user = userEvent.setup();
      renderCoach();

      const card = await screen.findByRole("region", { name: /pedido de ajuste/i });
      await user.click(within(card).getByRole("button", { name: /^recusar$/i }));
      await user.type(within(card).getByRole("textbox", { name: /motivo/i }), "semana de festa");
      await user.click(within(card).getByRole("button", { name: /confirmar recusa/i }));

      expect(await screen.findByText("Beleza, mantive a meta.")).toBeInTheDocument();
      const decisao = chamadas.find((c) => c.url === "/api/coach/t-9/decisao");
      expect(JSON.parse(String(decisao!.init!.body))).toEqual({ aprovar: false, motivo: "semana de festa" });
    });
  });

  it("429 mostra a mensagem de cota e devolve o texto ao campo", async () => {
    mockFetch((u) => (u === "/api/coach" ? json({ detail: "cota_do_coach" }, 429) : undefined));
    const user = userEvent.setup();
    renderCoach();

    const campo = screen.getByRole("textbox", { name: /mensagem para o coach/i });
    await user.type(campo, "mais uma");
    await user.click(screen.getByRole("button", { name: /enviar/i }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "Você usou todas as mensagens do coach de hoje. Volta amanhã!",
    );
    expect(campo).toHaveValue("mais uma");
  });

  it("422 com texto do servidor mostra o texto (ex.: foto grande)", async () => {
    mockFetch((u) => (u === "/api/coach" ? json({ detail: "foto maior que 5 MB" }, 422) : undefined));
    const user = userEvent.setup();
    renderCoach();
    await user.type(screen.getByRole("textbox", { name: /mensagem para o coach/i }), "oi");
    await user.click(screen.getByRole("button", { name: /enviar/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent("foto maior que 5 MB");
  });

  it("409 de aprovação pendente pede para responder o card", async () => {
    mockFetch((u) => (u === "/api/coach" ? json({ detail: "aprovacao_pendente" }, 409) : undefined));
    const user = userEvent.setup();
    renderCoach();
    await user.type(screen.getByRole("textbox", { name: /mensagem para o coach/i }), "oi");
    await user.click(screen.getByRole("button", { name: /enviar/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(/responda o pedido/i);
  });

  it("503 mostra que o coach está fora do ar", async () => {
    mockFetch((u) => (u === "/api/coach" ? json({ detail: "coach_indisponivel" }, 503) : undefined));
    const user = userEvent.setup();
    renderCoach();
    await user.type(screen.getByRole("textbox", { name: /mensagem para o coach/i }), "oi");
    await user.click(screen.getByRole("button", { name: /enviar/i }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "O coach está fora do ar agora. Registre manualmente e tente mais tarde.",
    );
  });

  it("mostra 'pensando' enquanto espera", async () => {
    let soltar: (r: Response) => void = () => {};
    vi.stubGlobal(
      "fetch",
      vi.fn((url: RequestInfo | URL) =>
        String(url) === "/api/coach"
          ? new Promise<Response>((r) => (soltar = r))
          : Promise.resolve(json({ detail: "Not Found" }, 404)),
      ),
    );
    const user = userEvent.setup();
    renderCoach();
    await user.type(screen.getByRole("textbox", { name: /mensagem para o coach/i }), "oi");
    await user.click(screen.getByRole("button", { name: /enviar/i }));
    expect(await screen.findByText(/pensando/i)).toBeInTheDocument();
    expect(screen.getByText("oi")).toBeInTheDocument();
    soltar(
      json({
        thread_id: "t",
        mensagens: [
          { papel: "usuario", texto: "oi", ferramentas: [] },
          { papel: "coach", texto: "Opa!", ferramentas: [] },
        ],
        pendente: null,
      }),
    );
    expect(await screen.findByText("Opa!")).toBeInTheDocument();
    expect(screen.queryByText(/pensando/i)).not.toBeInTheDocument();
  });
});
