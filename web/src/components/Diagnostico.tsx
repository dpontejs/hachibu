import type { ReactNode } from "react";
import type { Diagnostico as DadosDiagnostico } from "../api";
import { decimal, rotuloOrigem } from "../formato";

const FORMULA: Record<DadosDiagnostico["formula"], { nome: string; como: string }> = {
  "mifflin-st-jeor": {
    nome: "Mifflin-St Jeor",
    como: "Sai do seu peso, altura, idade e sexo.",
  },
  "katch-mcardle": {
    nome: "Katch-McArdle",
    como: "Sai da sua massa magra, por isso usa o % de gordura que você informou.",
  },
};

function explicarAjuste(ajuste: number): string {
  if (ajuste < 0) return "Déficit para perder gordura: comer um pouco menos do que você gasta.";
  if (ajuste > 0) return "Superávit para ganhar massa: comer um pouco mais do que você gasta.";
  return "Sem ajuste: o objetivo é manter o peso, então a meta fica no gasto.";
}

function explicarOrigem(origem: string | undefined): string {
  if (origem === "profissional") return "Prescrita pelo seu nutricionista. Vale no lugar da fórmula.";
  if (origem === "coach") return "O coach ajustou a meta a partir do seu progresso.";
  return "Gasto diário mais o ajuste do objetivo.";
}

/** Sinal de verdade (−) no lugar do hífen, e "+" explícito no superávit. */
function comSinal(n: number): string {
  const r = Math.round(n);
  if (r < 0) return `−${-r}`;
  if (r > 0) return `+${r}`;
  return "0";
}

/** Card "de onde vêm os números": cada linha com o valor e uma frase do porquê. */
export default function Diagnostico({ dados }: { dados: DadosDiagnostico }) {
  const formula = FORMULA[dados.formula] ?? FORMULA["mifflin-st-jeor"];
  const { metas } = dados;
  const avisos: string[] = [];
  if (dados.alerta_cintura) {
    avisos.push(
      "Cintura com metade da altura ou mais está ligada a maior risco para o coração. Vale conversar com um médico.",
    );
  }
  if (dados.abaixo_do_piso) {
    avisos.push(
      "Esta meta está abaixo do piso de segurança que a fórmula usaria. Siga só com acompanhamento profissional.",
    );
  }

  return (
    <section className="diag" aria-labelledby="diag-titulo">
      <div className="linha">
        <h2 id="diag-titulo" className="rotulo px">
          DIAGNOSTICO
        </h2>
        <span className="diag__sub mudo">de onde vêm os números</span>
      </div>

      {avisos.length > 0 && (
        <div className="diag__avisos" role="alert">
          {avisos.map((a) => (
            <p key={a} className="diag__aviso">
              <span className="px" aria-hidden="true">
                !
              </span>
              {a}
            </p>
          ))}
        </div>
      )}

      <dl className="diag__lista">
        <Linha rotulo="TMB" valor={<Num n={Math.round(dados.tmb)} unidade="kcal" />} extra={formula.nome}>
          O que seu corpo gasta em repouso, só para funcionar. {formula.como}
        </Linha>
        <Linha
          rotulo="GASTO"
          valor={<Num n={Math.round(dados.gasto_diario)} unidade="kcal" />}
          extra={`× ${decimal(dados.fator_atividade)}`}
        >
          A TMB vezes o fator de atividade, que sai dos seus dias de treino.
        </Linha>
        <Linha rotulo="AJUSTE" valor={<Num n={comSinal(dados.ajuste_objetivo)} unidade="kcal" />}>
          {explicarAjuste(dados.ajuste_objetivo)}
        </Linha>
        {dados.relacao_cintura_altura !== null && (
          <Linha
            rotulo="CINTURA/ALTURA"
            valor={<Num n={decimal(dados.relacao_cintura_altura, 2)} />}
            alerta={dados.alerta_cintura}
          >
            Sua cintura dividida pela altura. Abaixo de 0,5 é o recomendado.
          </Linha>
        )}
        <Linha rotulo="META" valor={<Num n={Math.round(metas.kcal)} unidade="kcal" />} extra={rotuloOrigem(metas.origem)}>
          {explicarOrigem(metas.origem)}{" "}
          <span className="diag__macros vt">
            <span style={{ color: "var(--prot)" }}>P {metas.proteina_g}g</span>
            <span style={{ color: "var(--carb)" }}>C {metas.carbo_g}g</span>
            <span style={{ color: "var(--gord)" }}>G {metas.gordura_g}g</span>
          </span>
        </Linha>
      </dl>
    </section>
  );
}

function Num({ n, unidade }: { n: number | string; unidade?: string }) {
  return (
    <>
      <span className="vt diag__num">{n}</span>
      {unidade && <span className="vt mudo diag__unidade">{unidade}</span>}
    </>
  );
}

function Linha({
  rotulo,
  valor,
  extra,
  alerta = false,
  children,
}: {
  rotulo: string;
  valor: ReactNode;
  extra?: string;
  alerta?: boolean;
  children: ReactNode;
}) {
  return (
    <div className={alerta ? "diag__linha diag__linha--alerta" : "diag__linha"}>
      <dt className="rotulo px">{rotulo}</dt>
      <dd className="diag__valor">
        {valor}
        {extra && <span className="diag__extra">{extra}</span>}
      </dd>
      <dd className="diag__porque">{children}</dd>
    </div>
  );
}
