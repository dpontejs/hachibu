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

const BAYER = [
  [0, 8, 2, 10],
  [12, 4, 14, 6],
  [3, 11, 1, 9],
  [15, 7, 13, 5],
];

function ruido(n: number): number {
  const x = Math.sin(n * 127.1) * 43758.5453;
  return x - Math.floor(x); // 0..1 determinístico
}

/**
 * Monte Fuji noturno. A textura vem do ângulo a partir do pico (cristas e ravinas irradiam em diagonal),
 * a neve desce mais ao longo das cristas e o lado esquerdo recebe a luz.
 */
function desenharFuji(f: CanvasRenderingContext2D, cx: number, chao: number, altura: number, meiaBase: number) {
  const topo = chao - altura;
  const plato = 6;
  const ROCHA = ["#191d28", "#1f2431", "#272d3c", "#323a4c"]; // sombra → crista iluminada
  const NEVE = ["#4a5367", "#636c82", "#7f899f", "#9ca6ba"];
  for (let x = Math.floor(cx - meiaBase * 1.1); x <= Math.ceil(cx + meiaBase); x++) {
    const dx = x - cx;
    // Leve assimetria: a saia esquerda é um pouco mais longa.
    const largura = dx < 0 ? meiaBase * 1.1 : meiaBase;
    const t = Math.max(0, (Math.abs(dx) - plato) / (largura - plato));
    if (t > 1) continue;
    const y0 = Math.round(topo + altura * t ** 0.85 + (ruido(Math.floor(x / 2)) - 0.5) * 1.2);
    for (let y = y0; y < chao; y++) {
      const dy = y - topo + 2;
      const angulo = Math.atan2(dx, dy); // 0 = direto para baixo a partir do pico
      // Cristas: listras no ângulo, com ondulação para não ficarem retas demais.
      const crista = Math.sin(angulo * 16 + Math.sin(dy * 0.15) * 0.6 + ruido(Math.round(angulo * 20)) * 2);
      // Luz gradual de um lado para o outro (sem emenda no meio).
      const lado = -dx / (Math.abs(dx) + 10);
      const luz = 0.1 + lado * 0.45 + crista * 0.45 + (BAYER[y & 3][x & 3] / 16 - 0.5) * 0.35;
      // Neve: ~28% da altura, descendo mais nas cristas (dedos) e menos nas bordas.
      const dedo = crista > 0.2 ? Math.min((crista - 0.2) * 0.32, 0.2) : 0;
      const profundidadeNeve = altura * (0.28 + dedo) * (1 - Math.abs(dx) / largura * 0.35);
      const naNeve = y - topo < profundidadeNeve + (BAYER[y & 3][x & 3] / 16) * 2;
      const tons = naNeve ? NEVE : ROCHA;
      const nivel = luz > 0.65 ? 3 : luz > 0.15 ? 2 : luz > -0.35 ? 1 : 0;
      f.fillStyle = tons[nivel];
      f.fillRect(x, y, 1, 1);
    }
  }
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

    carregar("/sprites/cerejeira.png")
      .then((arvore) => {
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
        // Monte Fuji na camada mais distante: encostas côncavas, topo achatado e neve com "dentes".
        // No celular não há espaço livre para ele: a árvore ocupa o alto e o texto, a base.
        // Perto do nome: o pico fica logo à direita do logo, e a saia passa por trás do texto.
        if (!retrato) desenharFuji(f, Math.max(W * 0.38, 150), chao, 100, 150);
        // Colinas ao fundo, em duas camadas.
        const camadas: [string, number, number, number, number][] = [
          ["#15181e", chao - 46, 14, 0.018, 1],
          ["#171b21", chao - 26, 10, 0.03, 4],
        ];
        for (const [cor, base, amp, freq, fase] of camadas) {
          f.fillStyle = cor;
          for (let x = 0; x < W; x++) {
            const y = Math.round(base - Math.sin(x * freq + fase) * amp - Math.sin(x * freq * 2.7) * amp * 0.3);
            f.fillRect(x, y, 1, chao - y);
          }
        }
        // Chão com grama, tufos e florzinhas.
        f.fillStyle = "#0e1014";
        f.fillRect(0, chao, W, 8);
        for (let x = 0; x < W; x++) {
          if ((x * 7) % 5 < 2) {
            f.fillStyle = "#1d3b29";
            f.fillRect(x, chao - 1, 1, 1);
          }
          if ((x * 13) % 17 === 0) {
            f.fillStyle = "#2f5e3f";
            f.fillRect(x, chao - 3, 1, 2);
            f.fillRect(x + 1, chao - 2, 1, 1);
            f.fillRect(x - 1, chao - 2, 1, 1);
          }
          if ((x * 29) % 53 === 0) {
            f.fillStyle = "#9ff2b9";
            f.fillRect(x, chao - 3, 1, 1);
          }
        }
        // No celular a árvore fica centralizada no alto; no computador, à direita, com outra ao fundo.
        const ax = retrato ? Math.round((W - arvore.width) / 2) : W - arvore.width - 18;
        const ay = retrato ? Math.round(H * 0.08) : chao - arvore.height + 2;
        f.drawImage(arvore, ax, ay);
        // Montinho de pétalas ao pé da árvore.
        const base = retrato ? ay + arvore.height : chao;
        for (let i = 0; i < 70; i++) {
          const x = ax + 40 + Math.random() * 90;
          if (Math.random() > Math.abs(x - (ax + 85)) / 45) {
            f.fillStyle = TONS[i % 2];
            f.fillRect(Math.round(x), base - 1 - (Math.random() < 0.3 ? 1 : 0), 1, 1);
          }
        }
        const vagalumes = Array.from({ length: retrato ? 5 : 9 }, () => ({
          x: Math.random() * W * (retrato ? 1 : 0.6),
          y: 15 + Math.random() * H * 0.5,
          fase: Math.random() * 6.3,
        }));
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
          for (const v of vagalumes) {
            const brilho = (Math.sin(t * 0.02 + v.fase) + 1) / 2;
            if (brilho > 0.55) {
              ctx.globalAlpha = (brilho - 0.55) * 2.2;
              ctx.fillStyle = "#d6ffe2";
              ctx.fillRect(
                Math.round(v.x + Math.sin(t * 0.005 + v.fase) * 6),
                Math.round(v.y + Math.cos(t * 0.004 + v.fase) * 3),
                1,
                1,
              );
              ctx.globalAlpha = 1;
            }
          }
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
