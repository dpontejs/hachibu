import { useEffect, useRef, useState, type FormEvent } from "react";
import { useNavigate } from "react-router";
import { api, ApiError, mensagemDeErro, type Alimento } from "../api";
import { horaEmBrasilia } from "../formato";

const ESPERA_MS = 250;
const MAX_ITENS = 30;
const GRAMAS_PADRAO = "100";

/** Nome sugerido pela hora de Brasília. */
export function nomePorHora(h: number): string {
  if (h < 10) return "Café da manhã";
  if (h < 15) return "Almoço";
  if (h < 18) return "Lanche";
  return "Jantar";
}

interface ItemPrato {
  alimento: Alimento;
  gramas: string; // texto do campo; vira número só no envio
}

function gramasValidas(g: string): number | null {
  const n = Number(g);
  if (g.trim() === "" || !Number.isFinite(n) || n < 1 || n > 2000) return null;
  return n;
}

/** Valor por 100 g × gramas. Gramas inválidas contam como 0 na prévia. */
function proporcional(valor100: number, gramas: string): number {
  const n = Number(gramas);
  return Number.isFinite(n) && n > 0 ? (valor100 * n) / 100 : 0;
}

const NOME_CAMPO: Record<string, string> = {
  nome: "Nome",
  gramas: "Gramas",
  alimento_id: "Alimento",
  itens: "Itens",
};

export default function Comida() {
  const navegar = useNavigate();
  const busca = useRef<HTMLInputElement>(null);
  const [termo, setTermo] = useState("");
  const [resultados, setResultados] = useState<Alimento[] | null>(null);
  const [buscando, setBuscando] = useState(false);
  const [erroBusca, setErroBusca] = useState<string | null>(null);
  const [prato, setPrato] = useState<ItemPrato[]>([]);
  const [nome, setNome] = useState(() => nomePorHora(horaEmBrasilia()));
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  const consulta = termo.trim();

  useEffect(() => {
    if (consulta.length < 2) {
      setResultados(null);
      setBuscando(false);
      setErroBusca(null);
      return;
    }
    let vivo = true;
    setBuscando(true);
    const t = window.setTimeout(() => {
      api
        .buscarAlimentos(consulta)
        .then((r) => {
          if (!vivo) return;
          setResultados(r);
          setErroBusca(null);
        })
        .catch((e) => vivo && setErroBusca(mensagemDeErro(e)))
        .finally(() => vivo && setBuscando(false));
    }, ESPERA_MS);
    return () => {
      vivo = false;
      window.clearTimeout(t);
    };
  }, [consulta]);

  function adicionar(a: Alimento) {
    setErro(null);
    setPrato((p) => {
      if (p.some((i) => i.alimento.id === a.id) || p.length >= MAX_ITENS) return p;
      return [...p, { alimento: a, gramas: GRAMAS_PADRAO }];
    });
    // Limpa a busca para o prato aparecer logo abaixo, e volta o foco para buscar o próximo.
    setTermo("");
    busca.current?.focus();
  }

  function mudarGramas(id: number, gramas: string) {
    setPrato((p) => p.map((i) => (i.alimento.id === id ? { ...i, gramas } : i)));
  }

  function remover(id: number) {
    setPrato((p) => p.filter((i) => i.alimento.id !== id));
  }

  const total = prato.reduce(
    (t, { alimento: a, gramas }) => ({
      kcal: t.kcal + proporcional(a.kcal, gramas),
      proteina_g: t.proteina_g + proporcional(a.proteina_g, gramas),
      carbo_g: t.carbo_g + proporcional(a.carbo_g, gramas),
      gordura_g: t.gordura_g + proporcional(a.gordura_g, gramas),
    }),
    { kcal: 0, proteina_g: 0, carbo_g: 0, gordura_g: 0 },
  );
  const invalidos = prato.filter((i) => gramasValidas(i.gramas) === null).length;
  const podeSalvar = prato.length > 0 && invalidos === 0 && !salvando;

  async function salvar(ev: FormEvent) {
    ev.preventDefault();
    if (!podeSalvar) return;
    setSalvando(true);
    setErro(null);
    try {
      await api.addRefeicaoTaco({
        nome: nome.trim() || nomePorHora(horaEmBrasilia()),
        itens: prato.map((i) => ({ alimento_id: i.alimento.id, gramas: Number(i.gramas) })),
      });
      navegar("/");
    } catch (e) {
      if (e instanceof ApiError && e.status === 422 && e.detail === "alimento_inexistente") {
        setErro("Um alimento do prato não foi encontrado na tabela. Remova e busque de novo.");
      } else if (e instanceof ApiError && e.status === 422 && Object.keys(e.campos).length) {
        setErro(
          Object.entries(e.campos)
            .map(([c, m]) => `${NOME_CAMPO[c] ?? c}: ${m}`)
            .join(" · "),
        );
      } else {
        setErro(mensagemDeErro(e));
      }
      setSalvando(false);
    }
  }

  const noPrato = new Set(prato.map((i) => i.alimento.id));

  return (
    <div className="comida">
      <header className="comida__topo">
        <div className="rotulo px">COMIDA</div>
        <h1 className="comida__titulo">Montar refeição</h1>
        <p className="mudo comida__intro">
          Busque na TACO, a tabela brasileira de alimentos. Você escolhe as gramas; as calorias saem da tabela.
        </p>
      </header>

      <section className="comida__busca" aria-label="Busca de alimentos">
        <label className="busca">
          <span className="busca__lupa px" aria-hidden="true">
            ?
          </span>
          <input
            ref={busca}
            type="search"
            aria-label="Buscar alimento"
            placeholder="arroz, frango, banana…"
            maxLength={60}
            autoComplete="off"
            enterKeyHint="search"
            value={termo}
            onChange={(e) => setTermo(e.target.value)}
          />
          {buscando && <span className="busca__status vt">buscando</span>}
        </label>

        {erroBusca && (
          <p className="aviso" role="alert">
            {erroBusca}
          </p>
        )}

        {resultados && resultados.length === 0 && !buscando && (
          <p className="resultados__vazio">
            Nada com “{consulta}”. Tente uma palavra só, como <span className="vt">frango</span>.
          </p>
        )}

        {resultados && resultados.length > 0 && (
          <ul className="resultados" aria-label="Resultados">
            {resultados.map((a) => (
              <li key={a.id}>
                <button
                  type="button"
                  className="resultado"
                  onClick={() => adicionar(a)}
                  disabled={!noPrato.has(a.id) && prato.length >= MAX_ITENS}
                >
                  <span className="resultado__texto">
                    <span className="resultado__nome">{a.nome}</span>
                    <span className="resultado__cat mudo">{noPrato.has(a.id) ? "já está no prato" : a.categoria}</span>
                  </span>
                  <span className="resultado__kcal">
                    <span className="vt">{Math.round(a.kcal)}</span>
                    <span className="vt mudo">kcal/100 g</span>
                  </span>
                  <span className="resultado__mais px" aria-hidden="true">
                    {noPrato.has(a.id) ? "✓" : "+"}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      <form className="prato" onSubmit={salvar} aria-labelledby="prato-titulo">
        <div className="linha">
          <h2 id="prato-titulo" className="rotulo px">
            PRATO
          </h2>
          <span className="vt mudo meta-num">
            {prato.length}/{MAX_ITENS}
          </span>
        </div>

        {prato.length === 0 ? (
          <div className="prato__vazio">
            <div className="prato__blocos" aria-hidden="true">
              {Array.from({ length: 5 }, (_, i) => (
                <i key={i} />
              ))}
            </div>
            <p className="mudo">Prato vazio. Toque num alimento da busca para adicionar.</p>
          </div>
        ) : (
          <ul className="prato__itens">
            {prato.map(({ alimento: a, gramas }) => {
              const invalido = gramasValidas(gramas) === null;
              return (
                <li key={a.id} className="prato__item">
                  <span className="prato__nome">{a.nome}</span>
                  <label className="prato__gramas">
                    <input
                      type="number"
                      inputMode="numeric"
                      min={1}
                      max={2000}
                      step="any"
                      aria-label={`Gramas de ${a.nome}`}
                      aria-invalid={invalido}
                      value={gramas}
                      onChange={(e) => mudarGramas(a.id, e.target.value)}
                    />
                    <span className="vt mudo">g</span>
                  </label>
                  <span className="vt prato__kcal">{Math.round(proporcional(a.kcal, gramas))}</span>
                  <button
                    type="button"
                    className="prato__remover"
                    aria-label={`Remover ${a.nome}`}
                    onClick={() => remover(a.id)}
                  >
                    <span className="px" aria-hidden="true">
                      ×
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}

        <div className="prato__total">
          <div className="prato__total-kcal">
            <span className="rotulo px">TOTAL</span>
            <output className="vt prato__total-num" aria-label="Total do prato">
              {Math.round(total.kcal)}
            </output>
            <span className="vt mudo">kcal</span>
          </div>
          <div className="prato__macros vt">
            <span style={{ color: "var(--prot)" }}>P {Math.round(total.proteina_g)}g</span>
            <span style={{ color: "var(--carb)" }}>C {Math.round(total.carbo_g)}g</span>
            <span style={{ color: "var(--gord)" }}>G {Math.round(total.gordura_g)}g</span>
          </div>
        </div>

        {invalidos > 0 && <p className="campo__erro">Gramas entre 1 e 2000 em cada item.</p>}

        <label className="campo">
          <span className="campo__rotulo">Nome da refeição</span>
          <input type="text" maxLength={120} value={nome} onChange={(e) => setNome(e.target.value)} />
        </label>

        {erro && (
          <p className="aviso" role="alert">
            {erro}
          </p>
        )}

        <button type="submit" className="botao" disabled={!podeSalvar}>
          {salvando ? "Salvando…" : "Salvar refeição"}
        </button>
      </form>
    </div>
  );
}
