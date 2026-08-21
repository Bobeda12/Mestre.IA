import { Dices } from 'lucide-react';

// Espelha DadosRolagem (Backend/app/domain/eventos.py) — um evento de
// rolagem estruturado, como sai do frame SSE "tool_event" (Etapa 7).
export interface DadosRolagem {
  texto: string;
  tipo: 'ataque' | 'teste' | 'dano' | 'morte';
  quem: string;
  alvo?: string | null;
  d20?: number | null;
  bonus?: number | null;
  total?: number | null;
  cd?: number | null;
  ca?: number | null;
  sucesso?: boolean | null;
  critico: boolean;
  falha_critica: boolean;
  dano?: number | null;
}

// O jogador vê o número exato da rolagem, não só o resultado — é
// transparência do sistema tanto quanto diversão (PLANO_MESTRE.md, Etapa 7):
// prova que o mestre não está trapaceando atrás da narrativa.
export default function RollCard({ dados }: { dados: DadosRolagem }) {
  const cor = dados.critico
    ? 'border-yellow-600/60 text-yellow-300 bg-yellow-950/20'
    : dados.falha_critica
      ? 'border-red-700/60 text-red-300 bg-red-950/20'
      : dados.sucesso
        ? 'border-emerald-700/50 text-emerald-300 bg-emerald-950/10'
        : 'border-gray-700 text-gray-400 bg-gray-900/40';

  const alvoLabel = dados.cd != null ? `CD ${dados.cd}` : dados.ca != null ? `CA ${dados.ca}` : null;
  // "ataque"/"dano" usam o vocabulário de combate (ACERTO/ERROU); "teste" e
  // "morte" usam o vocabulário do próprio evento (SUCESSO/FALHA) — mesma
  // distinção que o texto formatado no backend já faz (tools.py/combat.py).
  const ehCombate = dados.tipo === 'ataque' || dados.tipo === 'dano';
  const rotulo = dados.critico
    ? 'CRÍTICO!'
    : dados.falha_critica
      ? 'FALHA CRÍTICA'
      : dados.sucesso
        ? ehCombate ? 'ACERTO' : 'SUCESSO'
        : ehCombate ? 'ERROU' : 'FALHA';

  return (
    <div className="flex justify-center my-2 animate-fade-in" role="status">
      <div className={`flex items-center gap-2 px-4 py-1.5 rounded-full border font-mono text-xs ${cor}`}>
        <Dices size={13} className="shrink-0" />
        {dados.d20 != null && (
          <span>
            d20({dados.d20}){dados.bonus != null && dados.bonus !== 0 ? ` ${dados.bonus > 0 ? '+' : ''}${dados.bonus}` : ''}
            {dados.total != null && ` = ${dados.total}`}
            {alvoLabel && ` vs ${alvoLabel}`}
          </span>
        )}
        {dados.dano != null && dados.dano > 0 && <span>· {dados.dano} dano</span>}
        <span className="font-bold tracking-wide">{rotulo}</span>
      </div>
    </div>
  );
}
