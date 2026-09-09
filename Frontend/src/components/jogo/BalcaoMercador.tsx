import { useEffect, useRef } from 'react';
import type { AcaoDireta, ItemInfo, PessoaMundo } from '../../lib/gameplay';
import PanelFrame from '../PanelFrame';
import PixelIcon from '../PixelIcon';

// Fase 6 (ADR-0036) — o balcão do mercador (Fase 1, ADR-0033) sai do painel
// Mundo Vivo e vira um modal: abre pelo verbo "Comerciar" do dock quando a
// pessoa selecionada tem vitrine. Preços já vêm calculados pelo servidor
// (confiança e talento); aqui só se mostra e se clica.
interface Props {
  pessoa: PessoaMundo;
  inventario: string[];
  catalogo: Record<string, ItemInfo>;
  ouro: number;
  ocupado: boolean;
  combate: boolean;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
  aoFechar: () => void;
}

const ITEM = 'flex items-center justify-between gap-2 border-2 border-gray-700 bg-black/50 px-2 py-2 min-h-11 text-left font-rpg text-sm text-gray-100 hover:border-rpg-gold disabled:opacity-45 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:border-rpg-gold';

export default function BalcaoMercador(p: Props) {
  const fecharRef = useRef<HTMLButtonElement>(null);
  useEffect(() => {
    fecharRef.current?.focus();
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') p.aoFechar(); };
    window.addEventListener('keydown', esc);
    return () => window.removeEventListener('keydown', esc);
  }, [p]);

  const vitrine = p.pessoa.vitrine ?? [];
  const bloqueado = p.ocupado || p.combate;

  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/80 p-4 animate-fade-in" role="dialog" aria-modal="true" aria-labelledby="balcao-titulo" onClick={p.aoFechar}>
      <PanelFrame className="w-full max-w-2xl bg-[#0b0e0a] p-4 max-h-full overflow-y-auto custom-scrollbar" onClick={e => e.stopPropagation()}>
        <div className="flex items-center justify-between gap-2 mb-2">
          {/* "BALCAO" fica sem acento de propósito (rótulo curto e fixo,
              Press Start 2P); o nome do NPC pode ter acento (ex.: um NPC
              chamado "Olívia"), então vai em Alegreya, que tem os glifos. */}
          <h2 id="balcao-titulo" className="text-rpg-gold text-xs flex items-center gap-2">
            <PixelIcon name="moeda" size={16} /> <span className="font-pixel-title">BALCAO DE</span> <span className="font-rpg uppercase tracking-wide">{p.pessoa.nome}</span>
          </h2>
          <button ref={fecharRef} type="button" onClick={p.aoFechar} aria-label="Fechar balcão" className="text-gray-400 hover:text-white p-1"><PixelIcon name="fechar" size={14} /></button>
        </div>
        <p className="font-rpg text-gray-300 text-sm mb-3">Preços do mercado, ajustados pela confiança. Você tem <span className="text-rpg-gold">{p.ouro}</span> de ouro.</p>

        <h3 className="font-rpg text-[10px] text-gray-400 uppercase tracking-widest mb-1.5">À venda</h3>
        {vitrine.length === 0 && <p className="text-xs text-gray-500 font-rpg mb-3">Nada à venda agora.</p>}
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5 mb-4">
          {vitrine.map(v => (
            <button type="button" key={`c:${v.item}`} className={ITEM} disabled={bloqueado || p.ouro < v.preco}
              title={p.catalogo[v.item]?.descricao}
              onClick={() => p.aoAgir({ acao: 'comerciar', alvo: p.pessoa.id, operacao: 'comprar', item: v.item }, `Comprar ${v.item} de ${p.pessoa.nome}`)}>
              <span className="min-w-0 truncate">{v.item}</span>
              <span className="shrink-0 text-rpg-gold text-xs flex items-center gap-1"><PixelIcon name="moeda" size={11} />{v.preco}</span>
            </button>
          ))}
        </div>

        {p.inventario.length > 0 && (
          <>
            <h3 className="font-rpg text-[10px] text-gray-400 uppercase tracking-widest mb-1.5">Vender do seu inventário (metade do valor)</h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-1.5">
              {p.inventario.map((item, i) => (
                <button type="button" key={`v:${item}:${i}`} className={ITEM} disabled={bloqueado}
                  onClick={() => p.aoAgir({ acao: 'comerciar', alvo: p.pessoa.id, operacao: 'vender', item }, `Vender ${item} a ${p.pessoa.nome}`)}>
                  <span className="min-w-0 truncate">{item}</span>
                  <span className="shrink-0 text-gray-300 text-xs flex items-center gap-1"><PixelIcon name="moeda" size={11} />{p.catalogo[item]?.preco_venda ?? 1}</span>
                </button>
              ))}
            </div>
          </>
        )}
      </PanelFrame>
    </div>
  );
}
