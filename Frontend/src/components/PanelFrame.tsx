import type { HTMLAttributes } from 'react';

// Etapa 14 (C-1) — moldura 9-slice de verdade (`border-image`), sprite real
// do UI Pack - Pixel Adventure (Kenney, CC0, ver docs/CREDITOS.md). O
// `.pixel-frame` da Etapa 11 era um truque de `box-shadow` (cantos retos);
// este componente desenha cantos de verdade a partir da textura, pra caixas
// grandes onde isso se nota (card de personagem, sidebar, modais). O
// `.pixel-frame` continua existindo para os casos simples onde a borda reta
// já basta. `fill` em `borderImageSlice` pinta o miolo da textura como
// fundo — não precisa de `background-color` separado. `...rest` repassa
// `title`/`aria-label`/`tabIndex` etc. — usado pelos slots de inventário
// (C-6) pra dar tooltip e foco por teclado sem precisar de outro wrapper.
export default function PanelFrame({
  children,
  className = '',
  borderWidth = 12,
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  borderWidth?: number;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={`box-border ${className}`}
      style={{
        borderStyle: 'solid',
        borderWidth,
        borderImageSource: "url('/assets/ui/painel-pergaminho.png')",
        borderImageSlice: '8 fill',
        borderImageRepeat: 'round',
        imageRendering: 'pixelated',
      }}
    >
      {children}
    </div>
  );
}
