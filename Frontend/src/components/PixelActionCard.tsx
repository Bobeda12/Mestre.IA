import type { ButtonHTMLAttributes } from 'react';

// Fase 1 do remaster UX (PLANO_REMASTER_UX.md) — as sugestões táticas
// ([OPCOES]) deixam de ser botão de formulário e viram carta de ação
// dourada/madeira, no mesmo espírito dos botões metálicos do documento de
// design, adaptado pra pixel art. CSS puro (a estilização vive em
// `.pixel-action-card`, index.css) — framer-motion fica reservado pros
// pontos de alta coreografia da Fase 3.
export default function PixelActionCard({
  children,
  className = '',
  ...props
}: {
  children: React.ReactNode;
} & ButtonHTMLAttributes<HTMLButtonElement>) {
  return (
    <button
      type="button"
      {...props}
      className={`pixel-action-card text-left font-rpg text-rpg-parchment ${className}`}
    >
      {children}
    </button>
  );
}
