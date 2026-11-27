import { useCallback, useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router";
import {
  api,
  mensagemDeErro,
  type ExercicioSessao,
  type ResumoSessao,
  type SessaoTreino as Sessao,
  type UltimaVez,
} from "../api";

const kg = (v: number | null) => (v === null ? "corpo" : `${String(v).replace(".", ",")} kg`);
const relogio = (s: number) => `${Math.floor(s / 60)}:${String(Math.max(0, s) % 60).padStart(2, "0")}`;

function textoUltima(u: UltimaVez): string {
  const series = u.series.map((s) => `${kg(s.carga_kg)} × ${s.reps}`).join(", ");
  return `Última vez: ${series}` + (u.local ? ` · ${u.local}` : "");
}

/** Valores iniciais de uma linha: o que já foi feito, senão a última vez, senão vazio. */
function inicial(e: ExercicioSessao, ordem: number): { carga: string; reps: string } {
  const feita = e.feitas.find((f) => f.ordem === ordem);
  if (feita) return { carga: feita.carga_kg === null ? "" : String(feita.carga_kg), reps: String(feita.reps) };
  const anterior = e.ultima?.series[ordem] ?? e.ultima?.series.at(-1);
  if (anterior)
    return { carga: anterior.carga_kg === null ? "" : String(anterior.carga_kg), reps: String(anterior.reps) };
  return { carga: "", reps: String(e.reps_min) };
}

function Buscar({ onEscolher, onFechar }: { onEscolher: (id: string) => void; onFechar: () => void }) {
  const [q, setQ] = useState("");
  const [achados, setAchados] = useState<{ id: string; nome: string; grupo: string }[]>([]);
  useEffect(() => {
    if (q.trim().length < 2) return setAchados([]);
    let vivo = true;
    const t = window.setTimeout(() => {
      api
        .buscarExercicios(q.trim())
        .then((r) => vivo && setAchados(r.slice(0, 12)))
        .catch(() => vivo && setAchados([]));
    }, 200);
    return () => {
      vivo = false;
      window.clearTimeout(t);
    };
  }, [q]);
  return (
    <div className="sessao__busca">
      <input
        type="search"
        aria-label="Buscar exercício"
        placeholder="Buscar exercício (ex.: remada)"
        autoFocus
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onKeyDown={(e) => e.key === "Escape" && onFechar()}
      />
      <ul>
        {achados.map((a) => (
          <li key={a.id}>
            <button type="button" onClick={() => onEscolher(a.id)}>
              {a.nome}
            </button>
          </li>
        ))}
      </ul>
      <button type="button" className="sessao__link" onClick={onFechar}>
        cancelar
      </button>
    </div>
  );
}

function Exercicio({
  e,
  ocupado,
  onMarcar,
  onDesmarcar,
  onTrocar,
}: {
  e: ExercicioSessao;
  ocupado: boolean;
  onMarcar: (ordem: number, carga: number | null, reps: number) => void;
  onDesmarcar: (ordem: number) => void;
  onTrocar: (exercicioId: string) => void;
}) {
  const feitasMax = e.feitas.reduce((m, f) => Math.max(m, f.ordem + 1), 0);
  const [extras, setExtras] = useState(0);
  const linhas = Math.max(e.series_planejadas, feitasMax) + extras;
  const [valores, setValores] = useState<Record<number, { carga: string; reps: string }>>({});
  const [trocando, setTrocando] = useState(false);
  const valor = (ordem: number) => valores[ordem] ?? inicial(e, ordem);
  const mudar = (ordem: number, campo: "carga" | "reps", v: string) =>
    setValores((atual) => ({ ...atual, [ordem]: { ...valor(ordem), [campo]: v } }));

  return (
    <section className="sessao__exercicio" aria-label={e.nome}>
      <header>
        <h2>{e.nome}</h2>
        <button type="button" className="sessao__link" onClick={() => setTrocando((t) => !t)} disabled={ocupado}>
          trocar
        </button>
      </header>
      <p className="mudo sessao__meta">
        {e.ultima ? textoUltima(e.ultima) : "Primeira vez com este exercício."} · alvo {e.reps_min}–{e.reps_max} reps
      </p>
      {trocando && (
        <Buscar
          onFechar={() => setTrocando(false)}
          onEscolher={(id) => {
            setTrocando(false);
            setValores({});
            onTrocar(id);
          }}
        />
      )}
      <ol className="sessao__series">
        {Array.from({ length: linhas }, (_, ordem) => {
          const feita = e.feitas.some((f) => f.ordem === ordem);
          const v = valor(ordem);
          return (
            <li key={ordem} className={feita ? "sessao__serie sessao__serie--feita" : "sessao__serie"}>
              <span className="vt sessao__n">{ordem + 1}</span>
              <label>
                <input
                  type="number"
                  inputMode="decimal"
                  step="0.5"
                  min={0}
                  aria-label={`Carga da série ${ordem + 1} (kg)`}
                  placeholder="kg"
                  value={v.carga}
                  disabled={feita}
                  onChange={(ev) => mudar(ordem, "carga", ev.target.value)}
                />
                <span className="mudo">kg</span>
              </label>
              <label>
                <input
                  type="number"
                  inputMode="numeric"
                  min={1}
                  aria-label={`Reps da série ${ordem + 1}`}
                  value={v.reps}
                  disabled={feita}
                  onChange={(ev) => mudar(ordem, "reps", ev.target.value)}
                />
                <span className="mudo">reps</span>
              </label>
              <button
                type="button"
                className={feita ? "sessao__check sessao__check--on" : "sessao__check"}
                aria-label={feita ? `Desmarcar série ${ordem + 1}` : `Marcar série ${ordem + 1}`}
                disabled={ocupado || (!feita && !(Number(v.reps) >= 1))}
                onClick={() =>
                  feita
                    ? onDesmarcar(ordem)
                    : onMarcar(ordem, v.carga.trim() === "" ? null : Number(v.carga), Number(v.reps))
                }
              >
                ✓
              </button>
            </li>
          );
        })}
      </ol>
      <button type="button" className="sessao__link" onClick={() => setExtras((n) => n + 1)}>
        + série
      </button>
    </section>
  );
}

/** A sessão de musculação: cada série marcada é salva na hora; dá para fechar o app e continuar depois. */
export default function SessaoTreino() {
  const { id } = useParams();
  const sessaoId = Number(id);
  const navegar = useNavigate();
  const [sessao, setSessao] = useState<Sessao | null>(null);
  const [erro, setErro] = useState<string | null>(null);
  const [ocupado, setOcupado] = useState(false);
  const [locais, setLocais] = useState<string[]>([]);
  const [local, setLocal] = useState("");
  const [descansoFim, setDescansoFim] = useState<number | null>(null);
  const [agora, setAgora] = useState(Date.now());
  const [acrescentando, setAcrescentando] = useState(false);
  const [resumo, setResumo] = useState<ResumoSessao | null>(null);

  useEffect(() => {
    api
      .sessao(sessaoId)
      .then((s) => {
        setSessao(s);
        setLocal(s.local ?? "");
      })
      .catch((e) => setErro(mensagemDeErro(e)));
    api
      .locais()
      .then(setLocais)
      .catch(() => {});
  }, [sessaoId]);

  useEffect(() => {
    const t = window.setInterval(() => setAgora(Date.now()), 1000);
    return () => window.clearInterval(t);
  }, []);

  const acao = useCallback(async (fazer: () => Promise<Sessao>) => {
    setOcupado(true);
    setErro(null);
    try {
      setSessao(await fazer());
      return true;
    } catch (e) {
      setErro(mensagemDeErro(e));
      return false;
    } finally {
      setOcupado(false);
    }
  }, []);

  if (resumo)
    return (
      <div className="sessao">
        <section className="sessao__resumo" aria-label="Treino concluído">
          <h1 className="rotulo px">
            TREINO CONCLUIDO
          </h1>
          <p className="vt sessao__resumo-num">{resumo.duracao_min} min</p>
          <p>
            {resumo.series} séries · {resumo.volume_kg.toLocaleString("pt-BR")} kg de volume
          </p>
          <button type="button" className="botao" onClick={() => navegar("/treino")}>
            VOLTAR AO TREINO
          </button>
        </section>
      </div>
    );

  if (!sessao)
    return erro ? (
      <p className="aviso" role="alert">
        {erro}
      </p>
    ) : (
      <p className="carregando px">CARREGANDO</p>
    );

  const restante = descansoFim ? Math.round((descansoFim - agora) / 1000) : 0;
  const decorrido = Math.round((agora - new Date(sessao.iniciada_em).getTime()) / 1000);

  async function finalizar() {
    const feitas = sessao!.exercicios.reduce((n, e) => n + e.feitas.length, 0);
    if (feitas === 0 && !window.confirm("Nenhuma série marcada. Finalizar mesmo assim?")) return;
    setOcupado(true);
    try {
      setResumo(await api.finalizarSessao(sessaoId));
    } catch (e) {
      setErro(mensagemDeErro(e));
    } finally {
      setOcupado(false);
    }
  }

  async function descartar() {
    if (!window.confirm("Descartar este treino? As séries marcadas serão apagadas.")) return;
    try {
      await api.descartarSessao(sessaoId);
      navegar("/treino");
    } catch (e) {
      setErro(mensagemDeErro(e));
    }
  }

  return (
    <div className="sessao">
      <header className="sessao__topo">
        <div>
          <span className="rotulo px">TREINO</span>
          <h1>{sessao.nome}</h1>
        </div>
        <span className="vt sessao__tempo" aria-label="Tempo de treino">
          {relogio(decorrido)}
        </span>
      </header>

      <label className="sessao__local">
        <span className="mudo">Local</span>
        <input
          list="locais-usados"
          placeholder="ex.: Smart Fit centro (opcional)"
          value={local}
          maxLength={60}
          onChange={(e) => setLocal(e.target.value)}
          onBlur={() => {
            if ((sessao.local ?? "") !== local.trim()) void acao(() => api.mudarLocal(sessaoId, local.trim() || null));
          }}
        />
        <datalist id="locais-usados">
          {locais.map((l) => (
            <option key={l} value={l} />
          ))}
        </datalist>
      </label>

      {sessao.exercicios.map((e) => (
        <Exercicio
          key={`${e.ordem}-${e.exercicio_id}`}
          e={e}
          ocupado={ocupado}
          onMarcar={(ordem, carga, reps) =>
            void acao(() => api.marcarSerie(sessaoId, { ordem_exercicio: e.ordem, ordem, carga_kg: carga, reps })).then(
              (ok) => {
                if (!ok) return;
                setAgora(Date.now());
                setDescansoFim(Date.now() + e.descanso_s * 1000);
              },
            )
          }
          onDesmarcar={(ordem) => void acao(() => api.desmarcarSerie(sessaoId, e.ordem, ordem))}
          onTrocar={(novo) => void acao(() => api.trocarExercicio(sessaoId, e.ordem, novo))}
        />
      ))}

      {acrescentando ? (
        <Buscar
          onFechar={() => setAcrescentando(false)}
          onEscolher={(novo) => {
            setAcrescentando(false);
            void acao(() => api.acrescentarExercicio(sessaoId, novo));
          }}
        />
      ) : (
        <button type="button" className="sessao__link" onClick={() => setAcrescentando(true)}>
          + exercício
        </button>
      )}

      {erro && (
        <p className="aviso" role="alert">
          {erro}
        </p>
      )}

      {descansoFim && restante > 0 && (
        <div className="sessao__descanso" role="timer" aria-label="Descanso">
          <span className="rotulo px">DESCANSO</span>
          <span className="vt">{relogio(restante)}</span>
          <button type="button" className="sessao__link" onClick={() => setDescansoFim(null)}>
            pular
          </button>
        </div>
      )}

      <div className="sessao__acoes">
        <button type="button" className="botao" onClick={() => void finalizar()} disabled={ocupado}>
          FINALIZAR
        </button>
        <button type="button" className="sessao__link" onClick={() => void descartar()}>
          descartar treino
        </button>
      </div>
    </div>
  );
}
