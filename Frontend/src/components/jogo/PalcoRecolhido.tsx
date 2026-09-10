import type { AliadoVisual, InimigoVisual, PessoaMundo } from '../../lib/gameplay';
import { getLocalImage } from '../../lib/utils';
import PixelIcon from '../PixelIcon';

// Pedido do usuário (rodada de melhorias pós-Fase-6) — o palco competia
// permanentemente com o chat pelo mesmo espaço, mesmo fora de combate
// (quando ele só mostra quem já está visível, sem nada pra selecionar).
// Esta é a versão recolhida: uma tira fina com quem está na cena, sem a
// moldura/fundo/prateleira do palco cheio — clique em qualquer lugar
// expande. Mesmo padrão de "recolher/expandir" que a ficha lateral já usa.
interface Props {
  classe: string;
  local: string;
  combate: boolean;
  aliados: AliadoVisual[];
  pessoas: PessoaMundo[];
  inimigos: InimigoVisual[];
  aoExpandir: () => void;
}

export default function PalcoRecolhido(p: Props) {
  return (
    <button
      type="button"
      onClick={p.aoExpandir}
      aria-label="Expandir o palco da cena"
      className="shrink-0 w-full flex items-center gap-2 px-3 py-1.5 mx-3 mt-2 border-2 border-gray-700 bg-black/40 hover:border-rpg-gold transition-colors text-left"
    >
      <PixelIcon name="seta" size={10} className="-rotate-90 opacity-60 shrink-0" />
      <span className="font-rpg text-sm text-rpg-gold truncate shrink-0 max-w-[40%]">{p.local || 'Cena'}</span>
      <div className="flex items-center -space-x-1 overflow-hidden">
        <img className="w-6 h-6 shrink-0 border border-gray-700 bg-black" src={getLocalImage('classes', p.classe || 'Guerreiro')} alt="" draggable={false} />
        {p.aliados.slice(0, 3).map(a => (
          <img key={a.nome} className="w-6 h-6 shrink-0 border border-gray-700 bg-black" src={getLocalImage('races', a.raca || 'Humano')} alt="" draggable={false} />
        ))}
        {p.pessoas.slice(0, 3).map(pe => (
          <img key={pe.id} className="w-6 h-6 shrink-0 border border-gray-700 bg-black" src={getLocalImage('races', pe.raca || 'Humano')} alt="" draggable={false} />
        ))}
      </div>
      {p.combate ? (
        <span className="ml-auto shrink-0 text-[10px] uppercase tracking-widest text-red-400 font-rpg">
          Combate · {p.inimigos.filter(i => i.hp > 0).length} inimigo{p.inimigos.filter(i => i.hp > 0).length === 1 ? '' : 's'}
        </span>
      ) : (
        <span className="ml-auto shrink-0 text-[10px] uppercase tracking-widest text-gray-500 font-rpg">Ver cena</span>
      )}
    </button>
  );
}
