import { motion, AnimatePresence } from 'framer-motion';
import PixelIcon from './PixelIcon';
import { categoriaDe } from './InventoryGrid';
import { useMovimentoReduzido } from '../lib/acessibilidade';

// Fase 3 do remaster UX (PLANO_REMASTER_UX.md) — "Animação de Loot": ao
// receber um item (`dar_item`, Backend/app/services/tools.py), a tela
// escurece, o ícone do item aparece brilhando no centro e depois voa até a
// aba ITENS da ficha. Único ponto desta fase que usa framer-motion — o
// resto do remaster é CSS puro; esta coreografia (posição final variável,
// dependente de onde a aba ITENS está na tela) é o caso onde CSS puro fica
// frágil de manter.
//
// O alvo do voo é medido na hora via `getBoundingClientRect` do botão da
// aba (id="aba-itens", sempre montado — a gaveta mobile só desloca a
// sidebar pra fora da tela, não desmonta). Se por algum motivo o elemento
// não existir, cai pro canto superior esquerdo (onde a mochila sempre vive
// no layout desktop) em vez de quebrar a animação.
export interface LootAtivo {
  id: number;
  item: string;
}

export default function LootRevealOverlay({ loot, onFinish }: { loot: LootAtivo | null; onFinish: () => void }) {
  const reduzido = useMovimentoReduzido();

  if (!loot) return null;
  const { icone } = categoriaDe(loot.item);

  const alvo = document.getElementById('aba-itens')?.getBoundingClientRect();
  const destinoX = alvo ? alvo.left + alvo.width / 2 - window.innerWidth / 2 : -window.innerWidth / 2 + 60;
  const destinoY = alvo ? alvo.top + alvo.height / 2 - window.innerHeight / 2 : -window.innerHeight / 2 + 60;

  const duracao = reduzido ? 0.4 : 1.6;

  return (
    <AnimatePresence>
      <motion.div
        className="fixed inset-0 z-[90] bg-black/80 flex items-center justify-center pointer-events-none"
        role="status"
        aria-live="polite"
        aria-label={`Você encontrou: ${loot.item}`}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.2 }}
      >
        <div className="flex flex-col items-center gap-3">
          <motion.div
            className="pixel-frame bg-black p-4"
            style={{ boxShadow: '0 0 24px 6px rgba(197,160,89,0.6)' }}
            initial={{ opacity: 0, scale: 0.4 }}
            animate={
              reduzido
                ? { opacity: [0, 1, 1, 0], scale: 1 }
                : { opacity: [0, 1, 1, 1, 0], scale: [0.4, 1.1, 1, 0.3, 0.2], x: [0, 0, 0, destinoX, destinoX], y: [0, 0, 0, destinoY, destinoY] }
            }
            transition={{ duration: duracao, times: reduzido ? [0, 0.15, 0.75, 1] : [0, 0.2, 0.55, 0.9, 1], ease: 'easeInOut' }}
            onAnimationComplete={onFinish}
          >
            <PixelIcon name={icone} size={48} />
          </motion.div>
          <motion.p
            className="font-pixel-title text-[10px] text-rpg-gold text-center px-4 leading-relaxed"
            initial={{ opacity: 0 }}
            animate={{ opacity: [0, 1, 1, 0] }}
            transition={{ duration: duracao, times: reduzido ? [0, 0.15, 0.75, 1] : [0, 0.15, 0.6, 0.85] }}
          >
            Você encontrou:<br />{loot.item}
          </motion.p>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}
