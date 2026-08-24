import { useEffect, useRef } from 'react';

// O retrato do herói é gerado por IA (image.pollinations.ai) e volta como
// pintura digital realista — bonita, mas em outra linguagem visual do resto do
// jogo, que é pixel art de ponta a ponta. Pedir "pixel art" no prompt não
// resolve: testado nas duas formulações possíveis (vocabulário de console e
// especificação técnica de grade/paleta), o gerador devolve ilustração
// suavizada nas duas vezes (ver ADR-0025).
//
// A conversão passou por duas versões erradas antes desta:
//
//   1. Só REDUZIR a resolução. Continuava lendo como foto: o que faz parecer
//      pixel art não é ter poucos pixels, é ter POUCAS CORES em áreas
//      chapadas. Foto reduzida mantém milhares de tons e degradês suaves.
//   2. Reduzir + posterizar cada canal em N níveis fixos. Isso achata, mas
//      quantizar R, G e B de forma independente num degradê INVENTA cor: o
//      fundo bege virava faixas verdes e rosas, e com saturação por cima
//      ficava neon.
//
// O que funciona é MEDIAN CUT: em vez de uma grade fixa de cores, ele escolhe
// a paleta a partir das cores que a imagem realmente tem, cortando o espaço de
// cor onde ele é mais largo. O resultado achata em faixas sem sair da
// identidade cromática do original — comparado lado a lado com o posterize,
// a diferença é gritante.
//
// Ler os pixels (`getImageData`) exige canvas não contaminado, o que funciona
// porque o provedor responde `Access-Control-Allow-Origin: *` e a imagem é
// pedida com `crossOrigin`. Se isso mudar, o `catch` degrada para a versão
// só-reduzida em vez de quebrar a tela.
// A grade é PROP, não constante: o mesmo valor dá resultados muito
// diferentes conforme o tamanho em que a imagem é exibida. Numa miniatura de
// 64px, 56 de grade é quase 1:1 e fica detalhado; num painel de 288px vira
// 5x de ampliação e o rosto colapsa em manchas. Regra prática: uma grade em
// torno de 1/3 da largura exibida lê como pixel art sem destruir a figura.
const GRADE_PADRAO = 56;
const CORES = 22;
const SATURACAO = 1.18;

/** Agrupa as cores da imagem em `nCores` grupos e pinta cada pixel com a média
 *  do seu grupo. Corta sempre o grupo de maior amplitude, no canal mais largo
 *  dele — que é o que dá nome ao método. */
function medianCut(px: Uint8ClampedArray, nCores: number): void {
  const total = px.length / 4;
  let grupos: number[][] = [Array.from({ length: total }, (_, i) => i * 4)];

  while (grupos.length < nCores) {
    let alvo = -1;
    let maiorAmplitude = -1;
    let canalDoCorte = 0;

    grupos.forEach((g, idx) => {
      if (g.length < 2) return;
      for (let c = 0; c < 3; c++) {
        let min = 255;
        let max = 0;
        for (const p of g) {
          const v = px[p + c];
          if (v < min) min = v;
          if (v > max) max = v;
        }
        if (max - min > maiorAmplitude) {
          maiorAmplitude = max - min;
          alvo = idx;
          canalDoCorte = c;
        }
      }
    });

    if (alvo < 0 || maiorAmplitude <= 0) break; // já é tudo cor chapada
    const g = grupos[alvo];
    g.sort((a, b) => px[a + canalDoCorte] - px[b + canalDoCorte]);
    const meio = g.length >> 1;
    grupos.splice(alvo, 1, g.slice(0, meio), g.slice(meio));
  }

  for (const g of grupos) {
    if (!g.length) continue;
    let r = 0;
    let vd = 0;
    let b = 0;
    for (const p of g) {
      r += px[p];
      vd += px[p + 1];
      b += px[p + 2];
    }
    r = Math.round(r / g.length);
    vd = Math.round(vd / g.length);
    b = Math.round(b / g.length);
    for (const p of g) {
      px[p] = r;
      px[p + 1] = vd;
      px[p + 2] = b;
    }
  }
}

export default function RetratoPixelado({
  src,
  className = '',
  alt = '',
  grade = GRADE_PADRAO,
}: {
  src: string;
  className?: string;
  alt?: string;
  grade?: number;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!src) return;
    let cancelado = false;

    // Desenha e, quando possível, quantiza. `podeLerPixels` diz se a imagem
    // veio por um pedido com CORS — sem isso o canvas fica "contaminado" e
    // `getImageData` lança.
    const desenhar = (img: HTMLImageElement, podeLerPixels: boolean) => {
      const cv = ref.current;
      if (cancelado || !cv) return;
      const ctx = cv.getContext('2d', { willReadFrequently: true });
      if (!ctx) return;

      // O canvas fica do tamanho da GRADE, não da imagem: quem amplia é o CSS
      // (`image-rendering: pixelated`), o que mantém a grade nítida em
      // qualquer tamanho de painel sem redesenhar.
      const altura = Math.max(1, Math.round((grade * img.height) / img.width));
      cv.width = grade;
      cv.height = altura;
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(img, 0, 0, grade, altura);
      if (!podeLerPixels) return;

      try {
        const dados = ctx.getImageData(0, 0, grade, altura);
        const px = dados.data;

        // Satura ANTES de quantizar: paleta fechada lava a cor, e sprite de
        // console é saturado de propósito. Afastar cada canal da luminância
        // satura sem mexer no brilho aparente.
        for (let i = 0; i < px.length; i += 4) {
          const lum = 0.2126 * px[i] + 0.7152 * px[i + 1] + 0.0722 * px[i + 2];
          for (let c = 0; c < 3; c++) {
            px[i + c] = lum + (px[i + c] - lum) * SATURACAO;
          }
        }

        medianCut(px, CORES);
        ctx.putImageData(dados, 0, 0);
      } catch {
        // Fica a versão só-reduzida, que já ajuda.
      }
    };

    // Primeira tentativa COM CORS, que é o que permite quantizar.
    const comCors = new Image();
    comCors.crossOrigin = 'anonymous'; // precisa vir antes do `src`
    comCors.onload = () => desenhar(comCors, true);

    // Se falhar, tenta de novo SEM CORS. Isso acontece de verdade: quando a
    // mesma URL já está no cache vinda de um pedido sem CORS, o pedido com
    // CORS reaproveita a resposta cacheada e a checagem falha. Sem este
    // segundo caminho o retrato simplesmente não aparecia — e como não havia
    // `onerror`, falhava calado, deixando o canvas no tamanho padrão (300x150).
    comCors.onerror = () => {
      if (cancelado) return;
      const semCors = new Image();
      semCors.onload = () => desenhar(semCors, false);
      semCors.src = src;
    };

    comCors.src = src;
    return () => {
      cancelado = true;
    };
  }, [src, grade]);

  return (
    <canvas
      ref={ref}
      role="img"
      aria-label={alt}
      className={className}
      style={{ imageRendering: 'pixelated' }}
    />
  );
}
