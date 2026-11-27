import { useEffect, useRef } from "react";

// Cerejeira em pixel art (sprite de Infallible, recolorido para o verde do tema) com pétalas caindo ao vento.
// A grade de pixels acompanha a proporção da tela: cada pixel continua quadrado em qualquer largura.

const TONS = ["#9ff2b9", "#58c97e", "#2f8a52"];
const FORMAS: [number, number, number][][] = [
  [[0, 0, 0], [1, 0, 1]],
  [[1, 0, 0], [0, 1, 0], [1, 1, 1], [2, 1, 1]],
  [[0, 0, 0], [0, 1, 1], [1, 1, 1]],
  [[1, 0, 0], [0, 1, 0], [1, 1, 1], [1, 2, 1]],
];
const ALTURA = 175; // pixels "de jogo" na vertical

interface Petala {
  x: number;
  y: number;
  vy: number;
  fase: number;
  forma: number;
  tons: [string, string];
  pousada: number;
}

function carregar(src: string): Promise<HTMLImageElement> {
  return new Promise((ok, erro) => {
    const img = new Image();
    img.onload = () => ok(img);
    img.onerror = erro;
    img.src = src;
  });
}

export default function Cerejeira() {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = ref.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return; // sem canvas (testes, navegador antigo): a página segue sem a árvore
    let quadroId = 0;
    let vivo = true;
    const reduz = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

    Promise.all([carregar("/sprites/cerejeira.png"), carregar("/sprites/cerejeira-fundo.png")])
      .then(([arvore, fundoArvore]) => {
        if (!vivo) return;
        const proporcao = canvas.clientWidth / Math.max(canvas.clientHeight, 1);
        // Em tela estreita (celular) a grade cresce até a árvore caber inteira na largura.
        const H = Math.max(ALTURA, Math.ceil((arvore.width + 24) / proporcao));
        const W = Math.max(60, Math.round(H * proporcao));
        canvas.width = W;
        canvas.height = H;
        const retrato = W < H;
        const chao = H - 8;

        const fundo = document.createElement("canvas");
        fundo.width = W;
        fundo.height = H;
        const f = fundo.getContext("2d")!;
        f.fillStyle = "#0e1014";
        f.fillRect(0, chao, W, 8);
        for (let x = 0; x < W; x++) {
          if ((x * 7) % 5 < 2) {
            f.fillStyle = "#1d3b29";
            f.fillRect(x, chao - 1, 1, 1);
          }
        }
        // No celular a árvore fica centralizada no alto; no computador, à direita, com outra ao fundo.
        const ax = retrato ? Math.round((W - arvore.width) / 2) : W - arvore.width - 18;
        const ay = retrato ? Math.round(H * 0.08) : chao - arvore.height + 2;
        if (!retrato) f.drawImage(fundoArvore, Math.round(W * 0.42), chao - fundoArvore.height + 6);
        f.drawImage(arvore, ax, ay);
        const copa = { x0: ax + 10, x1: ax + arvore.width - 10, y0: ay + 10, y1: ay + arvore.height * 0.55 };
        const limiteChao = retrato ? ay + arvore.height : chao;

        const nova = (inicio: boolean): Petala => ({
          x: copa.x0 + Math.random() * (copa.x1 - copa.x0),
          y: inicio ? Math.random() * H : copa.y0 + Math.random() * (copa.y1 - copa.y0),
          vy: 0.07 + Math.random() * 0.09,
          fase: Math.random() * 6.3,
          forma: Math.floor(Math.random() * FORMAS.length),
          tons: Math.random() < 0.5 ? [TONS[0], TONS[1]] : [TONS[1], TONS[2]],
          pousada: 0,
        });
        const petalas = Array.from({ length: retrato ? 35 : 55 }, () => nova(true));
        let t = 0;

        const quadro = () => {
          ctx.clearRect(0, 0, W, H);
          ctx.drawImage(fundo, 0, 0);
          const vento = 0.12 + Math.sin(t * 0.004) * 0.1 + Math.max(0, Math.sin(t * 0.0013)) ** 8 * 0.6;
          for (const p of petalas) {
            if (!reduz && !p.pousada) {
              p.y += p.vy;
              p.x -= vento * (0.6 + p.vy * 3) + Math.sin(t * 0.03 + p.fase) * 0.12;
              if (t % 14 === 0) p.forma = (p.forma + 1) % FORMAS.length;
              if (p.y >= limiteChao - 1) {
                p.y = limiteChao - 1;
                p.pousada = 1;
                p.forma = 0;
              }
            } else if (p.pousada && !reduz && ++p.pousada > 900) {
              Object.assign(p, nova(false));
            }
            if (p.x < -4 || p.y > H) Object.assign(p, nova(false));
            for (const [dx, dy, tom] of FORMAS[p.forma]) {
              ctx.fillStyle = p.tons[tom];
              ctx.fillRect(Math.round(p.x) + dx, Math.round(p.y) + dy, 1, 1);
            }
          }
          t++;
          if (!reduz && vivo) quadroId = requestAnimationFrame(quadro);
        };
        quadro();
      })
      .catch(() => {
        /* sem os sprites, fica só o fundo escuro */
      });

    return () => {
      vivo = false;
      cancelAnimationFrame(quadroId);
    };
  }, []);

  return <canvas ref={ref} className="cerejeira" aria-hidden="true" />;
}
