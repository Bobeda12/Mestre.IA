import type { PessoaMundo } from '../../lib/gameplay';
import { getLocalImage } from '../../lib/utils';
import PixelBar from '../PixelBar';
import PixelIcon from '../PixelIcon';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '../ui/tooltip';

// Fase 6 (ADR-0036) — RELAÇÕES funde as duas fontes que o backend manda
// sobre pessoas: `reputacoes` (ajustar_reputacao_npc, -100..+100, Etapa 5)
// e `mundo.pessoas` (Mundo Vivo: disposição, confiança, necessidade,
// depoimento, lembranças). Um card por nome; clicar seleciona a pessoa no
// palco (Etapa 6.2) — a aba é consulta, a ação acontece no dock.
interface Props {
  reputacoes: Record<string, number>;
  pessoas: PessoaMundo[];
  onSelecionar?: (id: string) => void;
}

function leituraReputacao(npc: string, valor: number): string {
  if (valor > 50) return `${npc} confia profundamente em você.`;
  if (valor > 15) return `${npc} confia em você.`;
  if (valor < -50) return `${npc} é seu inimigo declarado.`;
  if (valor < -15) return `${npc} desconfia de você.`;
  return `${npc} ainda não formou opinião sobre você.`;
}

export default function AbaRelacoes(p: Props) {
  const nomes = new Set<string>([...p.pessoas.map(x => x.nome), ...Object.keys(p.reputacoes)]);
  if (nomes.size === 0) {
    return <p className="text-sm text-gray-400 font-rpg text-center py-8">Nenhum NPC conhecido ainda.</p>;
  }
  const cards = [...nomes].map(nome => ({ nome, pessoa: p.pessoas.find(x => x.nome === nome), reputacao: p.reputacoes[nome] }));

  return (
    <TooltipProvider delayDuration={150}>
      <div className="space-y-2 animate-fade-in">
        {cards.map(({ nome, pessoa, reputacao }) => {
          const valor = reputacao ?? 0;
          const cor = valor > 15 ? 'bg-emerald-600' : valor < -15 ? 'bg-red-600' : 'bg-gray-500';
          const Corpo = (
            <div className="bg-black/50 border-2 border-gray-700 p-2 transition-transform hover:-translate-y-0.5 hover:border-gray-500 focus-visible:outline-none focus-visible:border-rpg-gold text-left w-full">
              <div className="flex items-center gap-2 mb-1">
                {pessoa && <img src={getLocalImage('races', pessoa.raca || 'Humano')} alt="" width={32} height={32} className="shrink-0" />}
                <div className="min-w-0 flex-1">
                  <span className="block text-sm text-gray-100 font-rpg truncate">{nome}</span>
                  {pessoa && <span className="block text-[10px] text-gray-400 font-rpg truncate">{pessoa.disposicao} · confiança {pessoa.confianca}</span>}
                </div>
                {reputacao !== undefined && <span className="text-[10px] text-gray-400 font-rpg shrink-0">{valor > 0 ? `+${valor}` : valor}</span>}
              </div>
              {reputacao !== undefined && (
                <>
                  <PixelBar value={valor + 100} max={200} segments={10} colorClass={cor} />
                  <div className="flex justify-between mt-0.5 text-[8px] text-gray-600 uppercase tracking-widest"><span>Inimigo</span><span>Aliado</span></div>
                </>
              )}
              {pessoa?.necessidade && <p className="text-[11px] text-gray-300 mt-1">Pode oferecer: {pessoa.necessidade}.</p>}
              {pessoa?.depoimento && <p className="text-[11px] text-gray-400 italic mt-1">Depoimento não verificado: {pessoa.depoimento}</p>}
              {pessoa && pessoa.lembrancas.length > 0 && (
                <div className="mt-1.5 border-t border-gray-800 pt-1.5 space-y-0.5">
                  <span className="text-[9px] text-gray-500 uppercase tracking-widest font-rpg flex items-center gap-1"><PixelIcon name="pergaminho" size={9} /> Entre vocês</span>
                  {pessoa.lembrancas.slice(-4).map((m, i) => <p key={i} className="text-[11px] text-gray-300 leading-snug">{m}</p>)}
                </div>
              )}
            </div>
          );
          return (
            <Tooltip key={nome}>
              <TooltipTrigger asChild>
                {pessoa && p.onSelecionar
                  ? <button type="button" onClick={() => p.onSelecionar!(pessoa.id)} aria-label={`Selecionar ${nome} no palco`} className="block w-full">{Corpo}</button>
                  : <div tabIndex={0} className="cursor-help">{Corpo}</div>}
              </TooltipTrigger>
              <TooltipContent>{reputacao !== undefined ? leituraReputacao(nome, valor) : pessoa?.descricao}</TooltipContent>
            </Tooltip>
          );
        })}
      </div>
    </TooltipProvider>
  );
}
