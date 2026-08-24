import type { HTMLAttributes } from 'react';

// Etapa 14 (C-1) — moldura 9-slice de verdade (`border-image`), sprite real
// do UI Pack - Pixel Adventure (Kenney, CC0, ver docs/CREDITOS.md). O
// `.pixel-frame` da Etapa 11 era um truque de `box-shadow` (cantos retos);
// este componente desenha cantos de verdade a partir da textura, pra caixas
// grandes onde isso se nota (card de personagem, sidebar, modais). O
// `.pixel-frame` continua existindo para os casos simples onde a borda reta
// já basta. `...rest` repassa `title`/`aria-label`/`tabIndex` etc. — usado
// pelos slots de inventário (C-6) pra dar tooltip e foco por teclado sem
// precisar de outro wrapper.
//
// `preencher` (o `fill` do `border-image-slice`) pinta o miolo da textura
// como fundo do elemento. Ficou ligado por padrão na primeira versão e isso
// foi um bug de legibilidade: o miolo do pergaminho é creme, então todo card
// que herdava a moldura virava creme por baixo de texto `text-gray-300/400`
// pensado pro tema escuro — ilegível (relatado na revisão da Etapa 14). Agora
// é opt-in: quem quiser o fundo de pergaminho pede, e assume o texto escuro
// junto. O padrão desenha só a borda e deixa o `bg-*` do próprio elemento
// aparecer.
export default function PanelFrame({
  children,
  className = '',
  borderWidth = 12,
  preencher = false,
  ...rest
}: {
  children: React.ReactNode;
  className?: string;
  borderWidth?: number;
  preencher?: boolean;
} & HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      {...rest}
      className={`box-border ${className}`}
      style={{
        borderStyle: 'solid',
        borderWidth,
        borderImageSource: "url('/assets/ui/painel-pergaminho.png')",
        borderImageSlice: preencher ? '8 fill' : '8',
        borderImageRepeat: 'round',
        imageRendering: 'pixelated',
      }}
    >
      {children}
    </div>
  );
}
