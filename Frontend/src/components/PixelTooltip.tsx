import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

// Item 10 da rodada de polish pós-remaster — `ui/tooltip.tsx` (Radix/shadcn)
// usa por padrão `bg-foreground`/`text-background`/`rounded-md`: tema
// shadcn genérico, com cantos arredondados que destoam do resto do app
// (tudo em `border-2` reto). Em vez de mudar o componente base (usado cru
// em RollCard/InventoryGrid/faixa de vitais sem problema visual relatado),
// este wrapper só passa um `className` pixel por padrão pra quem quiser o
// tema — pensado pra informação de MONSTRO (bestiário, card de combate),
// onde a caixa branca padrão do navegador (`title=` nativo) quebrava a
// imersão.
export default function PixelTooltip({
  children,
  content,
  side,
}: {
  children: React.ReactNode;
  content: React.ReactNode;
  side?: 'top' | 'right' | 'bottom' | 'left';
}) {
  return (
    <TooltipProvider delayDuration={150}>
      <Tooltip>
        <TooltipTrigger asChild>{children}</TooltipTrigger>
        <TooltipContent
          side={side}
          className="rounded-none border-2 border-rpg-gold bg-rpg-dark text-rpg-parchment font-rpg text-xs px-2 py-1.5 max-w-[220px]"
        >
          {content}
        </TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
