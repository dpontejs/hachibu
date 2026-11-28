import { StrictMode, useEffect } from "react";
import { createRoot } from "react-dom/client";
import { BrowserRouter, Route, Routes, useNavigate } from "react-router";
import { definirNavegacao } from "./api";
import Shell, { EmBreve, TelaCoach } from "./layout/Shell";
import SessaoTreino from "./pages/SessaoTreino";
import Treino from "./pages/Treino";
import BoasVindas from "./pages/BoasVindas";
import Cadastro from "./pages/Cadastro";
import Comida from "./pages/Comida";
import Entrar from "./pages/Entrar";
import Hoje from "./pages/Hoje";
import Perfil from "./pages/Perfil";
import "./theme.css";

/** Deixa o api.ts redirecionar (401/409) pelo router, sem recarregar a página. */
function LigarNavegacao() {
  const navegar = useNavigate();
  useEffect(() => definirNavegacao((para) => navegar(para, { replace: true })), [navegar]);
  return null;
}

function App() {
  return (
    <BrowserRouter>
      <LigarNavegacao />
      <Routes>
        <Route path="/boas-vindas" element={<BoasVindas />} />
        <Route path="/entrar" element={<Entrar />} />
        <Route path="/cadastro" element={<Cadastro />} />
        <Route element={<Shell />}>
          <Route index element={<Hoje />} />
          <Route path="perfil" element={<Perfil />} />
          <Route path="comida" element={<Comida />} />
          <Route path="treino" element={<Treino />} />
          <Route path="treino/sessao/:id" element={<SessaoTreino />} />
          <Route path="progresso" element={<EmBreve titulo="Progresso" etapa="Peso, streak e histórico chegam na etapa 6." />} />
          <Route path="coach" element={<TelaCoach />} />
          <Route path="*" element={<EmBreve titulo="404" chamada="Nada aqui" etapa="Essa tela não existe." />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
