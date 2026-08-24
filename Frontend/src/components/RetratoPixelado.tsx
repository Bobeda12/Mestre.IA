import { useEffect, useRef } from 'react';

// O retrato do herói é gerado por IA (image.pollinations.ai) e volta como
// pintura digital realista — bonita, mas em outra linguagem visual do resto do
// jogo, que é pixel art de ponta a ponta. Pedir "pixel art" no prompt não
// resolve: foi testado nas duas formulações possíveis (vocabulário de console
// e especificação técnica de grade/paleta) e o gerador devolveu ilustração
// suavizada nas duas vezes (ver ADR-0025).
//
// O que funciona é converter depois, e é isso aqui: desenha a imagem numa
// grade pequena e reamplia com a interpolação desligada. Mesmo princípio do
// script que pixelizou os retratos de catálogo, só que no navegador.
//
// Não lê pixels de volta (nada de `getImageData`/`toDataURL`), só `drawImage`
// — por isso funciona mesmo com a imagem vindo de outro domínio sem CORS:
// canvas "contaminado" bloqueia leitura, não desenho.
const LARGURA_GRADE = 110;

export default function RetratoPixelado({
  src,
  className = '',
  alt = '',
}: {
  src: string;
  className?: string;
  alt?: string;
}) {
  const ref = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    if (!src) return;
    const img = new Image();
    let cancelado = false;

    img.onload = () => {
      const cv = ref.current;
      if (cancelado || !cv) return;
      const ctx = cv.getContext('2d');
      if (!ctx) return;

      // O canvas fica do tamanho da GRADE, não da imagem: quem amplia é o CSS
      // (`image-rendering: pixelated`), o que mantém a grade nítida em
      // qualquer tamanho de painel sem redesenhar.
      const altura = Math.max(1, Math.round((LARGURA_GRADE * img.height) / img.width));
      cv.width = LARGURA_GRADE;
      cv.height = altura;
      ctx.imageSmoothingEnabled = false;
      ctx.drawImage(img, 0, 0, LARGURA_GRADE, altura);
    };

    img.src = src;
    return () => {
      cancelado = true;
    };
  }, [src]);

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
