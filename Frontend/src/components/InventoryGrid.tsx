import PixelIcon, { type PixelIconName } from './PixelIcon';
import PanelFrame from './PanelFrame';

// Etapa 14 (C-6) — grade de slots (estilo RPG clássico) no lugar da lista
// de texto com ícone pequeno na frente (Etapa 7/`ItemIcon`). Não existe
// campo "tipo" no inventário do herói (Backend/app/infra/db.py:
// Personagem.inventario é só uma lista de strings) — a categorização por
// palavra-chave no nome é a mesma heurística de antes, só devolvendo um
// ícone pixel (PixelIcon) em vez de um ícone lucide.
const _PALAVRAS_POCAO = ['poção', 'pocao', 'elixir', 'frasco'];
const _PALAVRAS_ARMA = ['espada', 'cimitarra', 'machado', 'adaga', 'maça', 'martelo', 'arco', 'lança', 'rapier'];
const _PALAVRAS_ARMADURA = ['armadura', 'cota', 'escudo', 'couro', 'placas'];

function iconePara(nome: string): PixelIconName {
  const nomeLower = nome.toLowerCase();
  if (_PALAVRAS_POCAO.some((p) => nomeLower.includes(p))) return 'pocao-verde';
  if (_PALAVRAS_ARMA.some((p) => nomeLower.includes(p))) return 'espada';
  if (_PALAVRAS_ARMADURA.some((p) => nomeLower.includes(p))) return 'escudo';
  return 'pergaminho';
}

// Preenche até esse número de slots com espaços vazios, pra grade nunca
// ficar "quebrada" (uma linha incompleta) com poucos itens.
const SLOTS_MINIMOS = 8;

export default function InventoryGrid({ items }: { items: string[] }) {
  const vazios = Math.max(0, SLOTS_MINIMOS - items.length);
  return (
    <div className="grid grid-cols-4 gap-2">
      {items.map((item, i) => (
        <PanelFrame
          key={i}
          borderWidth={5}
          title={item}
          tabIndex={0}
          role="img"
          aria-label={item}
          className="aspect-square flex items-center justify-center bg-black animate-fade-in focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold"
        >
          <PixelIcon name={iconePara(item)} size={24} />
        </PanelFrame>
      ))}
      {Array.from({ length: vazios }).map((_, i) => (
        <div key={`vazio-${i}`} className="aspect-square border-2 border-gray-800/60 bg-black/30" />
      ))}
    </div>
  );
}
