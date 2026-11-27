import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import Perfil from "./Perfil";

function json(body: unknown, status = 200): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

const PERFIL = {
  sexo: "M",
  idade: 30,
  altura_cm: 180,
  peso_kg: 80,
  objetivo: "manter",
  nivel: "intermediario",
  dias_semana: 4,
  minutos_sessao: 60,
  equipamento: "academia",
};
const METAS = { kcal: 2759, proteina_g: 144, carbo_g: 402, gordura_g: 64, agua_ml: 2800, origem: "formula" };

describe("Perfil", () => {
  it("manda as preferências de corrida (e vazio quando não escolhidas)", async () => {
    const corpos: unknown[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: RequestInfo | URL, init?: RequestInit) => {
        const u = String(url);
        if (u === "/api/perfil" && init?.method === "PUT") {
          corpos.push(JSON.parse(String(init.body)));
          return json({ perfil: PERFIL, metas: METAS });
        }
        if (u === "/api/perfil") return json({ perfil: PERFIL, metas: METAS });
        if (u === "/api/memorias") return json({ memorias: [] });
        return json({ detail: "Not Found" }, 404);
      }),
    );
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Perfil />
      </MemoryRouter>,
    );
    await user.click(await screen.findByRole("radio", { name: "Depois da musculação" }));
    await user.click(screen.getByRole("radiogroup", { name: "Corridas por semana" }).querySelector('input[value="4"]')!);
    await user.type(screen.getByRole("spinbutton", { name: /minutos de corrida/i }), "35");
    await user.click(screen.getByRole("button", { name: /salvar e recalcular/i }));
    await waitFor(() => expect(corpos).toHaveLength(1));
    expect(corpos[0]).toMatchObject({
      corrida_quando: "mesmo_dia",
      corridas_semana: 4,
      nivel_corrida: null,
      minutos_corrida: 35,
    });
  });
});
