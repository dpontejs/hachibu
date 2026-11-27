import { Link } from "react-router";
import Cerejeira from "../components/Cerejeira";

// Rótulos em fonte pixel ficam sem acento: a Press Start 2P não desenha maiúsculas acentuadas.

const PASSOS = [
  {
    titulo: "Conte quem você é",
    texto:
      "Peso, altura, objetivo e quantos dias você treina. O Hachibu calcula as suas metas de calorias, proteína, carboidrato, gordura e água, e mostra um diagnóstico explicando cada número. Se você tem uma prescrição do seu nutricionista, ela vale no lugar da fórmula.",
  },
  {
    titulo: "Registre do jeito mais fácil",
    texto:
      "Tire uma foto do prato, busque o alimento na tabela TACO ou simplesmente escreva para o coach: \"bebi 500 ml\", \"almocei arroz, feijão e frango\". A tela Hoje mostra na hora quanto você já comeu e quanto falta.",
  },
  {
    titulo: "Converse com o coach",
    texto:
      "Pergunte o que quiser sobre o seu dia. O coach consulta os seus registros antes de responder e, quando sugere uma mudança de meta, espera você aprovar.",
  },
];

const RECURSOS = [
  {
    rotulo: "FOTO DO PRATO",
    texto:
      "A IA identifica cada alimento e estima a porção; as calorias saem da tabela TACO, não de um palpite. Você confere a lista, corrige as gramas se precisar e só então registra.",
  },
  {
    rotulo: "TABELA TACO",
    texto:
      "593 alimentos da Tabela Brasileira de Composição de Alimentos (UNICAMP), com valores medidos em laboratório. Busca sem se preocupar com acento: \"pao frances\" acha o pão francês.",
  },
  {
    rotulo: "METAS COM ORIGEM",
    texto:
      "Toda meta diz de onde veio: da fórmula (Mifflin-St Jeor, ou Katch-McArdle se você souber o seu % de gordura), do seu nutricionista ou de um ajuste que você aprovou.",
  },
  {
    rotulo: "DIAGNOSTICO",
    texto:
      "Taxa metabólica basal, gasto diário, relação cintura/altura e o ajuste do seu objetivo, cada número com uma frase explicando o que significa.",
  },
  {
    rotulo: "COACH ESPECIALISTA",
    texto:
      "Antes de aconselhar, o coach carrega o conhecimento do assunto: nutrição, musculação ou corrida. Uma pergunta como \"amanhã tenho longão, o que janto?\" junta corrida e alimentação na mesma resposta.",
  },
  {
    rotulo: "VOCE DECIDE",
    texto:
      "O coach propõe e explica; você aprova ou recusa. Limites de segurança ficam no próprio sistema: nada de meta abaixo do piso saudável ou com déficit exagerado.",
  },
];

const EM_BREVE = [
  {
    rotulo: "MUSCULACAO",
    texto: "Plano semanal, registro de séries e cargas, progressão e troca de exercício pela conversa.",
  },
  {
    rotulo: "CORRIDA",
    texto: "Treinos leves, intervalados e longões, ritmos calculados pelo seu tempo nos 5 km e aumento de volume seguro.",
  },
  {
    rotulo: "CARDAPIO",
    texto: "Cardápio da semana montado pelas suas metas e preferências, com a lista de compras gerada sozinha.",
  },
];

function Logo() {
  return (
    <h1 className="landing__logo">
      <span className="landing__nome px">HACHIBU</span>
      <span className="landing__kanji-logo" lang="ja">
        腹八分
      </span>
    </h1>
  );
}

export default function BoasVindas() {
  return (
    <main className="landing">
      <section className="landing__heroi">
        <Cerejeira />
        <div className="landing__texto">
          <Logo />
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
        <h2 className="rotulo px">COMO FUNCIONA</h2>
        <ol className="landing__passos">
          {PASSOS.map((p, i) => (
            <li key={p.titulo} className="landing__passo">
              <span className="landing__numero vt">{i + 1}</span>
              <div>
                <h3>{p.titulo}</h3>
                <p>{p.texto}</p>
              </div>
            </li>
          ))}
        </ol>
      </section>

      <section className="landing__secao">
        <h2 className="rotulo px">O QUE ELE FAZ</h2>
        <ul className="landing__recursos landing__recursos--seis">
          {RECURSOS.map((r) => (
            <li key={r.rotulo} className="landing__recurso">
              <h3 className="px">{r.rotulo}</h3>
              <p>{r.texto}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="landing__secao">
        <h2 className="rotulo px">EM BREVE</h2>
        <ul className="landing__recursos landing__recursos--breve">
          {EM_BREVE.map((r) => (
            <li key={r.rotulo} className="landing__recurso">
              <h3 className="px">{r.rotulo}</h3>
              <p>{r.texto}</p>
            </li>
          ))}
        </ul>
      </section>

      <section className="landing__secao landing__colunas">
        <div>
          <h2 className="rotulo px">NO SEU CELULAR</h2>
          <p>O Hachibu é um app da web que você instala na tela inicial, sem loja de aplicativos:</p>
          <ul className="landing__lista">
            <li>
              <strong>iPhone:</strong> abra no Safari, toque em Compartilhar e depois em Adicionar à Tela de
              Início.
            </li>
            <li>
              <strong>Android:</strong> abra no Chrome, toque no menu (⋮) e depois em Instalar app.
            </li>
            <li>
              <strong>Computador:</strong> funciona no navegador, com o coach num painel ao lado.
            </li>
          </ul>
        </div>
        <div>
          <h2 className="rotulo px">SEUS DADOS</h2>
          <ul className="landing__lista">
            <li>As fotos não são guardadas: só a lista de alimentos e porções vai para o seu diário.</li>
            <li>O seu diário é só seu. O coach só enxerga os dados de quem está conversando com ele.</li>
            <li>O cadastro é por convite.</li>
            <li>
              O Hachibu ajuda a organizar a rotina, mas não substitui nutricionista, médico ou educador físico.
            </li>
          </ul>
        </div>
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
          E o <em>hachi</em> (<span className="landing__kanji-texto" lang="ja">八</span>) é o número 8. Daí a cara de videogame de 8 e 16 bits. Um dia de cada vez, um
          pixel de cada vez.
        </p>
      </section>

      <section className="landing__secao landing__final">
        <h2 className="rotulo px">PRONTO PARA COMECAR?</h2>
        <p>Com o seu código de convite, a conta sai em um minuto. Depois é só preencher o perfil.</p>
        <div className="landing__ctas">
          <Link className="botao botao--cheio px" to="/cadastro">
            CRIAR CONTA
          </Link>
          <Link className="botao px" to="/entrar">
            ENTRAR
          </Link>
        </div>
      </section>

      <footer className="landing__rodape">
        <span>
          Cerejeira:{" "}
          <a href="https://infallible.itch.io/pack-of-sakura-trees" target="_blank" rel="noreferrer">
            pixel art de Infallible
          </a>
          , recolorida para o verde do Hachibu. Tabela TACO: NEPA-UNICAMP.
        </span>
        <Link to="/entrar">Já tenho conta</Link>
      </footer>
    </main>
  );
}
