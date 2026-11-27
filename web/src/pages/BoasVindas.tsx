import { Link } from "react-router";
import Cerejeira from "../components/Cerejeira";

const RECURSOS = [
  {
    rotulo: "FOTO DO PRATO",
    texto:
      "Mande a foto e o coach separa os alimentos, estima as porções e calcula pela tabela TACO. Você confirma antes de registrar.",
  },
  {
    rotulo: "METAS COM ORIGEM",
    texto:
      "Calculadas pelo seu corpo e objetivo, ou a prescrição do seu nutricionista. Nenhuma meta muda sem a sua aprovação.",
  },
  {
    rotulo: "UM COACH QUE LEMBRA",
    texto:
      "Pergunte quanto falta de proteína ou o que jantar antes do longão. Ele olha os seus registros antes de responder.",
  },
  {
    rotulo: "TREINO E CORRIDA",
    texto: "Em breve: plano de musculação e corrida que se ajusta à sua semana, do jeito que ela acontece.",
  },
];

export default function BoasVindas() {
  return (
    <main className="landing">
      <section className="landing__heroi">
        <Cerejeira />
        <div className="landing__texto">
          <h1 className="landing__nome px">HACHIBU</h1>
          <p className="landing__lema">
            Seu coach de treino, corrida e dieta.
            <br />
            Um dia de cada vez.
          </p>
          <div className="landing__ctas">
            <Link className="botao botao--cheio px" to="/cadastro">
              CRIAR CONTA
            </Link>
            <Link className="botao px" to="/entrar">
              ENTRAR
            </Link>
          </div>
        </div>
      </section>

      <section className="landing__secao">
        <h2 className="rotulo px">O QUE ELE FAZ</h2>
        <ul className="landing__recursos">
          {RECURSOS.map((r) => (
            <li key={r.rotulo} className="landing__recurso">
              <h3 className="px">{r.rotulo}</h3>
              <p>{r.texto}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="landing__secao landing__nomeacao">
        <h2 className="rotulo px">DE ONDE VEM O NOME</h2>
        <p className="landing__kanji" lang="ja">
          腹八分
        </p>
        <p>
          Em Okinawa existe um costume antigo: comer até a barriga estar oito partes cheia, de dez.{" "}
          <em>Hara hachi bu</em> quer dizer exatamente isso. É uma ideia de equilíbrio, não de restrição: parar
          um pouco antes, todo dia, sem sofrer.
        </p>
        <p>
          E o <em>hachi</em> (八) é o número 8. Daí a cara de videogame de 8 e 16 bits. Um dia de cada vez, um
          pixel de cada vez.
        </p>
      </section>

      <footer className="landing__rodape">
        <span>
          Cerejeira:{" "}
          <a href="https://infallible.itch.io/pack-of-sakura-trees" target="_blank" rel="noreferrer">
            pixel art de Infallible
          </a>
          , recolorida para o verde do Hachibu.
        </span>
        <Link to="/entrar">Já tenho conta</Link>
      </footer>
    </main>
  );
}
