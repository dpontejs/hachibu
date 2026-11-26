import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router";
import { api, ApiError, mensagemDeErro } from "../api";
import { TelaDeEntrada } from "./Entrar";

export default function Cadastro() {
  const navegar = useNavigate();
  const [email, setEmail] = useState("");
  const [senha, setSenha] = useState("");
  const [convite, setConvite] = useState("");
  const [erro, setErro] = useState<string | null>(null);
  const [campos, setCampos] = useState<Record<string, string>>({});
  const [enviando, setEnviando] = useState(false);

  async function enviar(ev: FormEvent) {
    ev.preventDefault();
    setEnviando(true);
    setErro(null);
    setCampos({});
    try {
      await api.signup(email, senha, convite);
      navegar("/perfil", { replace: true });
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setErro("Convite inválido.");
      else if (e instanceof ApiError && e.status === 409) setErro("Esse e-mail já tem conta. Tente entrar.");
      else {
        if (e instanceof ApiError) setCampos(e.campos);
        setErro(mensagemDeErro(e));
      }
    } finally {
      setEnviando(false);
    }
  }

  return (
    <TelaDeEntrada titulo="CRIAR CONTA">
      <form className="formulario" onSubmit={enviar}>
        <label className="campo">
          <span className="campo__rotulo">E-mail</span>
          <input
            type="email"
            autoComplete="email"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={"email" in campos}
          />
          {campos.email && <span className="campo__erro">{campos.email}</span>}
        </label>
        <label className="campo">
          <span className="campo__rotulo">
            Senha <span className="mudo">mínimo 8 caracteres</span>
          </span>
          <input
            type="password"
            autoComplete="new-password"
            required
            minLength={8}
            value={senha}
            onChange={(e) => setSenha(e.target.value)}
            aria-invalid={"senha" in campos}
          />
          {campos.senha && <span className="campo__erro">{campos.senha}</span>}
        </label>
        <label className="campo">
          <span className="campo__rotulo">Código de convite</span>
          <input
            type="text"
            autoComplete="off"
            autoCapitalize="none"
            spellCheck={false}
            required
            value={convite}
            onChange={(e) => setConvite(e.target.value)}
          />
        </label>
        {erro && (
          <p className="aviso" role="alert">
            {erro}
          </p>
        )}
        <button type="submit" className="botao" disabled={enviando}>
          {enviando ? "Criando…" : "Criar conta"}
        </button>
      </form>
      <p className="entrada__troca">
        Já tem conta? <Link to="/entrar">Entrar</Link>
      </p>
    </TelaDeEntrada>
  );
}
