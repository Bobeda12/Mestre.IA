import type { ButtonHTMLAttributes } from 'react';
import PixelIcon from './PixelIcon';

// Fase 1 do remaster UX (PLANO_REMASTER_UX.md) — as sugestões táticas
// ([OPCOES]) deixam de ser botão de formulário e viram carta de ação
// dourada/madeira, no mesmo espírito dos botões metálicos do documento de
// design, adaptado pra pixel art. CSS puro (a estilização vive em
// `.pixel-action-card`, index.css) — framer-motion fica reservado pros
// pontos de alta coreografia da Fase 3.
//
// Correção de UX pós Fase 1: adicionada uma seta antes do texto (mesmo
// espírito de item de menu de RPG clássico) que reage no hover — puramente
// visual, sem mudar a interação de clique.
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
      className={`pixel-action-card flex items-center gap-2 text-left font-rpg text-rpg-parchment ${className}`}
    >
      <PixelIcon name="seta" size={10} className="pixel-action-card__seta shrink-0" />
      <span className="pixel-action-card__texto min-w-0">{children}</span>
    </button>
  );
}
