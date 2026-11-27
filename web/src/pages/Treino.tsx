import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router";
import { api, mensagemDeErro, type CorridaDia, type DiaTreino, type PlanoTreino } from "../api";

const DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"];
const SEMANAS_PROGRESSAO = 9;

const minutos = (n: number) => `${String(n).replace(".", ",")} min`;

/** Texto da corrida do dia: blocos de corrida e caminhada, ou tipo e duração. */
export function descreverCorrida(c: CorridaDia): string {
  if (c.tipo === "corrida_caminhada" && c.corre_min) {
    if (!c.anda_min) return `${minutos(c.corre_min)} correndo sem parar`;
    return `${minutos(c.corre_min)} correndo + ${minutos(c.anda_min)} andando × ${c.repeticoes ?? 1}`;
  }
  const nome = { leve: "Leve", intervalado: "Intervalado", longao: "Longão", corrida_caminhada: "Corrida" }[c.tipo];
  return `${nome} · ${minutos(c.duracao_min)}`;
}

function resumo(d: DiaTreino): string {
  const partes: string[] = [];
  if (d.exercicios.length) partes.push(`${d.exercicios.length} exercícios`);
  if (d.corrida) partes.push(d.corrida.tipo === "corrida_caminhada" ? `corrida ${d.corrida.duracao_min} min` : descreverCorrida(d.corrida));
  return partes.join(" + ");
}

function Corrida({ c }: { c: CorridaDia }) {
  return (
    <div className="treino__corrida">
      <span className="rotulo px">CORRIDA</span>
      <p>{descreverCorrida(c)}</p>
      <p className="mudo">
        {c.tipo === "corrida_caminhada" && "5 min de caminhada antes · "}
        esforço {c.esforco_alvo} de 10 · {minutos(c.duracao_min)} no total
      </p>
    </div>
  );
}

function Exercicios({ d }: { d: DiaTreino }) {
  if (!d.exercicios.length) return null;
  return (
    <ol className="treino__exercicios">
      {d.exercicios.map((e, i) => (
        <li key={`${e.exercicio_id}-${i}`}>
          <span>{e.nome}</span>
          <span className="vt mudo">
            {e.series} × {e.reps_min}–{e.reps_max} · {e.descanso_s} s
          </span>
        </li>
      ))}
    </ol>
  );
}

/** A semana de treino: o de hoje em destaque, os outros dias abaixo. */
export default function Treino() {
  const [plano, setPlano] = useState<PlanoTreino | null | undefined>(undefined);
  const [erro, setErro] = useState<string | null>(null);
  const [gerando, setGerando] = useState(false);

  const carregar = useCallback(async () => {
    try {
      setPlano(await api.plano());
      setErro(null);
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }, []);

  useEffect(() => {
    void carregar();
  }, [carregar]);

  async function gerar(substituir: boolean) {
    if (substituir && !window.confirm("Gerar um plano base novo a partir do seu perfil? O plano atual fica no histórico."))
      return;
    setGerando(true);
    setErro(null);
    try {
      await api.gerarPlano(substituir);
      await carregar();
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setGerando(false);
    }
  }

  if (plano === undefined && !erro) return <p className="carregando px">CARREGANDO</p>;

  if (plano === null)
    return (
      <div className="treino">
        <h1 className="rotulo px">TREINO</h1>
        <section className="treino__vazio">
          <p>
            O Hachibu monta um plano base de musculação e corrida a partir do seu perfil: dias disponíveis, tempo por
            sessão, equipamento e nível. Depois você ajusta tudo com o coach.
          </p>
          <p className="mudo">
            Confira antes as preferências de corrida no <Link to="/perfil">Perfil</Link> (quando correr e quantas vezes
            por semana).
          </p>
          <button type="button" className="botao" onClick={() => void gerar(false)} disabled={gerando}>
            {gerando ? "MONTANDO…" : "MONTAR MEU PLANO"}
          </button>
        </section>
        {erro && (
          <p className="aviso" role="alert">
            {erro}
          </p>
        )}
      </div>
    );

  if (!plano)
    return (
      <p className="aviso" role="alert">
        {erro}
      </p>
    );

  const hojeIdx = (new Date().getDay() + 6) % 7;
  const hoje = plano.dias[hojeIdx];
  const temProgressao = plano.dias.some((d) => d.corrida?.progressao);

  return (
    <div className="treino">
      <header className="treino__topo">
        <h1 className="rotulo px">TREINO</h1>
        {temProgressao && (
          <span className="treino__semana mudo">
            Corrida: semana {plano.semana_corrida} de {SEMANAS_PROGRESSAO}
          </span>
        )}
      </header>

      {plano.avisos.length > 0 && (
        <section className="aviso treino__avisos" role="status">
          <p>Seu perfil mudou e o plano não cabe mais nele:</p>
          <ul>
            {plano.avisos.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <button type="button" className="botao" onClick={() => void gerar(true)} disabled={gerando}>
            GERAR NOVO PLANO BASE
          </button>
          <p className="mudo">Ou peça ao coach para adaptar o plano atual.</p>
        </section>
      )}

      {plano.tem_condicoes && (
        <p className="treino__condicoes mudo">
          Você tem condições físicas registradas. O plano base não as leva em conta: peça ao coach para adaptar.
        </p>
      )}

      <section className="treino__hoje" aria-labelledby="treino-hoje">
        <h2 id="treino-hoje" className="rotulo px">
          HOJE · {DIAS[hojeIdx]}
        </h2>
        <h3 className="treino__nome">{hoje.nome}</h3>
        {!hoje.exercicios.length && !hoje.corrida && <p className="mudo">Dia de descanso. Recuperar também é treino.</p>}
        <Exercicios d={hoje} />
        {hoje.corrida && <Corrida c={hoje.corrida} />}
      </section>

      <section aria-labelledby="treino-semana">
        <h2 id="treino-semana" className="rotulo px">
          SEMANA
        </h2>
        <ul className="treino__dias" aria-label="Semana">
          {plano.dias.map((d) => (
            <li key={d.dia} className={d.dia === hojeIdx ? "treino__dia treino__dia--hoje" : "treino__dia"}>
              <details>
                <summary>
                  <span className="px">{DIAS[d.dia]}</span>
                  <span className="treino__dia-nome">{d.nome}</span>
                  {resumo(d) && <span className="mudo">{resumo(d)}</span>}
                </summary>
                <Exercicios d={d} />
                {d.corrida && <Corrida c={d.corrida} />}
              </details>
            </li>
          ))}
        </ul>
      </section>

      {erro && (
        <p className="aviso" role="alert">
          {erro}
        </p>
      )}
    </div>
  );
}
