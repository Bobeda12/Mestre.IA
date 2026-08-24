import type { ButtonHTMLAttributes } from 'react';

// Etapa 14 (C-1) — botão com moldura 9-slice do UI Pack - Pixel Adventure
// (Kenney, CC0), no lugar dos botões `rounded-lg bg-gradient-to-r` da
// versão anterior. Não existe sprite de "pressionado" separado pra cada
// variante — o efeito de clique vem de transform + brilho, o mesmo recurso
// que o app já usava antes (ex: CharacterCreation, `hover:scale-110`).
const VARIANTS = {
  vermelho: '/assets/ui/botao-vermelho.png',
  azul: '/assets/ui/botao-azul.png',
  dourado: '/assets/ui/botao-dourado.png',
} as const;

export default function PixelButton({
  children,
  variant = 'dourado',
  className = '',
  ...props
}: {
  children: React.ReactNode;
  variant?: keyof typeof VARIANTS;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      {...props}
      className={`box-border font-pixel-title text-black transition-transform active:translate-y-[1px] active:brightness-90 disabled:opacity-50 disabled:active:translate-y-0 ${className}`}
      style={{
        borderStyle: 'solid',
        borderWidth: 8,
        borderImageSource: `url('${VARIANTS[variant]}')`,
        borderImageSlice: '5 fill',
        borderImageRepeat: 'round',
        imageRendering: 'pixelated',
      }}
    >
      {children}
    </button>
  );
}
