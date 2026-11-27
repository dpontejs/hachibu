import { Fragment, useCallback, useEffect, useRef, useState, type ChangeEvent, type FormEvent, type KeyboardEvent, type ReactNode } from "react";
import { api, ApiError, mensagemDeErro, type ConversaCoach, type MensagemCoach, type PendenciaCoach, type RespostaCoach } from "../api";
import { Icone } from "../ui";
import { EVENTO_FOTO, gravarThread, lerThread } from "./abrir";
import Aprovacao from "./Aprovacao";

export { CHAVE_THREAD } from "./abrir";

export const MENSAGEM_FOTO = "Registra essa refeição";
const LIMITE_TEXTO = 2000;
const LIMITE_FOTO = 5 * 1024 * 1024;
const LADO_MAX_FOTO = 1600;

const SUGESTOES = ["Como está meu dia?", "O que janto para bater a proteína?", "Monta um treino de 30 min"];

/** `ler_dia` → "ler dia"; `skill:corrida` → "skill corrida", marcado como skill. */
export function nomeFerramenta(f: string): { texto: string; skill: boolean } {
  const skill = f.startsWith("skill:");
  const nome = (skill ? f.slice("skill:".length) : f).replace(/_/g, " ").trim();
  return { texto: skill ? `skill ${nome}` : nome, skill };
}

/** Agrupa repetições mantendo a ordem: ["a","b","a"] → [a×2, b×1]. */
function agrupar(ferramentas: string[]): { nome: string; vezes: number }[] {
  const contagem = new Map<string, number>();
  for (const f of ferramentas) contagem.set(f, (contagem.get(f) ?? 0) + 1);
  return [...contagem].map(([nome, vezes]) => ({ nome, vezes }));
}

/** **negrito** dentro de uma linha; o resto vira texto puro (nunca HTML). */
function negrito(linha: string): ReactNode[] {
  return linha.split(/(\*\*[^*]+\*\*)/g).map((parte, i) =>
    parte.startsWith("**") && parte.endsWith("**") && parte.length > 4 ? (
      <strong key={i}>{parte.slice(2, -2)}</strong>
    ) : (
      <Fragment key={i}>{parte}</Fragment>
    ),
  );
}

/** Markdown mínimo do modelo: parágrafos, listas com "-"/"*" e negrito. */
function Texto({ texto }: { texto: string }) {
  const blocos = texto.trim().split(/\n{2,}/);
  return (
    <>
      {blocos.map((bloco, i) => {
        const linhas = bloco.split("\n");
        if (linhas.every((l) => /^\s*[-*•]\s+/.test(l)))
          return (
            <ul key={i}>
              {linhas.map((l, j) => (
                <li key={j}>{negrito(l.replace(/^\s*[-*•]\s+/, ""))}</li>
              ))}
            </ul>
          );
        return (
          <p key={i}>
            {linhas.map((l, j) => (
              <Fragment key={j}>
                {j > 0 && <br />}
                {negrito(l)}
              </Fragment>
            ))}
          </p>
        );
      })}
    </>
  );
}

function Chips({ ferramentas }: { ferramentas: string[] }) {
  if (ferramentas.length === 0) return null;
  return (
    <ul className="chips" aria-label="Ferramentas usadas">
      {agrupar(ferramentas).map(({ nome, vezes }) => {
        const { texto, skill } = nomeFerramenta(nome);
        return (
          <li key={nome} className={skill ? "chip chip--skill px" : "chip px"} title={nome}>
            {texto}
            {vezes > 1 && <span className="chip__vezes">×{vezes}</span>}
          </li>
        );
      })}
    </ul>
  );
}

function criarPrevia(foto: Blob): string | null {
  return typeof URL.createObjectURL === "function" ? URL.createObjectURL(foto) : null;
}

function soltarPrevia(url: string | null) {
  if (url && typeof URL.revokeObjectURL === "function") URL.revokeObjectURL(url);
}

/** Foto de celular acima de 5 MB: reduz para JPEG no navegador antes de mandar. */
async function reduzir(foto: File): Promise<File> {
  const img = await createImageBitmap(foto);
  const escala = Math.min(1, LADO_MAX_FOTO / Math.max(img.width, img.height));
  const canvas = document.createElement("canvas");
  canvas.width = Math.round(img.width * escala);
  canvas.height = Math.round(img.height * escala);
  canvas.getContext("2d")!.drawImage(img, 0, 0, canvas.width, canvas.height);
  img.close();
  const blob = await new Promise<Blob | null>((ok) => canvas.toBlob(ok, "image/jpeg", 0.85));
  if (!blob) throw new Error("sem blob");
  return new File([blob], foto.name.replace(/\.[^.]+$/, "") + ".jpg", { type: "image/jpeg" });
}

function quando(iso: string): string {
  return new Date(iso).toLocaleDateString("pt-BR", { day: "2-digit", month: "2-digit" });
}

function Conversas({
  conversas,
  atual,
  onAbrir,
}: {
  conversas: ConversaCoach[];
  atual: string | null;
  onAbrir: (id: string) => void;
}) {
  if (conversas.length === 0)
    return <p className="mudo coach__sem-conversas">Nenhuma conversa ainda. Mande a primeira mensagem!</p>;
  return (
    <ul className="conversas" aria-label="Conversas anteriores">
      {conversas.map((c) => (
        <li key={c.thread_id}>
          <button
            type="button"
            className={c.thread_id === atual ? "conversa conversa--atual" : "conversa"}
            onClick={() => onAbrir(c.thread_id)}
          >
            <span className="conversa__titulo">{c.titulo}</span>
            <span className="conversa__meta">
              {c.pendente && <span className="conversa__pendente px">FALTA APROVAR</span>}
              <span className="vt">{quando(c.atualizado_em)}</span>
            </span>
          </button>
        </li>
      ))}
    </ul>
  );
}

interface Envio {
  texto: string;
  previa: string | null;
}

/**
 * O coach: o mesmo componente no painel do desktop e em /coach no celular.
 * A conversa vive no servidor; aqui só fica o `thread_id` (localStorage).
 */
export default function Coach({ abrirCamera = false }: { abrirCamera?: boolean }) {
  const [threadId, setThreadId] = useState<string | null>(lerThread);
  const [mensagens, setMensagens] = useState<MensagemCoach[]>([]);
  const [pendente, setPendente] = useState<PendenciaCoach | null>(null);
  const [carregando, setCarregando] = useState(() => lerThread() !== null);
  const [envio, setEnvio] = useState<Envio | null>(null);
  const [decidindo, setDecidindo] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [texto, setTexto] = useState("");
  const [foto, setFoto] = useState<File | null>(null);
  const [previa, setPrevia] = useState<string | null>(null);
  const [previaQuebrada, setPreviaQuebrada] = useState(false);
  const [dicaCamera, setDicaCamera] = useState(abrirCamera);
  const [chamado, setChamado] = useState(false);
  /** `null`: painel na conversa; lista: painel mostrando as conversas anteriores. */
  const [conversas, setConversas] = useState<ConversaCoach[] | null>(null);
  const [listando, setListando] = useState(false);
  /** Cada carregamento de conversa pega um número; só o mais recente pode aplicar o resultado. */
  const geracao = useRef(0);

  const lista = useRef<HTMLDivElement>(null);
  const seletor = useRef<HTMLInputElement>(null);
  const campo = useRef<HTMLTextAreaElement>(null);
  const previaAtual = useRef<string | null>(null);
  previaAtual.current = previa;

  const aplicar = useCallback((r: RespostaCoach) => {
    setThreadId(r.thread_id);
    gravarThread(r.thread_id);
    setMensagens(r.mensagens);
    setPendente(r.pendente);
  }, []);

  const recarregar = useCallback(
    async (id: string, vivo: () => boolean = () => true) => {
      try {
        const r = await api.coachHistorico(id);
        if (!vivo()) return;
        if (r) aplicar(r);
        else {
          // Thread apagada ou de outra conta: segue como conversa nova.
          gravarThread(null);
          setThreadId(null);
          setMensagens([]);
          setPendente(null);
        }
      } catch (e) {
        if (vivo()) setErro(mensagemDeErro(e));
      } finally {
        if (vivo()) setCarregando(false);
      }
    },
    [aplicar],
  );

  useEffect(() => {
    const id = lerThread();
    if (!id) return;
    let vivo = true;
    const minha = geracao.current;
    void recarregar(id, () => vivo && geracao.current === minha);
    return () => {
      vivo = false;
    };
  }, [recarregar]);

  // Câmera pedida pela tela de comida: no celular ao montar, no desktop por evento.
  useEffect(() => {
    if (abrirCamera) seletor.current?.click();
  }, [abrirCamera]);

  useEffect(() => {
    let t = 0;
    function abrir() {
      seletor.current?.click();
      setChamado(true);
      window.clearTimeout(t);
      t = window.setTimeout(() => setChamado(false), 900);
    }
    window.addEventListener(EVENTO_FOTO, abrir);
    return () => {
      window.removeEventListener(EVENTO_FOTO, abrir);
      window.clearTimeout(t);
    };
  }, []);

  useEffect(() => () => soltarPrevia(previaAtual.current), []);

  useEffect(() => {
    const el = lista.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [mensagens, envio, pendente, erro]);

  // A caixa cresce com o texto até ~5 linhas.
  useEffect(() => {
    const el = campo.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 128)}px`;
  }, [texto]);

  function trocarFoto(nova: File | null, url: string | null) {
    if (previa && previa !== url) soltarPrevia(previa);
    setFoto(nova);
    setPrevia(url);
    setPreviaQuebrada(false);
  }

  async function escolherFoto(ev: ChangeEvent<HTMLInputElement>) {
    const escolhida = ev.target.files?.[0];
    ev.target.value = ""; // permite escolher a mesma foto de novo
    if (!escolhida) return;
    setDicaCamera(false);
    setErro(null);
    let final = escolhida;
    if (final.size > LIMITE_FOTO) {
      try {
        final = await reduzir(escolhida);
      } catch {
        final = escolhida;
      }
      if (final.size > LIMITE_FOTO) {
        setErro("Essa foto passa de 5 MB. Tente uma menor ou com menos resolução.");
        return;
      }
    }
    trocarFoto(final, criarPrevia(final));
    campo.current?.focus();
  }

  const ocupado = envio !== null || decidindo;
  const bloqueado = pendente !== null;

  async function enviar(sugestao?: string) {
    const digitado = texto;
    const mensagem = (sugestao ?? digitado).trim().slice(0, LIMITE_TEXTO) || (foto ? MENSAGEM_FOTO : "");
    if (!mensagem || ocupado || bloqueado || listando) return;
    const fotoEnviada = foto;
    const previaEnviada = previa;
    setEnvio({ texto: mensagem, previa: previaEnviada });
    setErro(null);
    setDicaCamera(false);
    if (!sugestao) setTexto("");
    setFoto(null);
    setPrevia(null);
    try {
      aplicar(await api.coachEnviar(mensagem, fotoEnviada, threadId));
      soltarPrevia(previaEnviada);
    } catch (e) {
      setErro(mensagemDeErro(e));
      // Nada se perde: texto e foto voltam para a caixa.
      if (!sugestao) setTexto(digitado);
      setFoto(fotoEnviada);
      setPrevia(previaEnviada);
    } finally {
      setEnvio(null);
    }
  }

  async function decidir(aprovar: boolean, motivo?: string) {
    if (!threadId || decidindo) return;
    setDecidindo(true);
    setErro(null);
    try {
      aplicar(await api.coachDecidir(threadId, aprovar, motivo));
    } catch (e) {
      setErro(mensagemDeErro(e));
      // 409: a pendência já foi resolvida (outra aba?); traz o estado real.
      if (e instanceof ApiError && e.status === 409) {
        const minha = ++geracao.current;
        await recarregar(threadId, () => geracao.current === minha);
      }
    } finally {
      setDecidindo(false);
    }
  }

  function novaConversa() {
    if (ocupado) return;
    geracao.current++;
    gravarThread(null);
    setThreadId(null);
    setMensagens([]);
    setPendente(null);
    setErro(null);
    setCarregando(false);
    trocarFoto(null, null);
    campo.current?.focus();
  }

  async function verConversas() {
    if (ocupado || listando) return;
    setListando(true);
    setErro(null);
    try {
      setConversas((await api.coachConversas()).conversas);
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setListando(false);
    }
  }

  async function abrirConversa(id: string) {
    if (ocupado) return;
    setConversas(null);
    setErro(null);
    if (id === threadId) return; // já é a conversa na tela (ou a que está carregando)
    const minha = ++geracao.current;
    const vivo = () => geracao.current === minha;
    const antes = { mensagens, pendente, carregando };
    setMensagens([]);
    setPendente(null);
    setCarregando(true);
    try {
      const r = await api.coachHistorico(id);
      if (!vivo()) return;
      if (r) {
        aplicar(r);
        setCarregando(false);
        return;
      }
      setErro("Essa conversa não existe mais.");
    } catch (e) {
      if (!vivo()) return;
      setErro(mensagemDeErro(e));
    }
    // Falhou: a tela volta para a conversa de antes, que continua sendo a do threadId.
    setMensagens(antes.mensagens);
    setPendente(antes.pendente);
    if (antes.carregando && threadId) {
      const nova = ++geracao.current;
      await recarregar(threadId, () => geracao.current === nova);
    } else setCarregando(false);
  }

  function aoEnviar(ev: FormEvent) {
    ev.preventDefault();
    void enviar();
  }

  function aoTeclar(ev: KeyboardEvent<HTMLTextAreaElement>) {
    if (ev.key === "Enter" && !ev.shiftKey && !ev.nativeEvent.isComposing) {
      ev.preventDefault();
      void enviar();
    }
  }

  const vazio = mensagens.length === 0 && !envio && !carregando;
  // Sem esperar o histórico carregar, uma mensagem poderia furar uma aprovação pendente.
  const podeEnviar = !ocupado && !bloqueado && !carregando && !listando && (texto.trim() !== "" || foto !== null);

  const topo = (
    <header className="coach__topo">
      <span className="coach__marca">
        <span className="coach__luz" aria-hidden="true" />
        <span className="rotulo px">COACH</span>
      </span>
      <span className="coach__acoes">
        {conversas ? (
          <button type="button" className="coach__nova px" onClick={() => setConversas(null)}>
            VOLTAR
          </button>
        ) : (
          <>
            <button
              type="button"
              className="coach__nova px"
              onClick={() => void verConversas()}
              disabled={ocupado || listando}
            >
              CONVERSAS
            </button>
            {(mensagens.length > 0 || threadId) && (
              <button
                type="button"
                className="coach__nova px"
                aria-label="Nova conversa"
                onClick={novaConversa}
                disabled={ocupado}
              >
                + NOVA
              </button>
            )}
          </>
        )}
      </span>
    </header>
  );

  if (conversas)
    return (
      <div className="coach">
        {topo}
        <div className="coach__lista">
          <Conversas conversas={conversas} atual={threadId} onAbrir={(id) => void abrirConversa(id)} />
        </div>
      </div>
    );

  return (
    <div className={chamado ? "coach coach--chamado" : "coach"}>
      {topo}

      <div className="coach__lista" ref={lista} aria-live="polite">
        {carregando && mensagens.length === 0 && <p className="carregando px">CARREGANDO</p>}

        {vazio && (
          <div className="coach__vazio">
            <p className="coach__ola">Oi! Eu leio seu dia, registro refeições e ajusto o plano com você.</p>
            <p className="mudo">Mudança de meta só acontece depois que você aprovar.</p>
            <ul className="coach__sugestoes">
              {SUGESTOES.map((s) => (
                <li key={s}>
                  <button type="button" onClick={() => void enviar(s)} disabled={ocupado}>
                    {s}
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}

        {mensagens.map((m, i) =>
          m.papel === "usuario" ? (
            <div key={i} className="msg msg--usuario">
              <div className="msg__balao">
                <Texto texto={m.texto} />
              </div>
            </div>
          ) : (
            <div key={i} className="msg msg--coach">
              <div className="msg__balao">
                <Texto texto={m.texto} />
              </div>
              <Chips ferramentas={m.ferramentas} />
            </div>
          ),
        )}

        {envio && (
          <>
            <div className="msg msg--usuario">
              <div className="msg__balao">
                {envio.previa && <img className="msg__foto" src={envio.previa} alt="Foto enviada" />}
                <Texto texto={envio.texto} />
              </div>
            </div>
            <div className="msg msg--coach" role="status">
              <div className="msg__balao pensando">
                <span className="pensando__blocos" aria-hidden="true">
                  <i />
                  <i />
                  <i />
                </span>
                <span className="vt">pensando…</span>
              </div>
            </div>
          </>
        )}

        {pendente && !envio && <Aprovacao pendente={pendente} decidindo={decidindo} onDecidir={decidir} />}

        {erro && (
          <p className="aviso coach__erro" role="alert">
            {erro}
          </p>
        )}
      </div>

      <form className={bloqueado ? "compositor compositor--bloqueado" : "compositor"} onSubmit={aoEnviar}>
        {dicaCamera && !foto && (
          <p className="compositor__dica">
            Toque na <span className="px">CAMERA</span> para tirar ou escolher a foto do prato.
          </p>
        )}
        {foto && (
          <div className="compositor__previa">
            {previa && !previaQuebrada ? (
              <img src={previa} alt="Prévia da foto" onError={() => setPreviaQuebrada(true)} />
            ) : (
              <span className="compositor__sem-previa px" role="img" aria-label="Prévia da foto">
                FOTO
              </span>
            )}
            <button
              type="button"
              className="compositor__tirar px"
              aria-label="Remover foto"
              onClick={() => trocarFoto(null, null)}
              disabled={ocupado}
            >
              ×
            </button>
            <span className="compositor__info mudo">
              {texto.trim() ? "Vai junto com a mensagem" : `Enviar como “${MENSAGEM_FOTO}”`}
            </span>
          </div>
        )}

        <div className="compositor__linha">
          <input
            ref={seletor}
            className="so-leitor"
            type="file"
            accept="image/*"
            aria-label="Foto da refeição"
            tabIndex={-1}
            onChange={escolherFoto}
          />
          <button
            type="button"
            className={dicaCamera ? "compositor__camera compositor__camera--dica" : "compositor__camera"}
            aria-label="Foto: câmera ou galeria"
            onClick={() => seletor.current?.click()}
            disabled={ocupado || bloqueado}
          >
            <Icone nome="camera" tamanho={18} />
          </button>
          <textarea
            ref={campo}
            rows={1}
            aria-label="Mensagem para o coach"
            placeholder={bloqueado ? "Responda o pedido acima" : "Pergunte ao coach…"}
            maxLength={LIMITE_TEXTO}
            enterKeyHint="send"
            value={texto}
            disabled={bloqueado || decidindo}
            onChange={(e) => setTexto(e.target.value)}
            onKeyDown={aoTeclar}
          />
          <button type="submit" className="compositor__enviar" aria-label="Enviar" disabled={!podeEnviar}>
            <Icone nome="enviar" tamanho={18} />
          </button>
        </div>
        {texto.length > LIMITE_TEXTO - 200 && (
          <span className="compositor__conta vt">
            {texto.length}/{LIMITE_TEXTO}
          </span>
        )}
      </form>
    </div>
  );
}
