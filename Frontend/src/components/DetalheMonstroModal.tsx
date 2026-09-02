import PixelIcon from './PixelIcon';
import PanelFrame from './PanelFrame';
import { getLocalImage } from '../lib/utils';

// Item 10 da rodada de polish pós-remaster — clicar num card do Bestiário
// abre isto: "Página de Livro Mágico", reaproveitando `PanelFrame` com
// `preencher` (fundo de pergaminho de verdade — mesma técnica já usada em
// FichaModal.tsx, texto escuro por cima).
//
// `lore` é opcional de propósito: `Backend/data/monsters.json` tem
// `ataque`/`comportamento` (dado mecânico), mas nenhum campo de
// lore/flavor text, e esse dado nem chega ao frontend fora de combate ativo
// hoje. Em vez de esperar um endpoint novo (fora do escopo desta rodada,
// decisão explícita), a UI já nasce pronta pra receber uma descrição real
// no futuro — até lá, mostra um texto de placeholder temático.
export default function DetalheMonstroModal({
  aberto,
  onFechar,
  nome,
  abates,
  lore,
}: {
  aberto: boolean;
  onFechar: () => void;
  nome: string;
  abates: number;
  lore?: string | null;
}) {
  if (!aberto) return null;

  return (
    <div
      className="fixed inset-0 z-[70] bg-black/85 flex items-center justify-center p-4 animate-fade-in"
      onClick={onFechar}
      role="dialog"
      aria-modal="true"
      aria-label={`Página do bestiário: ${nome}`}
    >
      <PanelFrame
        borderWidth={14}
        preencher
        className="max-w-sm w-full p-6 relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onFechar}
          aria-label="Fechar página do bestiário"
          className="absolute top-3 right-3 p-1 bg-black/40 border-2 border-gray-700 hover:border-rpg-gold text-gray-700 hover:text-rpg-gold focus-visible:outline-none focus-visible:border-rpg-gold"
        ><PixelIcon name="fechar" size={16} /></button>

        <div className="flex flex-col items-center text-center gap-2">
          <div className="pixel-frame w-24 h-24 bg-black/20 flex items-center justify-center overflow-hidden">
            <img
              src={getLocalImage('monstros', nome)}
              alt=""
              className="w-16 h-16"
              onError={(e) => { e.currentTarget.style.display = 'none'; }}
            />
          </div>
          <h2 className="font-rpg text-2xl text-rpg-dark leading-tight">{nome}</h2>
          <span className={`text-[10px] uppercase tracking-widest font-rpg ${abates > 0 ? 'text-red-700' : 'text-rpg-dark/50'}`}>
            {abates > 0 ? `Derrotado ×${abates}` : 'Avistado, nunca derrotado'}
          </span>

          <div className="border-t-2 border-rpg-dark/20 mt-3 pt-3 w-full">
            <h3 className="text-[10px] uppercase tracking-widest text-rpg-dark/60 font-rpg mb-1">Bestiário</h3>
            <p className="text-sm text-rpg-dark/80 italic leading-relaxed">
              {lore ?? 'As lendas sobre esta criatura ainda estão sendo escritas — os estudiosos do reino não chegaram tão longe.'}
            </p>
          </div>
        </div>
      </PanelFrame>
    </div>
  );
}
