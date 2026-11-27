import type { CSSProperties } from "react";
import { porcento } from "./formato";

/** Barra segmentada (blocos de 6 px com vão de 2 px). */
export function Barra({
  valor,
  meta,
  cor,
  rotulo,
  alta = false,
}: {
  valor: number;
  meta: number;
  cor: string;
  rotulo: string;
  alta?: boolean;
}) {
  const pct = porcento(valor, meta);
  return (
    <div
      className={alta ? "barra barra--alta" : "barra"}
      style={{ "--c": cor } as CSSProperties}
      role="progressbar"
      aria-label={rotulo}
      aria-valuemin={0}
      aria-valuemax={meta}
      aria-valuenow={Math.round(valor)}
    >
      <i style={{ width: `${pct}%` }} />
    </div>
  );
}

// Ícones 8×8 desenhados à mão, um caractere por pixel. Renderizados em SVG
// com `crispEdges` para continuarem nítidos em qualquer escala.
const ICONES = {
  hoje: [
    ".#....#.",
    "########",
    "#......#",
    "#.##.#.#",
    "#......#",
    "#.#.##.#",
    "#......#",
    "########",
  ],
  comida: [
    "....#...",
    "...#....",
    ".##.##..",
    "#######.",
    "#######.",
    "#######.",
    ".#####..",
    "..#.#...",
  ],
  treino: [
    "........",
    ".#....#.",
    "##....##",
    "########",
    "##....##",
    ".#....#.",
    "........",
    "........",
  ],
  progresso: [
    "......##",
    "......##",
    "...##.##",
    "...##.##",
    "##.##.##",
    "##.##.##",
    "........",
    "########",
  ],
  perfil: [
    "..####..",
    "..####..",
    "..####..",
    "........",
    ".######.",
    "########",
    "########",
    "########",
  ],
  sair: [
    "#####...",
    "#.......",
    "#....#..",
    "#.######",
    "#....#..",
    "#.......",
    "#####...",
    "........",
  ],
  camera: [
    "..###...",
    "########",
    "#..##..#",
    "#.#..#.#",
    "#.#..#.#",
    "#..##..#",
    "########",
    "........",
  ],
  enviar: [
    "........",
    "..#.....",
    "..##....",
    "..###...",
    "..####..",
    "..###...",
    "..##....",
    "..#.....",
  ],
} as const;

export type NomeIcone = keyof typeof ICONES;

export function Icone({ nome, tamanho = 16 }: { nome: NomeIcone; tamanho?: number }) {
  const rects: { x: number; y: number }[] = [];
  ICONES[nome].forEach((linha, y) => {
    for (let x = 0; x < linha.length; x++) if (linha[x] === "#") rects.push({ x, y });
  });
  return (
    <svg
      className="icone"
      width={tamanho}
      height={tamanho}
      viewBox="0 0 8 8"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {rects.map(({ x, y }) => (
        <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill="currentColor" />
      ))}
    </svg>
  );
}

/** O "H" pixelado do logo, nos mesmos pixels do ícone do app. */
export function Marca({ tamanho = 28 }: { tamanho?: number }) {
  const letra = ["##...##", "##...##", "##...##", "#######", "##...##", "##...##", "##...##"];
  const px: { x: number; y: number }[] = [];
  letra.forEach((linha, y) => {
    for (let x = 0; x < linha.length; x++) if (linha[x] === "#") px.push({ x, y });
  });
  return (
    <svg
      className="marca"
      width={tamanho}
      height={tamanho}
      viewBox="-1.5 -1.5 10 10"
      shapeRendering="crispEdges"
      aria-hidden="true"
    >
      {px.map(({ x, y }) => (
        <rect key={`s${x}-${y}`} x={x + 0.6} y={y + 0.6} width={1} height={1} fill="#2c6b42" />
      ))}
      {px.map(({ x, y }) => (
        <rect key={`${x}-${y}`} x={x} y={y} width={1} height={1} fill="var(--acento)" />
      ))}
    </svg>
  );
}
