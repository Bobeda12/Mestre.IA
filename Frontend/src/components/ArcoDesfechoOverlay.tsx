import type { ArcoEncerrado } from '../lib/gameplay';
import PanelFrame from './PanelFrame';
import PixelIcon from './PixelIcon';

// Fase 4 do plano "jogo completo" (ADR-0035) — o capítulo fechou: o
// servidor confirmou, a recompensa é dele, e o texto é a IA costurando os
// marcos registrados. Estilo do epitáfio/LootRevealOverlay.
export default function ArcoDesfechoOverlay({ arco, aoFechar }: { arco: ArcoEncerrado; aoFechar: () => void }) {
  const rotulo: Record<string, string> = { acordo: 'Acordo', consequencia: 'Consequências', vitoria_chefe: 'Vitória', abandono: 'Abandono' };
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/85 p-4 animate-fade-in" role="dialog" aria-modal="true" aria-labelledby="arco-titulo">
      <PanelFrame className="w-full max-w-2xl bg-[#0b0e0a] p-5 max-h-full overflow-y-auto">
        <p className="font-rpg text-xs text-gray-400 tracking-widest uppercase">CAPÍTULO ENCERRADO · {rotulo[arco.resultado] ?? arco.resultado}</p>
        <h2 id="arco-titulo" className="font-rpg text-2xl text-rpg-gold mt-1 mb-3 flex items-center gap-2"><PixelIcon name="pergaminho" size={18} />{arco.titulo}</h2>
        <div className="font-rpg text-gray-200 leading-relaxed whitespace-pre-wrap">{arco.texto}</div>
        {(arco.recompensa.xp > 0 || arco.recompensa.ouro > 0 || arco.recompensa.itens.length > 0) && (
          <p className="mt-3 text-[11px] font-rpg text-emerald-200 uppercase tracking-widest">
            Recompensa: {arco.recompensa.xp} XP · {arco.recompensa.ouro} ouro{arco.recompensa.itens.length ? ` · ${arco.recompensa.itens.join(', ')}` : ''}
          </p>
        )}
        <button type="button" onClick={aoFechar} className="mt-4 font-pixel-title text-[9px] text-rpg-gold border-2 border-rpg-leather hover:border-rpg-gold px-3 py-2">SEGUIR EM FRENTE</button>
      </PanelFrame>
    </div>
  );
}
