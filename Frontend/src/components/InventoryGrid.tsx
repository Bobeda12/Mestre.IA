import { useState } from 'react';
import PixelIcon, { type PixelIconName } from './PixelIcon';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import type { Equipamento, ItemInfo } from '../lib/gameplay';

// Etapa 14 (C-6) — grade de slots (estilo RPG clássico) no lugar da lista de
// texto com ícone pequeno na frente (Etapa 7/`ItemIcon`).
//
// Revisão da Etapa 14: a primeira grade mostrava só o ícone, e o nome do item
// vinha no atributo `title` — o balãozinho nativo do navegador, que demora
// ~1s pra aparecer e sai com a cara do sistema operacional, não do jogo.
// Agora usa o mesmo `ui/tooltip` que o RollCard já usava (Etapa 11), e
// clicar num slot abre um painel de descrição embaixo da grade, como menu de
// item de console. Reuso, não componente novo.
//
// Não existe campo "tipo" no inventário do herói (Backend/app/infra/db.py:
// Personagem.inventario é uma lista de strings), então a categoria sai por
// palavra-chave no nome — mesma heurística de antes.
const _PALAVRAS_POCAO = ['poção', 'pocao', 'elixir', 'frasco'];
const _PALAVRAS_ARMA = ['espada', 'cimitarra', 'machado', 'adaga', 'maça', 'martelo', 'arco', 'lança', 'rapier'];
const _PALAVRAS_ARMADURA = ['armadura', 'cota', 'escudo', 'couro', 'placas'];

// Exportados (Fase 3 do remaster UX, PLANO_REMASTER_UX.md) — LootRevealOverlay
// usa a mesma heurística nome→ícone pra mostrar o item certo na animação de
// loot, em vez de duplicar a lista de palavras-chave.
export interface Categoria {
  icone: PixelIconName;
  rotulo: string;
}

// Fase 1 do plano "jogo completo" (ADR-0033): quando o servidor manda a
// ficha (`catalogo_itens` no frame de estado), o tipo vem dela; a heurística
// por palavra fica só como fallback pra item que o servidor não conhece.
const _ICONE_POR_TIPO: Record<ItemInfo['tipo'], Categoria> = {
  consumivel: { icone: 'pocao-verde', rotulo: 'Consumível' },
  arma: { icone: 'espada', rotulo: 'Arma' },
  armadura: { icone: 'escudo', rotulo: 'Armadura' },
  escudo: { icone: 'escudo', rotulo: 'Escudo' },
  ferramenta: { icone: 'pergaminho', rotulo: 'Ferramenta' },
  inventado: { icone: 'pergaminho', rotulo: 'Item' },
};

export function categoriaDe(nome: string, info?: ItemInfo): Categoria {
  if (info && _ICONE_POR_TIPO[info.tipo]) return _ICONE_POR_TIPO[info.tipo];
  const n = nome.toLowerCase();
  if (_PALAVRAS_POCAO.some((p) => n.includes(p))) return { icone: 'pocao-verde', rotulo: 'Consumível' };
  if (_PALAVRAS_ARMA.some((p) => n.includes(p))) return { icone: 'espada', rotulo: 'Arma' };
  if (_PALAVRAS_ARMADURA.some((p) => n.includes(p))) return { icone: 'escudo', rotulo: 'Proteção' };
  return { icone: 'pergaminho', rotulo: 'Item' };
}

// Preenche até esse número de slots com espaços vazios, pra grade nunca ficar
// com uma linha incompleta e leia como "mochila com espaço", não como bug.
const SLOTS_MINIMOS = 12;

// Fase 8 da revisão de gameplay (Etapa 12/13) — clicar num item não usa ele
// direto: injeta `[Nome do Item]` na caixa de texto livre (mesmo padrão do
// clique no nome do inimigo em combate, GameChat.tsx). O jogador completa a
// frase como quiser ("Eu jogo a [Poção de Água] na cara do guarda") — o
// inventário vira apoio criativo, não um botão de "usar". Isto substitui a
// ideia antiga do backlog ("abrir inventário e usar de verdade"); as duas
// conflitavam, e esta foi a escolhida (ver docs/backlog-pos-lancamento.md, D-3).
//
// Correção de UX pós Fase 1 do remaster: o clique no slot fazia as duas
// coisas de uma vez (abrir detalhes E injetar no chat), o que gerava clique
// acidental no chat. Agora são dois passos: o slot só abre/fecha o painel de
// descrição; o botão "Citar no chat" dentro do painel é que injeta.
export default function InventoryGrid({ items, onUsarItem, infos, equipamento, onEquipar, onDesequipar, onConsumir, ocupado }: {
  items: string[];
  onUsarItem?: (item: string) => void;
  infos?: Record<string, ItemInfo>;
  equipamento?: Equipamento;
  onEquipar?: (item: string) => void;
  onDesequipar?: (slot: 'arma' | 'armadura' | 'escudo') => void;
  onConsumir?: (item: string) => void;
  ocupado?: boolean;
}) {
  const [selecionado, setSelecionado] = useState<number | null>(null);
  const vazios = Math.max(0, SLOTS_MINIMOS - items.length);
  const itemAberto = selecionado != null ? items[selecionado] : null;
  const infoAberto = itemAberto ? infos?.[itemAberto] : undefined;
  const slotEquipado = (item: string): 'arma' | 'armadura' | 'escudo' | null =>
    equipamento?.arma === item ? 'arma' : equipamento?.armadura === item ? 'armadura' : equipamento?.escudo === item ? 'escudo' : null;
  const equipavel = infoAberto && ['arma', 'armadura', 'escudo'].includes(infoAberto.tipo);

  return (
    <TooltipProvider delayDuration={120}>
      {equipamento && (
        <p className="text-[10px] text-gray-400 font-rpg uppercase tracking-widest mb-1">
          Equipado: {equipamento.arma ?? '—'} · {equipamento.armadura ?? '—'} · {equipamento.escudo ?? '—'}
        </p>
      )}
      <div className="grid grid-cols-4 gap-1.5">
        {items.map((item, i) => {
          const { icone } = categoriaDe(item, infos?.[item]);
          const ativo = selecionado === i;
          const eq = slotEquipado(item);
          return (
            <Tooltip key={i}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => setSelecionado(ativo ? null : i)}
                  aria-label={`Ver detalhes de ${item}${eq ? ' (equipado)' : ''}`}
                  aria-expanded={ativo}
                  aria-controls="painel-detalhe-item"
                  className={`relative aspect-square flex items-center justify-center border-2 transition-colors animate-fade-in focus-visible:outline-none focus-visible:border-rpg-gold ${
                    ativo
                      ? 'border-rpg-gold bg-rpg-gold/20'
                      : eq ? 'border-emerald-700 bg-black/60 hover:border-emerald-400' : 'border-gray-600 bg-black/60 hover:border-gray-400'
                  }`}
                >
                  <PixelIcon name={icone} size={26} />
                  {eq && <span aria-hidden className="absolute bottom-0 right-0 text-[8px] text-emerald-300 font-rpg px-0.5">E</span>}
                </button>
              </TooltipTrigger>
              <TooltipContent>{item}{eq ? ' · equipado' : ''}</TooltipContent>
            </Tooltip>
          );
        })}

        {Array.from({ length: vazios }).map((_, i) => (
          <div key={`vazio-${i}`} className="aspect-square border-2 border-gray-800 bg-black/30" />
        ))}
      </div>

      {/* Painel de descrição: o que "abrir o item" mostra. Fica sempre no
          mesmo lugar (embaixo da grade) em vez de virar um popover flutuante,
          que é como menu de RPG de console faz — assim a grade não pula de
          posição quando o jogador seleciona algo. */}
      <div id="painel-detalhe-item" className="mt-2 border-2 border-gray-700 bg-black/60 p-2 min-h-[3.5rem]">
        {itemAberto ? (
          <div className="animate-fade-in space-y-1.5 w-full">
            <div className="flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="font-rpg text-rpg-gold leading-tight truncate">{itemAberto}</p>
                <p className="text-[10px] text-gray-300 uppercase tracking-widest font-rpg">
                  {categoriaDe(itemAberto, infoAberto).rotulo}
                  {infoAberto?.tags?.length ? ` · ${infoAberto.tags.join(', ')}` : ''}
                  {infoAberto ? ` · vende por ${infoAberto.preco_venda}` : ''}
                </p>
              </div>
              <button
                type="button"
                onClick={() => onUsarItem?.(itemAberto)}
                aria-label={`Mencionar ${itemAberto} na ação`}
                className="shrink-0 flex items-center gap-1 text-[10px] uppercase tracking-widest font-rpg text-rpg-gold border-2 border-rpg-leather hover:border-rpg-gold px-2 py-1 transition-colors focus-visible:outline-none focus-visible:border-rpg-gold"
              >
                💬 Citar no chat
              </button>
            </div>
            {infoAberto?.descricao && <p className="text-[11px] text-gray-300 font-rpg leading-snug">{infoAberto.descricao}</p>}
            {/* Fase 1 — o juiz resolve na hora (POST /game/action), sem passar pelo narrador. */}
            <div className="flex gap-1.5 flex-wrap">
              {equipavel && !slotEquipado(itemAberto) && (
                <button type="button" disabled={ocupado} onClick={() => onEquipar?.(itemAberto)}
                  className="text-[10px] uppercase tracking-widest font-rpg text-emerald-200 border-2 border-emerald-800 hover:border-emerald-400 px-2 py-1 disabled:opacity-50">
                  Equipar
                </button>
              )}
              {equipavel && slotEquipado(itemAberto) && (
                <button type="button" disabled={ocupado} onClick={() => onDesequipar?.(slotEquipado(itemAberto)!)}
                  className="text-[10px] uppercase tracking-widest font-rpg text-gray-200 border-2 border-gray-600 hover:border-gray-300 px-2 py-1 disabled:opacity-50">
                  Guardar
                </button>
              )}
              {infoAberto?.tipo === 'consumivel' && (
                <button type="button" disabled={ocupado} onClick={() => onConsumir?.(itemAberto)}
                  className="text-[10px] uppercase tracking-widest font-rpg text-emerald-200 border-2 border-emerald-800 hover:border-emerald-400 px-2 py-1 disabled:opacity-50">
                  Usar
                </button>
              )}
            </div>
          </div>
        ) : (
          <p className="text-[11px] text-gray-400 font-rpg">
            {items.length > 0 ? 'Escolha um item para ver o que é.' : 'A mochila está vazia.'}
          </p>
        )}
      </div>
    </TooltipProvider>
  );
}
