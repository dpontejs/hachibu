import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError, mensagemDeErro } from "../api";
import { Marca } from "../ui";

/** Moldura das telas sem sessão (entrar e cadastro). */
export function TelaDeEntrada({ titulo, children }: { titulo: string; children: ReactNode }) {
  return (
    <main className="entrada">
      <div className="entrada__marca">
        <Marca tamanho={56} />
        <div>
          <div className="px entrada__nome">HACHIBU</div>
          <div className="mudo entrada__lema">coma até 80%, treine com constância</div>
        </div>
      </div>
      <section className="entrada__caixa">
        <h1 className="rotulo px">{titulo}</h1>
        {children}
      </section>
    </main>
  );
}

export default function Entrar() {
  const navegar = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [enviando, setEnviando] = useState(false);

  async function enviar(ev: FormEvent) {
    ev.preventDefault();
    setEnviando(true);
    setErro(null);
    try {
      await api.login(email, senha);
      const me = await api.me();
      navegar(me.perfil_completo ? "/" : "/perfil", { replace: true });
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) setErro("E-mail ou senha não conferem.");
      else setErro(mensagemDeErro(e));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <TelaDeEntrada titulo="ENTRAR">
      <form className="formulario" onSubmit={enviar}>
        <label className="campo">
          <span className="campo__rotulo">E-mail</span>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </label>
        <label className="campo">
          <span className="campo__rotulo">Senha</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
          />
        </label>
        {erro && (
          <p className="aviso" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao" disabled={enviando}>
          {enviando ? "Entrando…" : "Entrar"}
        </button>
      </form>
      <p className="entrada__troca">
        Tem um convite? <Link to="/cadastro">Criar conta</Link>
      </p>
    </TelaDeEntrada>
  );
}
