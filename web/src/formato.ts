// Datas e números no jeito brasileiro. O fuso é sempre o de Brasília, mesmo que
// o aparelho esteja em outro (o "dia" do diário é o do servidor, APP_TZ).

export const FUSO = "America/Sao_Paulo";

const DIAS = ["DOM", "SEG", "TER", "QUA", "QUI", "SEX", "SÁB"];
const MESES = ["JAN", "FEV", "MAR", "ABR", "MAI", "JUN", "JUL", "AGO", "SET", "OUT", "NOV", "DEZ"];

/** "2026-11-26" → "QUI · 26 NOV". A data já vem no fuso certo; não converte. */
export function rotuloDoDia(iso: string): string {
  const [a, m, d] = iso.split("-").map(Number);
  const data = new Date(Date.UTC(a, m - 1, d));
  return `${DIAS[data.getUTCDay()]} · ${d} ${MESES[m - 1]}`;
}

/** Hora (0–23) agora em Brasília. */
export function horaEmBrasilia(agora: Date = new Date()): number {
  const h = new Intl.DateTimeFormat("pt-BR", {
    hour: "numeric",
    hourCycle: "h23",
    timeZone: FUSO,
  }).format(agora);
  return Number(h);
}

export function saudacao(agora: Date = new Date()): string {
  const h = horaEmBrasilia(agora);
  if (h >= 5 && h < 12) return "Bom dia";
  if (h >= 12 && h < 18) return "Boa tarde";
  return "Boa noite";
}

/** "2026-11-26T15:30:00Z" → "12:30" (Brasília). */
export function horaMinuto(iso: string): string {
  const data = new Date(iso);
  if (Number.isNaN(data.getTime())) return "";
  return new Intl.DateTimeFormat("pt-BR", {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: FUSO,
  }).format(data);
}

/** 1500 → "1,5"; 3000 → "3". */
export function litros(ml: number): string {
  return new Intl.NumberFormat("pt-BR", { maximumFractionDigits: 1 }).format(ml / 1000);
}

/** 1.55 → "1,55"; com `casas`, fixa as casas decimais (0.5 → "0,50"). */
export function decimal(n: number, casas?: number): string {
  return new Intl.NumberFormat("pt-BR", {
    minimumFractionDigits: casas ?? 0,
    maximumFractionDigits: casas ?? 2,
  }).format(n);
}

/** De onde veio a meta, do jeito que o usuário fala. */
export function rotuloOrigem(origem: string | undefined): string {
  if (origem === "profissional") return "seu nutricionista";
  if (origem === "coach") return "ajuste do coach";
  return "fórmula";
}

export function porcento(valor: number, meta: number): number {
  if (!meta || meta <= 0) return 0;
  return Math.max(0, Math.min(100, (valor / meta) * 100));
}
