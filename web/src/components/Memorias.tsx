import { useEffect, useState, type FormEvent } from "react";
import { api, ApiError, mensagemDeErro, type Memoria, type TipoMemoria } from "../api";

const GRUPOS: { tipo: TipoMemoria; rotulo: string; nome: string; vazio: string }[] = [
  { tipo: "restricao", rotulo: "RESTRICOES", nome: "Restrições", vazio: "Nada ainda. Ex.: celíaco, alergia a amendoim." },
  { tipo: "condicao", rotulo: "CONDICOES FISICAS", nome: "Condições físicas", vazio: "Nada ainda. Ex.: dor no joelho." },
  { tipo: "gosto", rotulo: "GOSTOS", nome: "Gostos", vazio: "Nada ainda. Ex.: não gosta de azeitona." },
];

/** Restrição e condição: apagar muda o que o coach respeita, então pede confirmação. */
const SENSIVEL: TipoMemoria[] = ["restricao", "condicao"];

function Item({
  memoria,
  onSalvar,
  onApagar,
}: {
  memoria: Memoria;
  onSalvar: (texto: string) => Promise<boolean>;
  onApagar: () => void;
}) {
  const [editando, setEditando] = useState(false);
  const [texto, setTexto] = useState(memoria.texto);

  async function salvar(ev: FormEvent) {
    ev.preventDefault();
    if (texto.trim().length < 2) return;
    if (await onSalvar(texto)) setEditando(false);
  }

  function cancelar() {
    setTexto(memoria.texto);
    setEditando(false);
  }

  if (editando)
    return (
      <li className="memoria">
        <form className="memoria__edicao" onSubmit={salvar}>
          <input
            aria-label="Editar memória"
            autoFocus
            value={texto}
            onKeyDown={(e) => e.key === "Escape" && cancelar()}
            minLength={2}
            maxLength={200}
            required
            onChange={(e) => setTexto(e.target.value)}
          />
          <button type="submit" className="memoria__botao px">
            SALVAR
          </button>
          <button type="button" className="memoria__botao px" onClick={cancelar}>
            CANCELAR
          </button>
        </form>
      </li>
    );

  return (
    <li className="memoria">
      <span className="memoria__texto">{memoria.texto}</span>
      <span className="memoria__origem mudo">{memoria.origem === "coach" ? "anotado pelo coach" : "você"}</span>
      <span className="memoria__acoes">
        <button
          type="button"
          className="memoria__botao px"
          aria-label={`Editar ${memoria.texto}`}
          onClick={() => {
            setTexto(memoria.texto);
            setEditando(true);
          }}
        >
          EDITAR
        </button>
        <button type="button" className="memoria__botao px" aria-label={`Apagar ${memoria.texto}`} onClick={onApagar}>
          APAGAR
        </button>
      </span>
    </li>
  );
}

/** "O que o coach sabe de você": as memórias que valem em todas as conversas, editáveis pelo aluno. */
export default function Memorias() {
  const [memorias, setMemorias] = useState<Memoria[] | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [tipo, setTipo] = useState<TipoMemoria>("gosto");
  const [texto, setTexto] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [tentativa, setTentativa] = useState(0);
  const [falhouCarregar, setFalhouCarregar] = useState(false);

  useEffect(() => {
    let vivo = true;
    api
      .memorias()
      .then((r) => {
        if (!vivo) return;
        setMemorias(r.memorias);
        setFalhouCarregar(false);
        setErro(null);
      })
      .catch((e) => {
        if (!vivo) return;
        setFalhouCarregar(true);
        setErro(mensagemDeErro(e));
      });
    return () => {
      vivo = false;
    };
  }, [tentativa]);

  /** 404: a memória sumiu (outra aba, ou o coach esqueceu um gosto): tira da tela também. */
  function sumiu(e: unknown, id: number): boolean {
    if (!(e instanceof ApiError) || e.status !== 404) return false;
    setMemorias((atual) => (atual ?? []).filter((m) => m.id !== id));
    return true;
  }

  async function adicionar(ev: FormEvent) {
    ev.preventDefault();
    if (texto.trim().length < 2 || enviando || memorias === null) return;
    setEnviando(true);
    setErro(null);
    try {
      const nova = await api.criarMemoria(tipo, texto.trim());
      setMemorias((atual) => [...(atual ?? []).filter((m) => m.id !== nova.id), nova]);
      setTexto("");
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setEnviando(false);
    }
  }

  async function salvar(id: number, novo: string): Promise<boolean> {
    setErro(null);
    try {
      const editada = await api.editarMemoria(id, novo.trim());
      setMemorias((atual) => (atual ?? []).map((m) => (m.id === id ? editada : m)));
      return true;
    } catch (e) {
      setErro(mensagemDeErro(e));
      return sumiu(e, id);
    }
  }

  async function apagar(m: Memoria) {
    if (SENSIVEL.includes(m.tipo) && !window.confirm(`Apagar "${m.texto}"? O coach deixa de levar isso em conta.`))
      return;
    setErro(null);
    try {
      await api.apagarMemoria(m.id);
      setMemorias((atual) => (atual ?? []).filter((x) => x.id !== m.id));
    } catch (e) {
      if (!sumiu(e, m.id)) setErro(mensagemDeErro(e));
    }
  }

  return (
    <section className="memorias" aria-labelledby="memorias-titulo">
      <h2 id="memorias-titulo" className="rotulo px">
        O QUE O COACH SABE DE VOCE
      </h2>
      <p className="mudo memorias__nota">
        O coach anota o que você conta na conversa e lembra em todas as outras. Restrições e condições ele nunca
        apaga sozinho: só você, aqui.
      </p>

      {memorias === null && !falhouCarregar && (
        <p className="carregando px" role="status">
          CARREGANDO
        </p>
      )}
      {memorias === null && falhouCarregar && (
        <button type="button" className="botao" onClick={() => setTentativa((t) => t + 1)}>
          TENTAR DE NOVO
        </button>
      )}

      {memorias &&
        GRUPOS.map((g) => {
          const itens = memorias.filter((m) => m.tipo === g.tipo);
          return (
            <div key={g.tipo} className={SENSIVEL.includes(g.tipo) ? "memorias__grupo memorias__grupo--sensivel" : "memorias__grupo"}>
              <h3 className="px">{g.rotulo}</h3>
              {itens.length === 0 ? (
                <p className="mudo memorias__vazio">{g.vazio}</p>
              ) : (
                <ul aria-label={g.nome}>
                  {itens.map((m) => (
                    <Item key={m.id} memoria={m} onSalvar={(t) => salvar(m.id, t)} onApagar={() => void apagar(m)} />
                  ))}
                </ul>
              )}
            </div>
          );
        })}

      <form className="memorias__nova" onSubmit={adicionar}>
        <select aria-label="Tipo" value={tipo} disabled={memorias === null} onChange={(e) => setTipo(e.target.value as TipoMemoria)}>
          <option value="restricao">Restrição</option>
          <option value="condicao">Condição física</option>
          <option value="gosto">Gosto</option>
        </select>
        <input
          aria-label="O que o coach deve saber"
          placeholder="ex.: intolerante à lactose"
          value={texto}
          maxLength={200}
          disabled={memorias === null}
          onChange={(e) => setTexto(e.target.value)}
        />
        <button
          type="submit"
          className="botao"
          disabled={enviando || memorias === null || texto.trim().length < 2}
        >
          ADICIONAR
        </button>
      </form>

      {erro && (
        <p className="aviso" role="alert">
          {erro}
        </p>
      )}
    </section>
  );
}
