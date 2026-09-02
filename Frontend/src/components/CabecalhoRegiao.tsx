import PixelIcon from './PixelIcon';
import PixelBar from './PixelBar';
import FloatingCombatText, { type FlutuanteHeroi } from './FloatingCombatText';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

// Item 2 da rodada de polish pós-remaster — Local/Clima sai da sidebar
// (onde vivia espremido, `GameChat.tsx:1050-1063` antigo) e vira o topo da
// área central, "Cabeçalho de Região" — mesma heurística de chuva por
// regex e `periodoDoDia()` de sempre, só reposicionada e em escala maior.
//
// Item 1 (HUD híbrido, decisão aprovada) — a pílula de HP compacta mora
// aqui também: é o que garante que a vida continue visível mesmo com a
// ficha fechada no mobile (onde a sidebar é `fixed` e cobre a tela
// inteira) — sem ela, mover HP/XP/Ouro pra dentro da ficha (item 1)
// reintroduziria exatamente o problema que um comentário no código já
// documentou e corrigiu antes (ficha OU chat visíveis, nunca os dois).
export default function CabecalhoRegiao({
  localAtual,
  climaAtual,
  horaDoDia,
  periodoDoDia,
  hpAtual,
  hpMax,
  wasDamaged,
  flutuantesHeroiHp,
}: {
  localAtual: string;
  climaAtual: string;
  horaDoDia: number | null;
  periodoDoDia: (hora: number) => string;
  hpAtual: number;
  hpMax: number;
  wasDamaged: boolean;
  flutuantesHeroiHp: FlutuanteHeroi[];
}) {
  return (
    <div
      className={`shrink-0 flex items-center gap-3 md:gap-4 px-3 py-2 border-b-2 border-gray-800 bg-black/60 relative overflow-hidden ${/chuv/i.test(climaAtual) ? 'animate-chuva' : ''}`}
    >
      <TooltipProvider delayDuration={120}>
        <Tooltip>
          <TooltipTrigger asChild>
            <div tabIndex={0} className="relative flex items-center gap-2 shrink-0 cursor-help px-1 py-0.5 border-2 border-transparent hover:border-gray-700 focus-visible:outline-none focus-visible:border-rpg-gold transition-colors">
              <PixelIcon name="coracao" size={14} />
              <span className="text-[11px] font-rpg text-gray-200 shrink-0">{hpAtual}/{hpMax}</span>
              <div className="w-16 shrink-0"><PixelBar value={hpAtual} max={hpMax} colorClass="bg-red-600" flash={wasDamaged} /></div>
              <FloatingCombatText itens={flutuantesHeroiHp} />
            </div>
          </TooltipTrigger>
          <TooltipContent>
            Vida: {hpAtual} de {hpMax}
            {hpMax > 0 && ` (${Math.round((hpAtual / hpMax) * 100)}%)`}
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      {localAtual && (
        <div className="min-w-0 flex-1 flex items-baseline gap-2 border-l-2 border-gray-800 pl-3 md:pl-4">
          <PixelIcon name="seta" size={11} className="rotate-90 opacity-60 shrink-0" />
          <span className="font-rpg text-sm md:text-base text-rpg-gold truncate">{localAtual}</span>
          {climaAtual && <span className="text-[11px] text-gray-400 italic truncate hidden sm:inline">— {climaAtual}</span>}
          {horaDoDia != null && (
            <span className="ml-auto shrink-0 text-[9px] text-gray-500 uppercase tracking-widest">{periodoDoDia(horaDoDia)}</span>
          )}
        </div>
      )}
    </div>
  );
}
