// Peças do coach usadas fora dele (Shell, Comida): chave do thread, evento
// "abrir com câmera" e a consulta de layout que decide painel × tela cheia.
import { useEffect, useState } from "react";

export const CHAVE_THREAD = "hachibu.coach.thread";
/** Disparado no desktop, onde o coach já está montado no painel lateral. */
export const EVENTO_FOTO = "hachibu:coach-foto";

const CONSULTA_DESKTOP = "(min-width: 1024px)";

export function ehDesktop(): boolean {
  return typeof window !== "undefined" && typeof window.matchMedia === "function"
    ? window.matchMedia(CONSULTA_DESKTOP).matches
    : false;
}

/** Acompanha o breakpoint do painel fixo (mesmo valor do theme.css). */
export function useDesktop(): boolean {
  const [desktop, setDesktop] = useState(ehDesktop);
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(CONSULTA_DESKTOP);
    const mudar = () => setDesktop(mq.matches);
    mudar();
    mq.addEventListener("change", mudar);
    return () => mq.removeEventListener("change", mudar);
  }, []);
  return desktop;
}

/**
 * "Por foto": no desktop abre o seletor no painel (ainda dentro do clique, para o
 * navegador permitir); no celular leva para /coach com a câmera pedida.
 */
export function abrirCoachPorFoto(navegar: (para: string) => void): void {
  if (ehDesktop()) window.dispatchEvent(new Event(EVENTO_FOTO));
  else navegar("/coach?foto=1");
}

export function lerThread(): string | null {
  try {
    return localStorage.getItem(CHAVE_THREAD);
  } catch {
    return null;
  }
}

export function gravarThread(id: string | null): void {
  try {
    if (id) localStorage.setItem(CHAVE_THREAD, id);
    else localStorage.removeItem(CHAVE_THREAD);
  } catch {
    /* modo privado: a conversa só não sobrevive ao recarregar */
  }
}
