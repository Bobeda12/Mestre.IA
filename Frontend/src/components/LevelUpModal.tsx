import type { AcaoDireta, OpcaoNivel } from '../lib/gameplay';
import PanelFrame from './PanelFrame';
import PixelIcon from './PixelIcon';

// Fase 3 do plano "jogo completo" (ADR-0034) — a escolha de nível é do
// jogador, pela interface: o servidor lista as opções válidas para o nível
// pendente (+1 atributo, talento, ou especialização nos marcos 3 e 7) e o
// clique resolve pelo juiz (/game/action), sem narrador.
interface Props {
  nivel: number;
  opcoes: OpcaoNivel[];
  ocupado: boolean;
  aoEscolher: (acao: AcaoDireta, rotulo: string) => void;
  aoAdiar: () => void;
}

const ICONE: Record<OpcaoNivel['tipo'], 'estrela' | 'pergaminho' | 'seta'> = { atributo: 'estrela', talento: 'pergaminho', especializacao: 'seta' };

export default function LevelUpModal(p: Props) {
  const grupos: { titulo: string; tipo: OpcaoNivel['tipo'] }[] = [
    { titulo: 'Atributo (+1)', tipo: 'atributo' },
    { titulo: 'Talento', tipo: 'talento' },
    { titulo: 'Especialização', tipo: 'especializacao' },
  ];
  return (
    <div className="absolute inset-0 z-30 flex items-center justify-center bg-black/80 p-4 animate-fade-in" role="dialog" aria-modal="true" aria-labelledby="levelup-titulo">
      <PanelFrame className="w-full max-w-2xl bg-[#0b0e0a] p-4 max-h-full overflow-y-auto">
        <div className="flex items-center justify-between gap-2 mb-3">
          <h2 id="levelup-titulo" className="font-pixel-title text-rpg-gold text-sm flex items-center gap-2"><PixelIcon name="estrela" size={16} /> NÍVEL {p.nivel}</h2>
          <button type="button" onClick={p.aoAdiar} className="text-[10px] font-rpg text-gray-400 hover:text-gray-200 uppercase tracking-widest">Decidir depois</button>
        </div>
        <p className="font-rpg text-gray-300 text-sm mb-3">Uma escolha por nível. Números do servidor; o narrador só lembra, nunca decide.</p>
        {grupos.map(g => {
          const itens = p.opcoes.filter(o => o.tipo === g.tipo);
          if (!itens.length) return null;
          return (
            <section key={g.tipo} className="mb-3">
              <h3 className="font-pixel-title text-[9px] text-gray-400 tracking-widest mb-1.5">{g.titulo}</h3>
              <div className="grid grid-cols-2 md:grid-cols-3 gap-1.5">
                {itens.map(o => (
                  <button type="button" key={`${o.tipo}:${o.id}`} disabled={p.ocupado}
                    onClick={() => p.aoEscolher({ acao: 'escolher_nivel', nivel_escolha: p.nivel, tipo_escolha: o.tipo, opcao: o.id }, `Nível ${p.nivel}: ${o.nome}`)}
                    className="text-left border-2 border-gray-700 hover:border-rpg-gold bg-black/60 p-2 disabled:opacity-50 focus-visible:outline-none focus-visible:border-rpg-gold">
                    <span className="flex items-center gap-1 font-rpg text-rpg-gold text-sm"><PixelIcon name={ICONE[o.tipo]} size={12} />{o.nome}</span>
                    <span className="block text-[11px] text-gray-300 font-rpg leading-snug">{o.descricao}</span>
                  </button>
                ))}
              </div>
            </section>
          );
        })}
      </PanelFrame>
    </div>
  );
}
