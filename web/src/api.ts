// Cliente da API do Hachibu. Uma função tipada por rota (contrato: plano
// 2026-11-26-estrutura-inicial, Tasks 3–5; 2026-11-27-refeicoes-taco, Tasks 2–4).
// Toda chamada leva o cookie de sessão.
//
// Regras globais:
// - 401 fora do login → vai para /entrar.
// - 409 {"detail":"perfil_incompleto"} → vai para /perfil.
// - 422 → ApiError com `campos` (campo → mensagem) para o formulário mostrar.

export type Sexo = "M" | "F";
export type Objetivo = "perder" | "manter" | "ganhar";
export type Nivel = "iniciante" | "intermediario" | "avancado";
export type Equipamento = "academia" | "casa_halteres" | "peso_corporal";

export interface Perfil {
  sexo: Sexo;
  idade: number;
  altura_cm: number;
  peso_kg: number;
  objetivo: Objetivo;
  nivel: Nivel;
  dias_semana: number;
  minutos_sessao: number;
  equipamento: Equipamento;
  percentual_gordura?: number | null;
  cintura_cm?: number | null;
  condicoes_saude?: string | null;
  /** Meta prescrita por nutricionista: quando há kcal, ela substitui a fórmula. */
  meta_profissional_kcal?: number | null;
  meta_profissional_proteina_g?: number | null;
  meta_profissional_carbo_g?: number | null;
  meta_profissional_gordura_g?: number | null;
}

/** De onde veio a meta do dia. */
export type OrigemMeta = "formula" | "profissional" | "coach";

export interface Metas {
  kcal: number;
  proteina_g: number;
  carbo_g: number;
  gordura_g: number;
  agua_ml: number;
  /** Opcional só para tolerar respostas antigas; o servidor novo sempre manda. */
  origem?: OrigemMeta;
}

export interface PerfilComMetas {
  perfil: Perfil;
  metas: Metas;
}

export interface Me {
  email: string;
  perfil_completo: boolean;
}

export interface Consumido {
  kcal: number;
  proteina_g: number;
  carbo_g: number;
  gordura_g: number;
}

export interface ItemRefeicao {
  nome: string;
  gramas: number;
  kcal: number;
}

export interface RefeicaoResumo {
  id: number;
  nome: string;
  kcal: number;
  criado_em: string;
  /** Itens da TACO; refeição manual vem com lista vazia. */
  itens?: ItemRefeicao[];
}

export interface Hoje {
  data: string; // AAAA-MM-DD, já no fuso de Brasília
  metas: Metas;
  consumido: Consumido;
  agua_ml: number;
  refeicoes: RefeicaoResumo[];
}

export interface RefeicaoIn {
  nome: string;
  kcal: number;
  proteina_g: number;
  carbo_g: number;
  gordura_g: number;
}

/** Alimento da TACO; valores por 100 g. */
export interface Alimento {
  id: number;
  nome: string;
  categoria: string;
  kcal: number;
  proteina_g: number;
  carbo_g: number;
  gordura_g: number;
}

/** Refeição montada com a TACO: o servidor calcula kcal e macros. */
export interface RefeicaoTacoIn {
  nome: string;
  itens: { alimento_id: number; gramas: number }[];
}

export interface Diagnostico {
  tmb: number;
  formula: "mifflin-st-jeor" | "katch-mcardle";
  fator_atividade: number;
  gasto_diario: number;
  ajuste_objetivo: number;
  relacao_cintura_altura: number | null;
  alerta_cintura: boolean;
  abaixo_do_piso: boolean;
  metas: Metas;
}

// ---------- coach (plano 2026-11-27-coach-agente, Task 5) ----------

export interface MensagemCoach {
  papel: "usuario" | "coach";
  texto: string;
  /** Tools usadas para produzir a resposta; `skill:<nome>` para skills carregadas. */
  ferramentas: string[];
}

export interface ArgsAjusteMetas {
  kcal: number;
  proteina_g?: number;
  carbo_g?: number;
  gordura_g?: number;
  justificativa: string;
}

/** Ação que espera aprovação do aluno (hoje só `ajustar_metas`). */
export interface PendenciaCoach {
  ferramenta: string;
  args: Record<string, unknown>;
  descricao: string;
}

export interface RespostaCoach {
  thread_id: string;
  /** A conversa inteira da thread. */
  mensagens: MensagemCoach[];
  pendente: PendenciaCoach | null;
}

export class ApiError extends Error {
  readonly status: number;
  readonly detail: unknown;
  /** Para 422: campo do corpo → primeira mensagem de erro. */
  readonly campos: Record<string, string>;

  constructor(status: number, detail: unknown) {
    super(typeof detail === "string" ? detail : `HTTP ${status}`);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.campos = status === 422 ? extrairCampos(detail) : {};
  }
}

/** Lançado depois de redirecionar (401/409); quem chamou só precisa parar. */
export class Redirecionado extends Error {
  readonly para: string;
  constructor(para: string) {
    super(`redirecionado para ${para}`);
    this.name = "Redirecionado";
    this.para = para;
  }
}

type Navegar = (para: string) => void;

let navegar: Navegar = (para) => {
  if (window.location.pathname !== para) window.location.assign(para);
};

/** O app registra o `navigate` do react-router para redirecionar sem recarregar. */
export function definirNavegacao(fn: Navegar): void {
  navegar = fn;
}

function extrairCampos(detail: unknown): Record<string, string> {
  const campos: Record<string, string> = {};
  if (!Array.isArray(detail)) return campos;
  for (const erro of detail) {
    if (!erro || typeof erro !== "object") continue;
    const { loc, msg, type, ctx } = erro as { loc?: unknown; msg?: unknown; type?: unknown; ctx?: unknown };
    if (!Array.isArray(loc) || typeof msg !== "string") continue;
    const campo = String(loc[loc.length - 1] ?? "");
    if (campo && !(campo in campos)) campos[campo] = traduzir(msg, type, ctx);
  }
  return campos;
}

/** Mensagens do pydantic em pt-BR; tipo desconhecido fica com a mensagem original. */
function traduzir(msg: string, type: unknown, ctx: unknown): string {
  const c = (ctx && typeof ctx === "object" ? ctx : {}) as Record<string, unknown>;
  switch (type) {
    case "greater_than_equal":
      return `mínimo ${String(c.ge)}`;
    case "greater_than":
      return `maior que ${String(c.gt)}`;
    case "missing":
      return "obrigatório";
    case "int_from_float":
    case "int_parsing":
      return "use um número inteiro";
    case "less_than_equal":
      return `máximo ${String(c.le)}`;
    case "string_too_short":
      return "muito curto";
    case "literal_error":
      return "opção inválida";
    case "value_error":
      return msg.replace(/^Value error, /, "");
    default:
      return msg;
  }
}

interface Opcoes {
  /** No login, 401 é "senha errada", não "sessão expirada". */
  sem401Redirect?: boolean;
}

async function request<T>(
  method: string,
  caminho: string,
  corpo?: unknown,
  opcoes: Opcoes = {},
): Promise<T> {
  const init: RequestInit = { method, credentials: "include", headers: {} };
  if (corpo instanceof FormData) {
    // O navegador monta o Content-Type com o boundary do multipart.
    init.body = corpo;
  } else if (corpo !== undefined) {
    init.headers = { "Content-Type": "application/json" };
    init.body = JSON.stringify(corpo);
  }
  const resp = await fetch(`/api${caminho}`, init);

  if (resp.status === 204) return undefined as T;

  let dados: unknown = null;
  const texto = await resp.text();
  if (texto) {
    try {
      dados = JSON.parse(texto);
    } catch {
      dados = texto;
    }
  }

  if (resp.ok) return dados as T;

  const detail =
    dados && typeof dados === "object" && "detail" in dados
      ? (dados as { detail: unknown }).detail
      : dados;

  if (resp.status === 401 && !opcoes.sem401Redirect) {
    navegar("/entrar");
    throw new Redirecionado("/entrar");
  }
  if (resp.status === 409 && detail === "perfil_incompleto") {
    navegar("/perfil");
    throw new Redirecionado("/perfil");
  }
  throw new ApiError(resp.status, detail);
}

export const api = {
  signup: (email: string, senha: string, convite: string) =>
    request<unknown>("POST", "/auth/signup", { email, senha, convite }, { sem401Redirect: true }),
  login: (email: string, senha: string) =>
    request<unknown>("POST", "/auth/login", { email, senha }, { sem401Redirect: true }),
  logout: () => request<void>("POST", "/auth/logout"),
  me: () => request<Me>("GET", "/me"),
  /** `null` quando ainda não há perfil (404). */
  async getPerfil(): Promise<{ perfil: Perfil; metas: Metas | null } | null> {
    try {
      const dados = await request<PerfilComMetas | Perfil>("GET", "/perfil");
      // O contrato só fixa 200/404; aceita `{perfil, metas}` ou o perfil puro.
      if (dados && "perfil" in dados) return dados;
      return { perfil: dados, metas: null };
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },
  putPerfil: (perfil: Perfil) => request<PerfilComMetas>("PUT", "/perfil", perfil),
  hoje: () => request<Hoje>("GET", "/hoje"),
  addRefeicao: (r: RefeicaoIn) => request<unknown>("POST", "/refeicoes", r),
  addAgua: (ml: number) => request<unknown>("POST", "/agua", { ml }),
  buscarAlimentos: (q: string) => request<Alimento[]>("GET", `/alimentos?q=${encodeURIComponent(q)}`),
  addRefeicaoTaco: (r: RefeicaoTacoIn) => request<unknown>("POST", "/refeicoes", r),
  diagnostico: () => request<Diagnostico>("GET", "/diagnostico"),
  coachEnviar(mensagem: string, foto?: File | Blob | null, threadId?: string | null) {
    const corpo = new FormData();
    corpo.append("mensagem", mensagem);
    if (foto) corpo.append("foto", foto, foto instanceof File ? foto.name : "foto.jpg");
    if (threadId) corpo.append("thread_id", threadId);
    return request<RespostaCoach>("POST", "/coach", corpo);
  },
  coachDecidir: (threadId: string, aprovar: boolean, motivo?: string) =>
    request<RespostaCoach>(
      "POST",
      `/coach/${encodeURIComponent(threadId)}/decisao`,
      motivo?.trim() ? { aprovar, motivo: motivo.trim() } : { aprovar },
    ),
  /** `null` quando a thread não existe ou não é do usuário (404): vira conversa nova. */
  async coachHistorico(threadId: string): Promise<RespostaCoach | null> {
    try {
      return await request<RespostaCoach>("GET", `/coach/${encodeURIComponent(threadId)}`);
    } catch (e) {
      if (e instanceof ApiError && e.status === 404) return null;
      throw e;
    }
  },
};

export const MSG_COTA_COACH = "Você usou todas as mensagens do coach de hoje. Volta amanhã!";
export const MSG_COACH_FORA = "O coach está fora do ar agora. Registre manualmente e tente mais tarde.";

/** Mensagem curta para mostrar ao usuário; `null` se foi só um redirecionamento. */
export function mensagemDeErro(e: unknown): string | null {
  if (e instanceof Redirecionado) return null;
  if (e instanceof ApiError) {
    if (e.status === 429 && e.detail === "cota_do_coach") return MSG_COTA_COACH;
    if (e.status === 503 && e.detail === "coach_indisponivel") return MSG_COACH_FORA;
    if (e.status === 409 && e.detail === "aprovacao_pendente")
      return "Responda o pedido acima (aprovar ou recusar) antes de mandar outra mensagem.";
    if (e.status === 422) return typeof e.detail === "string" ? e.detail : "Confira os campos destacados.";
    if (e.status === 429) return "Muitas tentativas. Espere alguns minutos.";
    if (e.status >= 500) return "O servidor tropeçou. Tente de novo.";
    return typeof e.detail === "string" ? e.detail : e.message;
  }
  return "Sem conexão com o servidor.";
}
