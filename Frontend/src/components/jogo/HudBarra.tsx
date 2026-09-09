import { periodoDoDia } from '../../lib/gameplay';
import type { Progressao } from '../../lib/gameplay';
import { type FlutuanteHeroi } from '../FloatingCombatText';
import FloatingCombatText from '../FloatingCombatText';
import PixelIcon from '../PixelIcon';
import PixelBar from '../PixelBar';

// Fase 6 ("uma tela só", ADR-0036) — uma linha só no topo, fundindo o que
// eram duas faixas (ícones de menu + CabecalhoRegiao) e o header que vivia
// dentro do palco (nível). Só aparece com a ficha fechada: com ela aberta,
// os mesmos botões já existem no cabeçalho da própria ficha (mobile: a
// gaveta cobre a tela inteira).
interface Props {
  showSidebar: boolean;
  setShowSidebar: (aberto: boolean) => void;
  setManualAberto: (aberto: boolean) => void;
  setGuiaAberto: (aberto: boolean) => void;
  setConfigAberta: (aberto: boolean) => void;
  hpAtual: number;
  hpMax: number;
  wasDamaged: boolean;
  flutuantesHeroiHp: FlutuanteHeroi[];
  foco: Progressao['recurso'] | undefined;
  nivel: number;
  localAtual: string;
  climaAtual: string;
  horaDoDia: number | null;
}

const BOTAO_ICONE = 'shrink-0 p-1 border-2 border-gray-700 hover:border-rpg-gold text-gray-300 hover:text-rpg-gold transition-colors focus-visible:outline-none focus-visible:border-rpg-gold';

export default function HudBarra(p: Props) {
  return (
    <div className={`shrink-0 flex items-center gap-2 md:gap-3 px-2 md:px-3 py-1.5 border-b-2 border-gray-800 bg-black/60 relative overflow-hidden ${/chuv/i.test(p.climaAtual) ? 'animate-chuva' : ''}`}>
      {!p.showSidebar && (
        <button onClick={() => p.setShowSidebar(true)} aria-label="Abrir ficha do personagem" className={BOTAO_ICONE}>
          <PixelIcon name="menu" size={16} />
        </button>
      )}

      <div className="flex items-center gap-1 shrink-0" title={`Vida: ${p.hpAtual} de ${p.hpMax}`}>
        <PixelIcon name="coracao" size={14} />
        <span className="text-[11px] font-rpg text-gray-200">{p.hpAtual}/{p.hpMax}</span>
        <div className="relative w-14 shrink-0"><PixelBar value={p.hpAtual} max={p.hpMax} colorClass="bg-red-600" flash={p.wasDamaged} /><FloatingCombatText itens={p.flutuantesHeroiHp} /></div>
      </div>

      {p.foco && (
        <div className="hidden sm:flex items-center gap-1 shrink-0" title={`${p.foco.nome}: ${p.foco.atual} de ${p.foco.maximo}`}>
          <PixelIcon name="pocao-azul" size={14} />
          <span className="text-[11px] font-rpg text-sky-200">{p.foco.atual}/{p.foco.maximo}</span>
        </div>
      )}

      <div className="flex items-center gap-1 shrink-0 font-pixel-title text-[9px] text-rpg-gold" title={`Nível ${p.nivel}`}>
        <PixelIcon name="estrela" size={12} /> NV {p.nivel}
      </div>

      {p.localAtual && (
        <div className="min-w-0 flex-1 flex items-baseline gap-2 border-l-2 border-gray-800 pl-2 md:pl-3">
          <PixelIcon name="seta" size={11} className="rotate-90 opacity-60 shrink-0" />
          <span className="font-rpg text-sm md:text-base text-rpg-gold truncate">{p.localAtual}</span>
          {p.climaAtual && <span className="text-[11px] text-gray-400 italic truncate hidden md:inline">— {p.climaAtual}</span>}
          {p.horaDoDia != null && <span className="ml-auto shrink-0 text-[9px] text-gray-500 uppercase tracking-widest">{periodoDoDia(p.horaDoDia)}</span>}
        </div>
      )}

      {!p.showSidebar && (
        <div className="flex items-center gap-1 shrink-0 ml-auto">
          <button onClick={() => p.setManualAberto(true)} aria-label="Abrir manual do jogo" title="Manual do Jogo" className={BOTAO_ICONE}><PixelIcon name="dado" size={16} /></button>
          <button onClick={() => p.setGuiaAberto(true)} aria-label="Abrir guia do aventureiro" title="Guia do Aventureiro" className={`${BOTAO_ICONE} w-[26px] h-[26px] flex items-center justify-center font-pixel-title text-[9px]`}>?</button>
          <button onClick={() => p.setConfigAberta(true)} aria-label="Abrir configurações" title="Configurações" className={BOTAO_ICONE}><PixelIcon name="config" size={16} /></button>
        </div>
      )}
    </div>
  );
}
