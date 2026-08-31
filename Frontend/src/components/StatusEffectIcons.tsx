import PixelIcon, { type PixelIconName } from './PixelIcon';

// Pendência do remaster UX resolvida (PLANO_REMASTER_UX.md, item 1) — as
// três flags táticas de CombatState (Backend/app/domain/state.py) já
// existiam desde a Fase 1 da revisão de gameplay e nunca tinham chegado ao
// frame `state`; agora chegam (routers/game.py:_resposta) e viram ícone
// piscando ao lado do retrato, como o documento de design original pedia.
// Não existe efeito de veneno/condição no motor de regras — só isto três.
export interface StatusEfeito {
  icone: PixelIconName;
  titulo: string;
  cor: string;
}

export function statusEfeitosAtivos(opts: {
  escondido: boolean;
  bonusCa: number;
  vantagemInimiga: boolean | null;
}): StatusEfeito[] {
  const efeitos: StatusEfeito[] = [];
  if (opts.escondido) {
    efeitos.push({ icone: 'rosto', titulo: 'Escondido — os inimigos perderam seu rastro', cor: 'text-blue-300' });
  }
  if (opts.bonusCa > 0) {
    efeitos.push({ icone: 'escudo', titulo: `Postura defensiva — +${opts.bonusCa} de CA até o próximo turno`, cor: 'text-blue-300' });
  }
  if (opts.vantagemInimiga === true) {
    efeitos.push({ icone: 'alerta', titulo: 'Exposto — os inimigos atacam com vantagem no próximo turno', cor: 'text-red-400' });
  } else if (opts.vantagemInimiga === false) {
    efeitos.push({ icone: 'escudo', titulo: 'Esquivando — os inimigos atacam com desvantagem no próximo turno', cor: 'text-emerald-400' });
  }
  return efeitos;
}

export default function StatusEffectIcons({ efeitos }: { efeitos: StatusEfeito[] }) {
  if (efeitos.length === 0) return null;
  return (
    <div className="flex gap-1" role="status" aria-live="polite">
      {efeitos.map((e, i) => (
        <span key={i} title={e.titulo} className={`animate-pulse-slow ${e.cor}`}>
          <PixelIcon name={e.icone} size={14} />
        </span>
      ))}
    </div>
  );
}
