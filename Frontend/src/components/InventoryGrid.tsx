import { useState } from 'react';
import PixelIcon, { type PixelIconName } from './PixelIcon';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

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

export function categoriaDe(nome: string): Categoria {
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
export default function InventoryGrid({ items, onUsarItem }: { items: string[]; onUsarItem?: (item: string) => void }) {
  const [selecionado, setSelecionado] = useState<number | null>(null);
  const vazios = Math.max(0, SLOTS_MINIMOS - items.length);
  const itemAberto = selecionado != null ? items[selecionado] : null;

  return (
    <TooltipProvider delayDuration={120}>
      <div className="grid grid-cols-4 gap-1.5">
        {items.map((item, i) => {
          const { icone } = categoriaDe(item);
          const ativo = selecionado === i;
          return (
            <Tooltip key={i}>
              <TooltipTrigger asChild>
                <button
                  type="button"
                  onClick={() => { setSelecionado(ativo ? null : i); onUsarItem?.(item); }}
                  aria-label={`Mencionar ${item} na ação`}
                  aria-pressed={ativo}
                  className={`aspect-square flex items-center justify-center border-2 transition-colors animate-fade-in focus-visible:outline-none focus-visible:border-rpg-gold ${
                    ativo
                      ? 'border-rpg-gold bg-rpg-gold/20'
                      : 'border-gray-600 bg-black/60 hover:border-gray-400'
                  }`}
                >
                  <PixelIcon name={icone} size={26} />
                </button>
              </TooltipTrigger>
              <TooltipContent>{item}</TooltipContent>
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
      <div className="mt-2 border-2 border-gray-700 bg-black/60 p-2 min-h-[3.5rem] flex items-center">
        {itemAberto ? (
          <div className="animate-fade-in">
            <p className="font-rpg text-rpg-gold leading-tight">{itemAberto}</p>
            <p className="text-[10px] text-gray-300 uppercase tracking-widest font-rpg">
              {categoriaDe(itemAberto).rotulo}
            </p>
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
