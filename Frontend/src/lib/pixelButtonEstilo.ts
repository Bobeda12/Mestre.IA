import type { CSSProperties } from 'react';

// Etapa 14 (C-1) — moldura 9-slice do UI Pack - Pixel Adventure (Kenney,
// CC0), usada pelo PixelButton. Vive num arquivo à parte (não em
// PixelButton.tsx) porque o Fast Refresh só funciona em arquivos que
// exportam exclusivamente componentes — exportar constantes/funções junto
// do componente quebra o hot reload.
export const VARIANTS = {
  vermelho: '/assets/ui/botao-vermelho.png',
  azul: '/assets/ui/botao-azul.png',
  dourado: '/assets/ui/botao-dourado.png',
} as const;

// Reaproveitado por elementos que não podem ser <button> (ex.: o link
// "Entrar com Google" em Login.tsx, que precisa de <a href> para o redirect
// OAuth), sem duplicar a moldura 9-slice.
export const PIXEL_BUTTON_CLASS =
  'box-border font-pixel-title text-black transition-transform active:translate-y-[1px] active:brightness-90 disabled:opacity-50 disabled:active:translate-y-0';

export function pixelButtonBorderStyle(variant: keyof typeof VARIANTS): CSSProperties {
  return {
    borderStyle: 'solid',
    borderWidth: 8,
    borderImageSource: `url('${VARIANTS[variant]}')`,
    borderImageSlice: '5 fill',
    borderImageRepeat: 'round',
    imageRendering: 'pixelated',
  };
}
