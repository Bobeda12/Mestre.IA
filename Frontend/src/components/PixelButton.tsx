import type { ButtonHTMLAttributes } from 'react';
import { PIXEL_BUTTON_CLASS, pixelButtonBorderStyle, VARIANTS } from '../lib/pixelButtonEstilo';

// Etapa 14 (C-1) — botão com moldura 9-slice do UI Pack - Pixel Adventure
// (Kenney, CC0), no lugar dos botões `rounded-lg bg-gradient-to-r` da
// versão anterior. Não existe sprite de "pressionado" separado pra cada
// variante — o efeito de clique vem de transform + brilho, o mesmo recurso
// que o app já usava antes (ex: CharacterCreation, `hover:scale-110`).
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
    <button {...props} className={`${PIXEL_BUTTON_CLASS} ${className}`} style={pixelButtonBorderStyle(variant)}>
      {children}
    </button>
  );
}
