import PixelIcon from './PixelIcon';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

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
  // Etapa 11 (B-8) — "de onde vem o bônus": qual atributo/arma originou a
  // rolagem, e a decomposição do bônus somado.
  atributo?: string | null;
  arma?: string | null;
  partes_bonus?: { rotulo: string; valor: number }[] | null;
}

const NOME_ATRIBUTO: Record<string, string> = {
  forca: 'Força', destreza: 'Destreza', constituicao: 'Constituição',
  inteligencia: 'Inteligência', sabedoria: 'Sabedoria', carisma: 'Carisma',
};

// Envolve uma sigla (CD, CA...) num tooltip que explica o que ela significa
// — pro amigo que nunca jogou D&D não precisar perguntar no chat.
function Sigla({ explicacao, children }: { explicacao: string; children: React.ReactNode }) {
  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <span className="underline decoration-dotted decoration-current/50 cursor-help">{children}</span>
      </TooltipTrigger>
      <TooltipContent>{explicacao}</TooltipContent>
    </Tooltip>
  );
}

function formatSinal(valor: number): string {
  return `${valor >= 0 ? '+' : ''}${valor}`;
}

// O jogador vê o número exato da rolagem, não só o resultado — é
// transparência do sistema tanto quanto diversão (PLANO_MESTRE.md, Etapa 7):
// prova que o mestre não está trapaceando atrás da narrativa. A Etapa 11
// (B-8) leva isso além do número: mostra do que é o teste e de onde vem
// cada parte do bônus, em vez de um "+4" que pede confiança.
export default function RollCard({ dados }: { dados: DadosRolagem }) {
  const cor = dados.critico
    ? 'border-yellow-600/60 text-yellow-300 bg-yellow-950/20'
    : dados.falha_critica
      ? 'border-red-700/60 text-red-300 bg-red-950/20'
      : dados.sucesso
        ? 'border-emerald-700/50 text-emerald-300 bg-emerald-950/10'
        : 'border-gray-700 text-gray-400 bg-gray-900/40';

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

  const titulo = dados.tipo === 'teste' && dados.atributo
    ? `Teste de ${NOME_ATRIBUTO[dados.atributo] || dados.atributo}`
    : dados.tipo === 'ataque' && dados.quem === 'heroi' && dados.arma
      ? `Ataque com ${dados.arma}`
      : null;

  const temBonus = dados.bonus != null && dados.bonus !== 0;
  const temBreakdown = temBonus && dados.partes_bonus && dados.partes_bonus.length > 0;

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex flex-col items-center gap-1 my-2 animate-fade-in" role="status">
        {titulo && <span className="text-[10px] uppercase tracking-widest text-gray-500">{titulo}</span>}
        <div className={`flex items-center gap-2 px-3 py-1.5 border-2 font-rpg text-xs ${cor}`}>
          <PixelIcon name="dado" size={13} />
          {dados.d20 != null && (
            <span>
              d20({dados.d20})
              {temBonus && (
                temBreakdown ? (
                  <Tooltip>
                    <TooltipTrigger asChild>
                      <span className="underline decoration-dotted decoration-current/50 cursor-help">
                        {` ${formatSinal(dados.bonus!)}`}
                      </span>
                    </TooltipTrigger>
                    <TooltipContent>
                      {dados.partes_bonus!.map(p => `${p.rotulo} ${formatSinal(p.valor)}`).join(' · ')}
                    </TooltipContent>
                  </Tooltip>
                ) : (
                  <span>{` ${formatSinal(dados.bonus!)}`}</span>
                )
              )}
              {dados.total != null && ` = ${dados.total}`}
              {dados.cd != null && (
                <>
                  {' vs '}
                  <Sigla explicacao="Classe de Dificuldade — o número que sua rolagem precisa alcançar ou superar para ter sucesso.">
                    CD {dados.cd}
                  </Sigla>
                </>
              )}
              {dados.ca != null && (
                <>
                  {' vs '}
                  <Sigla explicacao="Classe de Armadura — o número que seu ataque precisa alcançar ou superar para acertar.">
                    CA {dados.ca}
                  </Sigla>
                </>
              )}
            </span>
          )}
          {dados.dano != null && dados.dano > 0 && <span>· {dados.dano} dano</span>}
          <span className="font-bold tracking-wide">{rotulo}</span>
        </div>
      </div>
    </TooltipProvider>
  );
}
