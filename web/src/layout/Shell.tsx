import { useEffect, useState } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate, useSearchParams } from "react-router";
import { api, type Me } from "../api";
import Coach from "../coach/Coach";
import { useDesktop } from "../coach/abrir";
import { Icone, Marca, type NomeIcone } from "../ui";

const TELAS: { para: string; nome: string; curto: string; icone: NomeIcone }[] = [
  { para: "/", nome: "Hoje", curto: "HOJE", icone: "hoje" },
  { para: "/comida", nome: "Comida", curto: "COMIDA", icone: "comida" },
  { para: "/treino", nome: "Treino", curto: "TREINO", icone: "treino" },
  { para: "/progresso", nome: "Progresso", curto: "PROG", icone: "progresso" },
];

/**
 * Moldura das telas logadas.
 * < 1024 px: conteúdo + navegação inferior + botão "AI" (abre o coach em tela cheia).
 * ≥ 1024 px: barra lateral | conteúdo | painel do coach fixo à direita.
 */
export default function Shell() {
  const navegar = useNavigate();
  const { pathname } = useLocation();
  const [me, setMe] = useState<Me | null>(null);
  // Um coach montado por vez: no painel (desktop) ou na rota /coach (celular).
  const desktop = useDesktop();

  useEffect(() => {
    let vivo = true;
    api
      .me()
      .then((m) => {
        if (!vivo) return;
        setMe(m);
        if (!m.perfil_completo && pathname !== "/perfil") navegar("/perfil", { replace: true });
      })
      .catch(() => {
        /* 401 já redirecionou para /entrar */
      });
    return () => {
      vivo = false;
    };
    // Só na montagem: o guarda roda uma vez ao abrir o app.
  }, []);

  async function sair() {
    // Mesmo se a chamada falhar, a saída visual acontece; o cookie expira no servidor.
    await api.logout().catch(() => undefined);
    navegar("/entrar", { replace: true });
  }

  const noCoach = pathname === "/coach";

  return (
    <div className={noCoach ? "shell shell--coach" : "shell"}>
      <aside className="lateral" aria-label="Navegação principal">
        <Link to="/" className="lateral__marca">
          <Marca tamanho={26} />
          <span className="px">HACHIBU</span>
        </Link>
        <nav className="lateral__nav">
          {TELAS.map((t) => (
            <NavLink key={t.para} to={t.para} end className="lateral__item">
              <Icone nome={t.icone} />
              <span>{t.nome}</span>
            </NavLink>
          ))}
        </nav>
        <div className="lateral__rodape">
          <NavLink to="/perfil" className="lateral__item">
            <Icone nome="perfil" />
            <span>Perfil e metas</span>
          </NavLink>
          <button type="button" className="lateral__item lateral__sair" onClick={sair}>
            <Icone nome="sair" />
            <span>Sair</span>
          </button>
          {me && <div className="lateral__email mudo">{me.email}</div>}
        </div>
      </aside>

      <main className="conteudo">
        <Outlet />
      </main>

      {desktop && (
        <aside className="coach-painel" aria-label="Coach">
          <Coach />
        </aside>
      )}

      {!noCoach && (
        <Link to="/coach" className="fab px" aria-label="Abrir o coach">
          AI
        </Link>
      )}

      <nav className="inferior px" aria-label="Navegação principal">
        {TELAS.map((t) => (
          <NavLink key={t.para} to={t.para} end className="inferior__item">
            <Icone nome={t.icone} tamanho={18} />
            <span>{t.curto}</span>
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

/** /coach no celular; no desktop o coach já está no painel ao lado. */
export function TelaCoach() {
  const desktop = useDesktop();
  const [params, setParams] = useSearchParams();
  // Lido uma vez: "?foto=1" vem do botão "por foto" da tela de comida.
  const [comCamera] = useState(() => params.get("foto") === "1");

  useEffect(() => {
    if (params.has("foto")) setParams({}, { replace: true });
    // Só limpa a URL na montagem.
  }, []);

  if (desktop) {
    return (
      <div className="em-breve">
        <div className="rotulo px">COACH</div>
        <h1 className="em-breve__titulo">O coach fica no painel ao lado</h1>
        <p className="mudo">No computador a conversa acompanha todas as telas, na coluna da direita.</p>
      </div>
    );
  }
  return (
    <div className="tela-coach">
      <Coach abrirCamera={comCamera} />
    </div>
  );
}

export function EmBreve({
  titulo,
  etapa,
  chamada = "Em breve",
}: {
  titulo: string;
  etapa: string;
  chamada?: string;
}) {
  return (
    <div className="em-breve">
      <div className="rotulo px">{titulo.toUpperCase()}</div>
      <h1 className="em-breve__titulo">{chamada}</h1>
      <p className="mudo">{etapa}</p>
      <div className="em-breve__blocos" aria-hidden="true">
        {Array.from({ length: 8 }, (_, i) => (
          <i key={i} style={{ opacity: 0.15 + i * 0.1 }} />
        ))}
      </div>
    </div>
  );
}
