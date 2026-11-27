import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router";
import { api, mensagemDeErro, type CorridaDia, type DiaTreino, type PlanoTreino } from "../api";
import { abrirCoachCom } from "../coach/abrir";

const PEDIDO_MONTAR = "Quero montar meu plano de treino e corrida.";
const PEDIDO_AJUSTAR = "Meu plano de treino não cabe mais no meu perfil. Me ajuda a ajustar?";
const PEDIDO_PONTOS = "Vamos conversar sobre os pontos em aberto do meu plano de treino?";

const DIAS = ["SEG", "TER", "QUA", "QUI", "SEX", "SAB", "DOM"];
const SEMANAS_PROGRESSAO = 9;

/** 0 = segunda, pelo relógio do aparelho (o fuso de quem treina). */
const diaDeHoje = () => (new Date().getDay() + 6) % 7;

const minutos = (n: number) => `${String(n).replace(".", ",")} min`;

/** Texto da corrida do dia: blocos de corrida e caminhada, ou tipo e duração. */
export function descreverCorrida(c: CorridaDia): string {
  if (c.tipo === "corrida_caminhada" && c.corre_min) {
    if (!c.anda_min) return `${minutos(c.corre_min)} correndo sem parar`;
    return `${minutos(c.corre_min)} correndo + ${minutos(c.anda_min)} andando × ${c.repeticoes ?? 1}`;
  }
  if (c.tipo === "recuperacao") return `Recuperação · ${minutos(c.duracao_min)} de caminhada leve ou mobilidade`;
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
  const navegar = useNavigate();
  const pedir = (texto: string) => abrirCoachCom(texto, navegar);
  const [hojeIdx, setHojeIdx] = useState(diaDeHoje);

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

  // PWA aberto de um dia para o outro: o "hoje" muda quando a tela volta.
  useEffect(() => {
    const atualizar = () => document.visibilityState === "visible" && setHojeIdx(diaDeHoje());
    document.addEventListener("visibilitychange", atualizar);
    return () => document.removeEventListener("visibilitychange", atualizar);
  }, []);

  if (plano === undefined && !erro) return <p className="carregando px">CARREGANDO</p>;

  if (plano === null)
    return (
      <div className="treino">
        <h1 className="rotulo px">TREINO</h1>
        <section className="treino__vazio">
          <p>
            O seu plano de musculação e corrida nasce de uma conversa com o coach. Ele parte do seu perfil, das suas
            preferências e do que já sabe de você, explica cada escolha e pergunta o que estiver em aberto. Nada vale
            antes de você aprovar.
          </p>
          <p className="mudo">
            Vale conferir antes o <Link to="/perfil">Perfil</Link>: dias, minutos de musculação e de corrida, e quando
            correr.
          </p>
          <button type="button" className="botao" onClick={() => pedir(PEDIDO_MONTAR)}>
            MONTAR COM O COACH
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
      <div className="treino">
        <h1 className="rotulo px">TREINO</h1>
        <p className="aviso" role="alert">
          {erro}
        </p>
        <button type="button" className="botao" onClick={() => void carregar()}>
          TENTAR DE NOVO
        </button>
      </div>
    );

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
          <p>O plano não cabe no seu perfil atual:</p>
          <ul>
            {plano.avisos.map((a) => (
              <li key={a}>{a}</li>
            ))}
          </ul>
          <button type="button" className="botao" onClick={() => pedir(PEDIDO_AJUSTAR)}>
            AJUSTAR COM O COACH
          </button>
        </section>
      )}

      {plano.notas.length > 0 && (
        <section className="treino__notas" aria-label="Pontos para conversar">
          <ul className="mudo">
            {plano.notas.map((n) => (
              <li key={n}>{n}</li>
            ))}
          </ul>
          <button type="button" className="botao" onClick={() => pedir(PEDIDO_PONTOS)}>
            CONVERSAR COM O COACH
          </button>
        </section>
      )}

      {plano.tem_condicoes && (
        <p className="treino__condicoes mudo">
          Você tem condições físicas registradas: confira com o coach se o plano as respeita.
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
            <li
              key={d.dia}
              className={d.dia === hojeIdx ? "treino__dia treino__dia--hoje" : "treino__dia"}
              aria-current={d.dia === hojeIdx ? "date" : undefined}
            >
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
