import { describe, expect, it, vi } from "vitest";
import { api, ApiError, definirNavegacao, Redirecionado } from "./api";

function resposta(status: number, body?: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function prepara(status: number, body?: unknown) {
  const fetchMock = vi.fn(async () => resposta(status, body));
  vi.stubGlobal("fetch", fetchMock);
  const navegar = vi.fn();
  definirNavegacao(navegar);
  return { fetchMock, navegar };
}

describe("api", () => {
  it("manda o cookie e o prefixo /api", async () => {
    const { fetchMock } = prepara(200, { email: "a@b.c", perfil_completo: true });
    await expect(api.me()).resolves.toEqual({ email: "a@b.c", perfil_completo: true });
    expect(fetchMock).toHaveBeenCalledWith("/api/me", expect.objectContaining({ credentials: "include" }));
  });

  it("401 leva para /entrar", async () => {
    const { navegar } = prepara(401, { detail: "nao_autenticado" });
    await expect(api.hoje()).rejects.toBeInstanceOf(Redirecionado);
    expect(navegar).toHaveBeenCalledWith("/entrar");
  });

  it("401 no login é senha errada, sem redirecionar", async () => {
    const { navegar } = prepara(401, { detail: "credenciais_invalidas" });
    const erro = (await api.login("a@b.c", "12345678").catch((e) => e)) as ApiError;
    expect(erro).toBeInstanceOf(ApiError);
    expect(erro.status).toBe(401);
    expect(navegar).not.toHaveBeenCalled();
  });

  it("409 perfil_incompleto leva para /perfil", async () => {
    const { navegar } = prepara(409, { detail: "perfil_incompleto" });
    await expect(api.hoje()).rejects.toBeInstanceOf(Redirecionado);
    expect(navegar).toHaveBeenCalledWith("/perfil");
  });

  it("outro 409 (e-mail repetido) não redireciona", async () => {
    const { navegar } = prepara(409, { detail: "email_ja_cadastrado" });
    const erro = await api.signup("a@b.c", "12345678", "x").catch((e) => e);
    expect(erro).toBeInstanceOf(ApiError);
    expect(navegar).not.toHaveBeenCalled();
  });

  it("422 expõe as mensagens por campo", async () => {
    prepara(422, {
      detail: [
        { loc: ["body", "altura_cm"], msg: "Input should be greater than or equal to 120", type: "x" },
        { loc: ["body", "peso_kg"], msg: "Input should be less than or equal to 250", type: "x" },
      ],
    });
    const erro = (await api.addAgua(0).catch((e) => e)) as ApiError;
    expect(erro.status).toBe(422);
    expect(erro.campos).toEqual({
      altura_cm: "Input should be greater than or equal to 120",
      peso_kg: "Input should be less than or equal to 250",
    });
  });

  it("204 no logout resolve sem corpo", async () => {
    prepara(204);
    await expect(api.logout()).resolves.toBeUndefined();
  });

  it("GET /perfil 404 vira null", async () => {
    prepara(404, { detail: "Not Found" });
    await expect(api.getPerfil()).resolves.toBeNull();
  });
});

describe("422 em pt-BR", () => {
  it("traduz os tipos de erro do pydantic", async () => {
    prepara(422, {
      detail: [
        {
          loc: ["body", "altura_cm"],
          msg: "Input should be greater than or equal to 120",
          type: "greater_than_equal",
          ctx: { ge: 120 },
        },
        {
          loc: ["body", "peso_kg"],
          msg: "Input should be less than or equal to 250",
          type: "less_than_equal",
          ctx: { le: 250 },
        },
        {
          loc: ["body", "nome"],
          msg: "String should have at least 1 character",
          type: "string_too_short",
          ctx: { min_length: 1 },
        },
        { loc: ["body", "sexo"], msg: "Input should be 'M' or 'F'", type: "literal_error", ctx: { expected: "'M' or 'F'" } },
        { loc: ["body", "itens", 0, "alimento_id"], msg: "Value error, alimento inexistente", type: "value_error" },
        { loc: ["body", "outro"], msg: "Field required", type: "missing" },
      ],
    });
    const erro = (await api.addAgua(0).catch((e) => e)) as ApiError;
    expect(erro.campos).toEqual({
      altura_cm: "mínimo 120",
      peso_kg: "máximo 250",
      nome: "muito curto",
      sexo: "opção inválida",
      alimento_id: "alimento inexistente",
      outro: "Field required",
    });
  });
});

describe("rotas da TACO e do diagnóstico", () => {
  it("buscarAlimentos codifica a consulta", async () => {
    const { fetchMock } = prepara(200, []);
    await api.buscarAlimentos("pão francês");
    expect(fetchMock).toHaveBeenCalledWith(
      `/api/alimentos?q=${encodeURIComponent("pão francês")}`,
      expect.objectContaining({ method: "GET" }),
    );
  });

  it("addRefeicaoTaco manda só alimento_id e gramas", async () => {
    const { fetchMock } = prepara(201, { id: 1 });
    await api.addRefeicaoTaco({ nome: "Almoço", itens: [{ alimento_id: 1, gramas: 150 }] });
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/refeicoes");
    expect(JSON.parse(String(init.body))).toEqual({ nome: "Almoço", itens: [{ alimento_id: 1, gramas: 150 }] });
  });

  it("diagnostico chama GET /api/diagnostico", async () => {
    const { fetchMock } = prepara(200, { tmb: 1780 });
    await expect(api.diagnostico()).resolves.toEqual({ tmb: 1780 });
    expect((fetchMock.mock.calls[0] as unknown as [string])[0]).toBe("/api/diagnostico");
  });
});
