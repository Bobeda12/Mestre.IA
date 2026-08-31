import PixelIcon, { type PixelIconName } from './PixelIcon';

// Fase 1 do remaster UX (PLANO_REMASTER_UX.md) — "Feedback Visual de
// Sistema": mudanças de recurso (ouro, item recebido) saem da bolha de
// narração e viram uma notificação flutuante no topo da tela, no mesmo
// vocabulário visual de RollCard/StatusCard (borda de 2px, tom por
// resultado), só que fixa e com saída automática — não faz parte do log de
// mensagens.
export interface ToastItem {
  id: number;
  icone: PixelIconName;
  texto: string;
  tom: 'positivo' | 'negativo' | 'neutro';
}

const TOM_CLASSES: Record<ToastItem['tom'], string> = {
  positivo: 'border-emerald-700/50 text-emerald-300 bg-emerald-950/70',
  negativo: 'border-red-700/50 text-red-300 bg-red-950/70',
  neutro: 'border-gray-700 text-gray-300 bg-gray-900/80',
};

export default function SistemaFeedbackToast({ toasts }: { toasts: ToastItem[] }) {
  if (toasts.length === 0) return null;

  return (
    <div
      className="fixed top-3 left-1/2 -translate-x-1/2 z-[70] flex flex-col items-center gap-1.5 pointer-events-none"
      aria-live="polite"
      role="status"
    >
      {toasts.map((t) => (
        <div
          key={t.id}
          className={`flex items-center gap-2 px-3 py-1.5 border-2 font-rpg text-xs md:text-sm shadow-lg backdrop-blur-sm animate-toast-in ${TOM_CLASSES[t.tom]}`}
        >
          <PixelIcon name={t.icone} size={14} />
          <span className="font-bold tracking-wide">{t.texto}</span>
        </div>
      ))}
    </div>
  );
}
