import type { MundoPersistente } from '../../lib/gameplay';

interface Props {
  oportunidades: NonNullable<MundoPersistente['imersao']>['oportunidades'];
}

export default function SinaisDaCena({ oportunidades }: Props) {
  if (!oportunidades.length) return null;
  return (
    <details className="shrink-0 border-t border-gray-800 bg-gray-900 px-4 py-2 text-xs" aria-label="Sinais da cena">
      <summary className="cursor-pointer font-rpg text-rpg-gold focus-visible:outline focus-visible:outline-rpg-gold">
        O que chama sua atenção <span className="text-gray-400">({oportunidades.length})</span>
      </summary>
      <div className="max-h-32 overflow-y-auto custom-scrollbar space-y-2 pt-2">
        {oportunidades.map(o => (
          <p key={o.id} className="text-gray-200 leading-relaxed">
            {o.percepcao}
            {o.risco && <span className="block text-amber-200/80">{o.risco}</span>}
          </p>
        ))}
      </div>
    </details>
  );
}
