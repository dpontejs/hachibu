import { useEffect, useId, useState, type CSSProperties } from "react";
import { api, type ArgsAjusteMetas, type Metas, type PendenciaCoach } from "../api";

const LINHAS: { campo: keyof Omit<ArgsAjusteMetas, "justificativa">; rotulo: string; nome: string; unidade: string; cor: string }[] = [
  { campo: "kcal", rotulo: "KCAL", nome: "kcal", unidade: "", cor: "var(--acento)" },
  { campo: "proteina_g", rotulo: "PROT", nome: "proteína", unidade: "g", cor: "var(--prot)" },
  { campo: "carbo_g", rotulo: "CARB", nome: "carbo", unidade: "g", cor: "var(--carb)" },
  { campo: "gordura_g", rotulo: "GORD", nome: "gordura", unidade: "g", cor: "var(--gord)" },
];

function numero(v: unknown): number | null {
  return typeof v === "number" && Number.isFinite(v) ? v : null;
}

/**
 * Card de aprovação de uma ação que o coach quer fazer (hoje, ajustar a meta).
 * Nada muda no plano até o aluno tocar em Aprovar.
 */
export default function Aprovacao({
  pendente,
  decidindo,
  onDecidir,
}: {
  pendente: PendenciaCoach;
  decidindo: boolean;
  onDecidir: (aprovar: boolean, motivo?: string) => void;
}) {
  const titulo = useId();
  const [metas, setMetas] = useState<Metas | null>(null);
  const [recusando, setRecusando] = useState(false);
  const [motivo, setMotivo] = useState("");
  const ajuste = pendente.ferramenta === "ajustar_metas";

  useEffect(() => {
    if (!ajuste) return;
    let vivo = true;
    api
      .hoje()
      .then((h) => vivo && setMetas(h.metas))
      .catch(() => {
        /* sem a meta atual o card mostra só a proposta */
      });
    return () => {
      vivo = false;
    };
  }, [ajuste]);

  const args = pendente.args;
  const justificativa = typeof args.justificativa === "string" ? args.justificativa : null;
  const linhas = ajuste ? LINHAS.filter((l) => numero(args[l.campo]) !== null) : [];

  return (
    <section className="aprovacao" role="region" aria-labelledby={titulo}>
      <header className="aprovacao__topo">
        <span className="aprovacao__sinal" aria-hidden="true" />
        <h3 id={titulo} className="rotulo px">
          {ajuste ? "PEDIDO DE AJUSTE" : "PEDIDO DO COACH"}
        </h3>
      </header>

      {linhas.length > 0 ? (
        <dl className="aprovacao__metas">
          {linhas.map((l) => {
            const nova = numero(args[l.campo])!;
            const atual = metas ? numero(metas[l.campo]) : null;
            const delta = atual !== null ? Math.round(nova - atual) : null;
            return (
              <div key={l.campo} className="aprovacao__linha" style={{ "--c": l.cor } as CSSProperties}>
                <dt className="px aprovacao__rotulo">{l.rotulo}</dt>
                <dd className="vt aprovacao__atual" aria-label={`${l.nome} atual`}>
                  {atual !== null ? `${Math.round(atual)}${l.unidade}` : "…"}
                </dd>
                <dd className="px aprovacao__seta" aria-hidden="true">
                  &gt;
                </dd>
                <dd className="vt aprovacao__nova" aria-label={`${l.nome} proposta`}>
                  {Math.round(nova)}
                  {l.unidade}
                </dd>
                <dd className="vt aprovacao__delta" aria-hidden="true">
                  {delta === null || delta === 0 ? "" : delta > 0 ? `+${delta}` : `−${Math.abs(delta)}`}
                </dd>
              </div>
            );
          })}
        </dl>
      ) : (
        <p className="aprovacao__descricao">{pendente.descricao}</p>
      )}

      {justificativa && <blockquote className="aprovacao__porque">{justificativa}</blockquote>}

      {recusando ? (
        <div className="aprovacao__recusa">
          <label className="campo">
            <span className="campo__rotulo">
              Motivo da recusa <span className="mudo">(opcional)</span>
            </span>
            <textarea
              rows={2}
              maxLength={500}
              value={motivo}
              autoFocus
              onChange={(e) => setMotivo(e.target.value)}
              placeholder="Ex.: semana de viagem, prefiro manter"
            />
          </label>
          <div className="aprovacao__botoes">
            <button type="button" className="botao-fantasma" onClick={() => setRecusando(false)} disabled={decidindo}>
              Voltar
            </button>
            <button
              type="button"
              className="botao botao--perigo"
              onClick={() => onDecidir(false, motivo)}
              disabled={decidindo}
            >
              {decidindo ? "Enviando…" : "Confirmar recusa"}
            </button>
          </div>
        </div>
      ) : (
        <div className="aprovacao__botoes">
          <button type="button" className="botao-fantasma" onClick={() => setRecusando(true)} disabled={decidindo}>
            Recusar
          </button>
          <button type="button" className="botao" onClick={() => onDecidir(true)} disabled={decidindo}>
            {decidindo ? "Aplicando…" : "Aprovar"}
          </button>
        </div>
      )}
    </section>
  );
}
