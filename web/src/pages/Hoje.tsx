import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link } from "react-router";
import { api, ApiError, mensagemDeErro, type Hoje as DadosHoje, type RefeicaoResumo } from "../api";
import { horaMinuto, litros, rotuloDoDia, rotuloOrigem, saudacao } from "../formato";
import { Barra, Icone } from "../ui";

const GOTAS = 12;

export function gotasCheias(aguaMl: number, metaMl: number): number {
  if (!metaMl || metaMl <= 0) return 0;
  return Math.max(0, Math.min(GOTAS, Math.round((aguaMl / metaMl) * GOTAS)));
}

export default function Hoje() {
  const [dados, setDados] = useState<DadosHoje | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [bebendo, setBebendo] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setDados(await api.hoje());
      setErro(null);
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function beber(ml: number) {
    setBebendo(true);
    try {
      await api.addAgua(ml);
      await carregar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setBebendo(false);
    }
  }

  if (!dados) {
    return (
      <div className="hoje">
        {erro ? (
          <p className="aviso" role="alert">
            {erro}
          </p>
        ) : (
          <p className="carregando px">CARREGANDO</p>
        )}
      </div>
    );
  }

  const { metas, consumido } = dados;
  const restantes = Math.round(metas.kcal - consumido.kcal);
  const cheias = gotasCheias(dados.agua_ml, metas.agua_ml);

  return (
    <div className="hoje">
      <header className="hoje__topo">
        <div>
          <div className="rotulo px">{rotuloDoDia(dados.data)}</div>
          <h1 className="hoje__titulo">{saudacao()}</h1>
        </div>
        <div className="hoje__topo-dir">
          <span
            className="streak px"
            title="A sequência de dias no plano chega junto com a gamificação"
          >
            ▲ 0 DIAS
          </span>
          <Link to="/perfil" className="botao-perfil" aria-label="Perfil e metas">
            <Icone nome="perfil" tamanho={14} />
          </Link>
        </div>
      </header>

      {erro && (
        <p className="aviso" role="alert">
          {erro}
        </p>
      )}

      <section className="card card--kcal" aria-labelledby="kcal-titulo">
        <div className="linha">
          <h2 id="kcal-titulo" className="rotulo px">
            KCAL
          </h2>
          <span className="kcal__meta">
            <span className="vt mudo meta-num">meta {metas.kcal}</span>
            <span className="meta-origem" title="De onde veio a meta do dia">
              {rotuloOrigem(metas.origem)}
            </span>
          </span>
        </div>
        <div className="linha kcal__numeros">
          <span className="vt kcal__grande">{Math.round(consumido.kcal)}</span>
          {restantes >= 0 ? (
            <span className="vt kcal__resto">{restantes} restantes</span>
          ) : (
            <span className="vt kcal__resto kcal__resto--acima">{-restantes} acima</span>
          )}
        </div>
        <Barra
          valor={consumido.kcal}
          meta={metas.kcal}
          cor="var(--acento)"
          rotulo="Calorias do dia"
          alta
        />
      </section>

      <section className="card card--macros" aria-label="Macronutrientes">
        <Macro nome="PROT" valor={consumido.proteina_g} meta={metas.proteina_g} cor="var(--prot)" />
        <Macro nome="CARB" valor={consumido.carbo_g} meta={metas.carbo_g} cor="var(--carb)" />
        <Macro nome="GORD" valor={consumido.gordura_g} meta={metas.gordura_g} cor="var(--gord)" />
      </section>

      <section className="card card--agua" aria-labelledby="agua-titulo">
        <div className="linha">
          <h2 id="agua-titulo" className="rotulo px">
            ÁGUA
          </h2>
          <span className="vt valor-num">
            {litros(dados.agua_ml)} / {litros(metas.agua_ml)} L
          </span>
        </div>
        <div
          className="gotas"
          role="img"
          aria-label={`${cheias} de ${GOTAS} gotas: ${litros(dados.agua_ml)} de ${litros(metas.agua_ml)} litros`}
        >
          {Array.from({ length: GOTAS }, (_, i) => (
            <b key={i} className={i < cheias ? "gota gota--cheia" : "gota"} data-gota={i < cheias ? "cheia" : "vazia"} />
          ))}
        </div>
        <div className="agua__botoes">
          <button type="button" className="botao-agua" disabled={bebendo} onClick={() => beber(250)}>
            +250 ml
          </button>
          <button type="button" className="botao-agua" disabled={bebendo} onClick={() => beber(500)}>
            +500 ml
          </button>
        </div>
      </section>

      <section className="refeicoes" aria-labelledby="refeicoes-titulo">
        <div className="linha">
          <h2 id="refeicoes-titulo" className="rotulo px">
            REFEIÇÕES
          </h2>
          <span className="vt mudo meta-num">{dados.refeicoes.length}</span>
        </div>
        {dados.refeicoes.length === 0 ? (
          <p className="refeicoes__vazio">Nada registrado hoje ainda.</p>
        ) : (
          <ul className="refeicoes__lista">
            {dados.refeicoes.map((r) => (
              <Refeicao key={r.id} r={r} />
            ))}
          </ul>
        )}
      </section>

      <AdicionarManual aoSalvar={carregar} />
    </div>
  );
}

function Refeicao({ r }: { r: RefeicaoResumo }) {
  const [aberta, setAberta] = useState(false);
  const itens = r.itens ?? [];
  const linha = (
    <>
      <span className="vt refeicao__hora">{horaMinuto(r.criado_em)}</span>
      <span className="refeicao__nome">{r.nome}</span>
      <span className="vt refeicao__kcal">{Math.round(r.kcal)}</span>
    </>
  );
  if (itens.length === 0) return <li className="refeicao">{linha}</li>;
  const idItens = `refeicao-${r.id}-itens`;
  return (
    <li className={aberta ? "refeicao refeicao--aberta" : "refeicao"}>
      <button
        type="button"
        className="refeicao__abrir"
        aria-expanded={aberta}
        aria-controls={idItens}
        onClick={() => setAberta((a) => !a)}
      >
        {linha}
        <span className="refeicao__seta px" aria-hidden="true">
          {aberta ? "-" : "+"}
        </span>
      </button>
      {aberta && (
        <ul id={idItens} className="refeicao__itens">
          {itens.map((i, n) => (
            <li key={n}>
              <span className="refeicao__item-nome">{i.nome}</span>
              <span className="vt mudo">{Math.round(i.gramas)} g</span>
              <span className="vt">{Math.round(i.kcal)}</span>
            </li>
          ))}
        </ul>
      )}
    </li>
  );
}

function Macro({ nome, valor, meta, cor }: { nome: string; valor: number; meta: number; cor: string }) {
  return (
    <div className="macro">
      <div className="linha">
        <span className="rotulo px">{nome}</span>
        <span className="vt valor-num">
          {Math.round(valor)}/{meta}g
        </span>
      </div>
      <Barra valor={valor} meta={meta} cor={cor} rotulo={nome} />
    </div>
  );
}

const VAZIO = { nome: "", kcal: "", proteina_g: "", carbo_g: "", gordura_g: "" };
type CampoRefeicao = keyof typeof VAZIO;

function AdicionarManual({ aoSalvar }: { aoSalvar: () => Promise<void> }) {
  const [aberto, setAberto] = useState(false);
  const [form, setForm] = useState(VAZIO);
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);

  function mudar(campo: CampoRefeicao, valor: string) {
    setForm((f) => ({ ...f, [campo]: valor }));
  }

  async function enviar(ev: FormEvent) {
    ev.preventDefault();
    setSalvando(true);
    setErro(null);
    setCampos({});
    try {
      await api.addRefeicao({
        nome: form.nome.trim(),
        kcal: Number(form.kcal),
        proteina_g: Number(form.proteina_g || 0),
        carbo_g: Number(form.carbo_g || 0),
        gordura_g: Number(form.gordura_g || 0),
      });
      setForm(VAZIO);
      setAberto(false);
      await aoSalvar();
    } catch (e) {
      if (e instanceof ApiError) setCampos(e.campos);
      setErro(mensagemDeErro(e));
    } finally {
      setSalvando(false);
    }
  }

  if (!aberto) {
    return (
      <button type="button" className="adicionar__abrir" onClick={() => setAberto(true)}>
        <span className="px">+</span> adicionar manual
      </button>
    );
  }

  const num = (campo: CampoRefeicao, rotulo: string, unidade: string, max: number) => (
    <label className="campo campo--num">
      <span className="campo__rotulo">
        {rotulo} <span className="mudo">{unidade}</span>
      </span>
      <input
        type="number"
        inputMode="decimal"
        min={0}
        max={max}
        step="any"
        required={campo === "kcal"}
        value={form[campo]}
        onChange={(e) => mudar(campo, e.target.value)}
        aria-invalid={campo in campos}
      />
      {campos[campo] && <span className="campo__erro">{campos[campo]}</span>}
    </label>
  );

  return (
    <form className="adicionar" onSubmit={enviar} aria-label="Adicionar refeição manual">
      <div className="linha">
        <h2 className="rotulo px">ADICIONAR MANUAL</h2>
        <button type="button" className="link-mudo" onClick={() => setAberto(false)}>
          cancelar
        </button>
      </div>
      <label className="campo">
        <span className="campo__rotulo">Nome</span>
        <input
          type="text"
          required
          maxLength={120}
          placeholder="Ex.: arroz, feijão e frango"
          value={form.nome}
          onChange={(e) => mudar("nome", e.target.value)}
          aria-invalid={"nome" in campos}
        />
        {campos.nome && <span className="campo__erro">{campos.nome}</span>}
      </label>
      <div className="adicionar__grade">
        {num("kcal", "Kcal", "", 5000)}
        {num("proteina_g", "Proteína", "g", 500)}
        {num("carbo_g", "Carbo", "g", 500)}
        {num("gordura_g", "Gordura", "g", 500)}
      </div>
      {erro && (
        <p className="aviso" role="alert">
          {erro}
        </p>
      )}
      <button type="submit" className="botao" disabled={salvando}>
        {salvando ? "Salvando…" : "Registrar"}
      </button>
    </form>
  );
}
