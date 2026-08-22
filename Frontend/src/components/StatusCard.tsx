import { HeartPulse, Skull } from 'lucide-react';

// Espelha EventoStatus (Backend/app/domain/eventos.py) — cura e morte de
// inimigo (Etapa 10, A-7): não são rolagem de d20, por isso não usam
// RollCard, mas mereciam o mesmo tratamento de card em vez de texto solto
// com emoji dentro da narrativa.
export interface EventoStatus {
  tipo: 'cura' | 'morte_inimigo';
  quem: string;
  valor?: number | null;
}

export default function StatusCard({ dados }: { dados: EventoStatus }) {
  const cura = dados.tipo === 'cura';
  const cor = cura
    ? 'border-emerald-700/50 text-emerald-300 bg-emerald-950/10'
    : 'border-gray-700 text-gray-400 bg-gray-900/40';

  return (
    <div className="flex justify-center my-2 animate-fade-in" role="status">
      <div className={`flex items-center gap-2 px-4 py-1.5 rounded-full border font-mono text-xs ${cor}`}>
        {cura ? <HeartPulse size={13} className="shrink-0" /> : <Skull size={13} className="shrink-0" />}
        <span className="font-bold tracking-wide">
          {cura ? `+${dados.valor ?? 0} PV` : `${dados.quem} caiu`}
        </span>
      </div>
    </div>
  );
}
