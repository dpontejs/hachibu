// Gera public/icons/icon-{180,192,512}.png: um "H" pixelado no verde do acento
// sobre o fundo do tema, com sombra dura de 1 pixel. Só usa a stdlib do Node.
// Uso: node scripts/gerar-icones.mjs
import { writeFileSync, mkdirSync } from "node:fs";
import { deflateSync } from "node:zlib";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const FUNDO = [0x12, 0x14, 0x1a];
const ACENTO = [0x7c, 0xf2, 0x9a];
const SOMBRA = [0x2c, 0x6b, 0x42];

const GRADE = 13; // células por lado; o "H" (7×7) fica no meio, longe da área de corte "maskable"
const LETRA = ["##...##", "##...##", "##...##", "#######", "##...##", "##...##", "##...##"];
const X0 = 3;
const Y0 = 3;

function celula(cx, cy) {
  const pinta = (x, y) => LETRA[y - Y0]?.[x - X0] === "#";
  if (pinta(cx, cy)) return ACENTO;
  if (pinta(cx - 1, cy - 1)) return SOMBRA;
  return FUNDO;
}

const TABELA_CRC = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});

function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = TABELA_CRC[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}

function bloco(tipo, dados) {
  const tam = Buffer.alloc(4);
  tam.writeUInt32BE(dados.length);
  const corpo = Buffer.concat([Buffer.from(tipo, "ascii"), dados]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(corpo));
  return Buffer.concat([tam, corpo, crc]);
}

function png(lado) {
  const linhas = [];
  for (let y = 0; y < lado; y++) {
    const linha = Buffer.alloc(1 + lado * 3); // filtro 0 + RGB
    const cy = Math.floor((y * GRADE) / lado);
    for (let x = 0; x < lado; x++) {
      const cx = Math.floor((x * GRADE) / lado);
      const [r, g, b] = celula(cx, cy);
      linha[1 + x * 3] = r;
      linha[2 + x * 3] = g;
      linha[3 + x * 3] = b;
    }
    linhas.push(linha);
  }
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(lado, 0);
  ihdr.writeUInt32BE(lado, 4);
  ihdr[8] = 8; // bits por canal
  ihdr[9] = 2; // RGB
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    bloco("IHDR", ihdr),
    bloco("IDAT", deflateSync(Buffer.concat(linhas), { level: 9 })),
    bloco("IEND", Buffer.alloc(0)),
  ]);
}

const destino = join(dirname(fileURLToPath(import.meta.url)), "..", "public", "icons");
mkdirSync(destino, { recursive: true });
for (const lado of [180, 192, 512]) {
  writeFileSync(join(destino, `icon-${lado}.png`), png(lado));
  console.log(`icon-${lado}.png`);
}
