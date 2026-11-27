import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { Link } from "react-router";
import {
  api,
  ApiError,
  mensagemDeErro,
  type Diagnostico as DadosDiagnostico,
  type Equipamento,
  type Metas,
  type Nivel,
  type Objetivo,
  type Perfil as DadosPerfil,
  type Sexo,
  type CorridaQuando,
} from "../api";
import Diagnostico from "../components/Diagnostico";
import Memorias from "../components/Memorias";
import { litros, rotuloOrigem } from "../formato";

interface Form {
  sexo: Sexo | "";
  idade: string;
  altura_cm: string;
  peso_kg: string;
  objetivo: Objetivo | "";
  nivel: Nivel | "";
  dias_semana: string;
  minutos_sessao: string;
  equipamento: Equipamento | "";
  percentual_gordura: string;
  cintura_cm: string;
  condicoes_saude: string;
  meta_profissional_kcal: string;
  meta_profissional_proteina_g: string;
  meta_profissional_carbo_g: string;
  meta_profissional_gordura_g: string;
  nivel_corrida: Nivel | "";
  corrida_quando: CorridaQuando | "";
  corridas_semana: string;
}

const VAZIO: Form = {
  sexo: "",
  idade: "",
  altura_cm: "",
  peso_kg: "",
  objetivo: "",
  nivel: "",
  dias_semana: "",
  minutos_sessao: "",
  equipamento: "",
  percentual_gordura: "",
  cintura_cm: "",
  condicoes_saude: "",
  meta_profissional_kcal: "",
  meta_profissional_proteina_g: "",
  meta_profissional_carbo_g: "",
  meta_profissional_gordura_g: "",
  nivel_corrida: "",
  corrida_quando: "",
  corridas_semana: "",
};

function deApi(p: DadosPerfil): Form {
  const s = (v: number | null | undefined) => (v === null || v === undefined ? "" : String(v));
  return {
    sexo: p.sexo,
    idade: s(p.idade),
    altura_cm: s(p.altura_cm),
    peso_kg: s(p.peso_kg),
    objetivo: p.objetivo,
    nivel: p.nivel,
    dias_semana: s(p.dias_semana),
    minutos_sessao: s(p.minutos_sessao),
    equipamento: p.equipamento,
    percentual_gordura: s(p.percentual_gordura),
    cintura_cm: s(p.cintura_cm),
    condicoes_saude: p.condicoes_saude ?? "",
    meta_profissional_kcal: s(p.meta_profissional_kcal),
    meta_profissional_proteina_g: s(p.meta_profissional_proteina_g),
    meta_profissional_carbo_g: s(p.meta_profissional_carbo_g),
    meta_profissional_gordura_g: s(p.meta_profissional_gordura_g),
    nivel_corrida: p.nivel_corrida ?? "",
    corrida_quando: p.corrida_quando ?? "",
    corridas_semana: s(p.corridas_semana),
  };
}

function paraApi(f: Form): DadosPerfil {
  const opcional = (v: string) => (v.trim() === "" ? null : Number(v));
  return {
    sexo: f.sexo as Sexo,
    idade: Number(f.idade),
    altura_cm: Number(f.altura_cm),
    peso_kg: Number(f.peso_kg),
    objetivo: f.objetivo as Objetivo,
    nivel: f.nivel as Nivel,
    dias_semana: Number(f.dias_semana),
    minutos_sessao: Number(f.minutos_sessao),
    equipamento: f.equipamento as Equipamento,
    percentual_gordura: opcional(f.percentual_gordura),
    cintura_cm: opcional(f.cintura_cm),
    condicoes_saude: f.condicoes_saude.trim() || null,
    // Campo vazio manda null: apagar a meta profissional volta para a fórmula.
    meta_profissional_kcal: opcional(f.meta_profissional_kcal),
    meta_profissional_proteina_g: opcional(f.meta_profissional_proteina_g),
    meta_profissional_carbo_g: opcional(f.meta_profissional_carbo_g),
    meta_profissional_gordura_g: opcional(f.meta_profissional_gordura_g),
    nivel_corrida: f.nivel_corrida || null,
    corrida_quando: f.corrida_quando || null,
    corridas_semana: opcional(f.corridas_semana),
  };
}

export default function Perfil() {
  const [form, setForm] = useState<Form>(VAZIO);
  const [metas, setMetas] = useState<Metas | null>(null);
  const [novo, setNovo] = useState(true);
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [erro, setErro] = useState<string | null>(null);
  const [salvando, setSalvando] = useState(false);
  const [salvo, setSalvo] = useState(false);
  const [diag, setDiag] = useState<DadosDiagnostico | null>(null);
  const topo = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let vivo = true;
    api
      .getPerfil()
      .then((r) => {
        if (!vivo || !r) return;
        setForm(deApi(r.perfil));
        setMetas(r.metas);
        setNovo(false);
      })
      .catch((e) => vivo && setErro(mensagemDeErro(e)));
    return () => {
      vivo = false;
    };
  }, []);

  function mudar<K extends keyof Form>(campo: K, valor: Form[K]) {
    setForm((f) => ({ ...f, [campo]: valor }));
    setSalvo(false);
  }

  async function enviar(ev: FormEvent) {
    ev.preventDefault();
    const faltando = (["sexo", "objetivo", "nivel", "dias_semana", "equipamento"] as const).filter(
      (c) => form[c] === "",
    );
    if (faltando.length) {
      setCampos(Object.fromEntries(faltando.map((c) => [c, "Escolha uma opção."])));
      setErro("Faltam algumas escolhas.");
      return;
    }
    setSalvando(true);
    setErro(null);
    setCampos({});
    try {
      const r = await api.putPerfil(paraApi(form));
      setMetas(r.metas);
      setNovo(false);
      setSalvo(true);
      // O diagnóstico é um extra: se falhar, as metas novas já estão na tela.
      setDiag(await api.diagnostico().catch(() => null));
      topo.current?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    } catch (e) {
      if (e instanceof ApiError) setCampos(e.campos);
      setErro(mensagemDeErro(e));
    } finally {
      setSalvando(false);
    }
  }

  const numero = (
    campo: keyof Form,
    rotulo: string,
    unidade: string,
    min: number,
    max: number,
    obrigatorio = true,
  ) => (
    <label className="campo campo--num">
      <span className="campo__rotulo">
        {rotulo} {unidade && <span className="mudo">{unidade}</span>}
      </span>
      <input
        type="number"
        inputMode="decimal"
        step="any"
        min={min}
        max={max}
        required={obrigatorio}
        value={form[campo]}
        onChange={(e) => mudar(campo, e.target.value)}
        aria-invalid={campo in campos}
      />
      {campos[campo] && <span className="campo__erro">{campos[campo]}</span>}
    </label>
  );

  return (
    <div className="perfil">
      <header className="perfil__topo">
        <div className="rotulo px">{novo ? "ETAPA 1 DE 2" : "PERFIL"}</div>
        <h1 className="perfil__titulo">{novo ? "Vamos calibrar suas metas" : "Seu perfil"}</h1>
        <p className="mudo perfil__intro">
          As metas saem de uma fórmula fixa (Mifflin-St Jeor, ou Katch-McArdle se você souber seu % de gordura), ou
          da meta que seu nutricionista passou, se você tiver uma. A entrevista com o coach vem na próxima etapa.
        </p>
      </header>

      <div ref={topo} className="perfil__resultado">
        {metas && <PainelMetas metas={metas} destaque={salvo} />}
        {salvo && diag && <Diagnostico dados={diag} />}
      </div>

      <form className="formulario perfil__form" onSubmit={enviar} noValidate={false}>
        <Grupo titulo="CORPO">
          <Escolha
            nome="sexo"
            rotulo="Sexo"
            valor={form.sexo}
            erro={campos.sexo}
            opcoes={[
              ["M", "Masculino"],
              ["F", "Feminino"],
            ]}
            aoMudar={(v) => mudar("sexo", v as Sexo)}
          />
          <div className="grade-3">
            {numero("idade", "Idade", "anos", 14, 90)}
            {numero("altura_cm", "Altura", "cm", 120, 230)}
            {numero("peso_kg", "Peso", "kg", 30, 250)}
          </div>
        </Grupo>

        <Grupo titulo="OBJETIVO">
          <Escolha
            nome="objetivo"
            rotulo="O que você quer agora"
            valor={form.objetivo}
            erro={campos.objetivo}
            opcoes={[
              ["perder", "Perder gordura"],
              ["manter", "Manter"],
              ["ganhar", "Ganhar massa"],
            ]}
            aoMudar={(v) => mudar("objetivo", v as Objetivo)}
          />
          <Escolha
            nome="nivel"
            rotulo="Experiência com treino"
            valor={form.nivel}
            erro={campos.nivel}
            opcoes={[
              ["iniciante", "Iniciante"],
              ["intermediario", "Intermediário"],
              ["avancado", "Avançado"],
            ]}
            aoMudar={(v) => mudar("nivel", v as Nivel)}
          />
        </Grupo>

        <Grupo titulo="ROTINA">
          <Escolha
            nome="dias_semana"
            rotulo="Dias de treino por semana"
            valor={form.dias_semana}
            erro={campos.dias_semana}
            compacta
            opcoes={["1", "2", "3", "4", "5", "6", "7"].map((d) => [d, d])}
            aoMudar={(v) => mudar("dias_semana", v)}
          />
          {numero("minutos_sessao", "Minutos por sessão", "min", 15, 180)}
          <Escolha
            nome="equipamento"
            rotulo="Onde você treina"
            valor={form.equipamento}
            erro={campos.equipamento}
            opcoes={[
              ["academia", "Academia"],
              ["casa_halteres", "Casa, com halteres"],
              ["peso_corporal", "Só peso corporal"],
            ]}
            aoMudar={(v) => mudar("equipamento", v as Equipamento)}
          />
        </Grupo>

        <Grupo
          titulo="CORRIDA"
          nota="Opcional. Sem escolher: iniciante, corrida no mesmo dia da academia se você treina até 4 dias (em dias separados a partir de 5) e 3 corridas por semana."
          destaque
        >
          <Escolha
            nome="nivel_corrida"
            rotulo="Experiência com corrida"
            valor={form.nivel_corrida}
            opcoes={[
              ["iniciante", "Começando agora"],
              ["intermediario", "Corro às vezes"],
              ["avancado", "Corro com frequência"],
            ]}
            aoMudar={(v) => mudar("nivel_corrida", v as Nivel)}
          />
          <Escolha
            nome="corrida_quando"
            rotulo="Quando correr"
            valor={form.corrida_quando}
            opcoes={[
              ["automatico", "Automático"],
              ["mesmo_dia", "Depois da musculação"],
              ["dias_separados", "Em dias separados"],
            ]}
            aoMudar={(v) => mudar("corrida_quando", v as CorridaQuando)}
          />
          <Escolha
            nome="corridas_semana"
            rotulo="Corridas por semana"
            valor={form.corridas_semana}
            compacta
            opcoes={["1", "2", "3", "4", "5", "6", "7"].map((d) => [d, d])}
            aoMudar={(v) => mudar("corridas_semana", v)}
          />
        </Grupo>

        <Grupo titulo="OPCIONAL" nota="Deixe em branco o que não souber." destaque>
          <div className="grade-2">
            {numero("percentual_gordura", "Gordura corporal", "%", 3, 60, false)}
            {numero("cintura_cm", "Cintura", "cm", 40, 200, false)}
          </div>
          <label className="campo">
            <span className="campo__rotulo">
              Condições de saúde <span className="mudo">ex.: hipertensão, dor no joelho esquerdo</span>
            </span>
            <textarea
              rows={3}
              maxLength={500}
              value={form.condicoes_saude}
              onChange={(e) => mudar("condicoes_saude", e.target.value)}
              aria-invalid={"condicoes_saude" in campos}
            />
            <span className="campo__dica">
              Dado sensível: fica só no seu perfil e serve para o coach adaptar o plano.{" "}
              <span className="vt">{form.condicoes_saude.length}/500</span>
            </span>
            {campos.condicoes_saude && <span className="campo__erro">{campos.condicoes_saude}</span>}
          </label>
        </Grupo>

        <Grupo
          titulo="NUTRICIONISTA"
          nota="Meta prescrita por nutricionista (opcional). Com as kcal preenchidas, ela vale no lugar da fórmula; macros em branco são calculados. Apague as kcal para voltar à fórmula."
          destaque
        >
          {numero("meta_profissional_kcal", "Calorias por dia", "kcal", 1000, 5000, false)}
          <div className="grade-3">
            {numero("meta_profissional_proteina_g", "Proteína", "g", 0, 500, false)}
            {numero("meta_profissional_carbo_g", "Carbo", "g", 0, 1000, false)}
            {numero("meta_profissional_gordura_g", "Gordura", "g", 0, 300, false)}
          </div>
        </Grupo>

        {erro && (
          <p className="aviso" role="alert">
            {erro}
          </p>
        )}
        <div className="perfil__acoes">
          <button type="submit" className="botao" disabled={salvando}>
            {salvando ? "Calculando…" : novo ? "Calcular minhas metas" : "Salvar e recalcular"}
          </button>
        </div>
      </form>

      {!novo && <Memorias />}
    </div>
  );
}

function Grupo({
  titulo,
  nota,
  destaque = false,
  children,
}: {
  titulo: string;
  nota?: string;
  destaque?: boolean;
  children: ReactNode;
}) {
  return (
    <fieldset className={destaque ? "grupo grupo--opcional" : "grupo"}>
      <legend className="rotulo px">{titulo}</legend>
      {nota && <p className="mudo grupo__nota">{nota}</p>}
      {children}
    </fieldset>
  );
}

function Escolha({
  nome,
  rotulo,
  valor,
  opcoes,
  aoMudar,
  erro,
  compacta = false,
}: {
  nome: string;
  rotulo: string;
  valor: string;
  opcoes: [string, string][];
  aoMudar: (v: string) => void;
  erro?: string;
  compacta?: boolean;
}) {
  return (
    <div className="campo" role="radiogroup" aria-label={rotulo}>
      <span className="campo__rotulo">{rotulo}</span>
      <div className={compacta ? "escolha escolha--compacta" : "escolha"}>
        {opcoes.map(([v, texto]) => (
          <label key={v} className={valor === v ? "escolha__op escolha__op--on" : "escolha__op"}>
            <input type="radio" name={nome} value={v} checked={valor === v} onChange={() => aoMudar(v)} />
            <span className={compacta ? "vt" : undefined}>{texto}</span>
          </label>
        ))}
      </div>
      {erro && <span className="campo__erro">{erro}</span>}
    </div>
  );
}

function PainelMetas({ metas, destaque }: { metas: Metas; destaque: boolean }) {
  return (
    <section className={destaque ? "metas metas--nova" : "metas"} aria-label="Suas metas diárias" aria-live="polite">
      <div className="linha">
        <h2 className="rotulo px">{destaque ? "METAS NOVAS" : "METAS DO DIA"}</h2>
        {destaque && (
          <Link to="/" className="link-acento">
            ir para Hoje →
          </Link>
        )}
      </div>
      <div className="metas__kcal">
        <span className="vt metas__grande">{metas.kcal}</span>
        <span className="vt mudo">kcal/dia</span>
        <span className="meta-origem">{rotuloOrigem(metas.origem)}</span>
      </div>
      <dl className="metas__grade">
        <div style={{ color: "var(--prot)" }}>
          <dt className="px">PROT</dt>
          <dd className="vt">{metas.proteina_g}g</dd>
        </div>
        <div style={{ color: "var(--carb)" }}>
          <dt className="px">CARB</dt>
          <dd className="vt">{metas.carbo_g}g</dd>
        </div>
        <div style={{ color: "var(--gord)" }}>
          <dt className="px">GORD</dt>
          <dd className="vt">{metas.gordura_g}g</dd>
        </div>
        <div style={{ color: "var(--agua)" }}>
          <dt className="px">AGUA</dt>
          <dd className="vt">{litros(metas.agua_ml)} L</dd>
        </div>
      </dl>
    </section>
  );
}
