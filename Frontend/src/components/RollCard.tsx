import { useEffect, useState } from 'react';
import { prefereMovimentoReduzido } from '../lib/acessibilidade';
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
  // Fase 0 da revisão de gameplay (Etapa 12/13) — vantagem/desvantagem rola
  // dois d20; `d20` já é o escolhido (maior/menor), `d20_extra` é o
  // descartado, guardado só pra mostrar os dois no card.
  d20_extra?: number | null;
  vantagem?: boolean | null;
  // Rodada de conserto (Parte 2, item I) — "Teste de Sabedoria" não dizia
  // se era pra perceber a emboscada ou resistir a um medo; `motivo` é o
  // que o modelo já descreve pra `rolar_teste` (Backend/app/services/
  // tools.py), agora chegando ao card em vez de morrer na chamada.
  motivo?: string | null;
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
// Fase 8 (revisão de gameplay) — "fator cassino": quanto tempo o dado gira
// antes de revelar o número. GameChat.tsx pausa o consumo do streaming pela
// mesma duração quando um evento de rolagem chega, pra narração não
// continuar antes do dado "parar de rolar" na tela.
// Rodada de conserto — subiu de 550ms: num ícone de 13px girando a 1
// volta/segundo (o padrão do Tailwind), 550ms é menos de meia volta —
// quase imperceptível mesmo quando a animação roda. 700ms com o giro mais
// rápido (ver `[animation-duration:...]` abaixo) dá mais de uma volta
// inteira dentro da janela.
// Item 3 da rodada de polish pós-remaster ("fator cassino") — subiu de
// 700ms pra ~1s: o giro sozinho não vendia suspense de cassino, precisava
// de mais tempo pro número embaralhando (abaixo) dar pra ler pelo menos
// 2-3 trocas antes de parar.
export const DURACAO_ANIMACAO_DADO_MS = 1000;
// Intervalo de troca do número embaralhando — rápido o bastante pra parecer
// "girando", devagar o bastante pra não virar borrão ilegível.
const INTERVALO_EMBARALHAR_MS = 70;

export default function RollCard({ dados }: { dados: DadosRolagem }) {
  // Rodada de conserto — achado ao vivo: `index.css` já desliga a animação
  // via CSS quando o sistema pede menos movimento, mas o `setTimeout`
  // continuava esperando os mesmos 700ms mesmo com o dado parado — o
  // jogador via a narração travar sem nenhum giro pra justificar a
  // espera. `useState(prefereMovimentoReduzido)` (inicializador lento, não
  // um efeito) já nasce revelado nesse caso, sem esperar nada.
  const [revelado, setRevelado] = useState(prefereMovimentoReduzido);
  // Item 3 — número "embaralhando" (1-20 aleatório trocando rápido) durante
  // a espera, no lugar de só o ícone girando sem número nenhum. Pulado
  // inteiro quando `prefereMovimentoReduzido()` (mesmo guard do efeito
  // abaixo — `revelado` já nasce `true` nesse caso, então este efeito nem
  // chega a rodar).
  const [numeroEmbaralhado, setNumeroEmbaralhado] = useState(() => 1 + Math.floor(Math.random() * 20));
  useEffect(() => {
    if (prefereMovimentoReduzido()) return;
    const t = setTimeout(() => setRevelado(true), DURACAO_ANIMACAO_DADO_MS);
    const i = setInterval(() => setNumeroEmbaralhado(1 + Math.floor(Math.random() * 20)), INTERVALO_EMBARALHAR_MS);
    return () => { clearTimeout(t); clearInterval(i); };
  }, []);

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

  if (!revelado && dados.d20 != null) {
    // "Rolando": o número existe (chegou pronto do backend, ver ADR-0006 —
    // o resultado nunca é decidido no cliente), só a REVELAÇÃO é adiada,
    // pra dar o "fator cassino" sem fingir suspense que o servidor não tem.
    return (
      <div className="flex flex-col items-center gap-1 my-2 animate-fade-in" role="status" aria-label="Rolando o dado">
        <div className="flex items-center gap-2 px-3 py-1.5 border-2 border-gray-700 text-gray-400 bg-gray-900/40 font-rpg text-xs">
          {/* Rodada de conserto — 13px→22px (o giro era quase invisível
              nesse tamanho) e o giro em si mais rápido (~0.45s/volta em vez
              de 1s), pra caber mais de uma volta inteira dentro dos 700ms
              de espera acima. */}
          <PixelIcon name="dado" size={22} className="animate-spin [animation-duration:0.45s]" />
          <span className="tracking-widest tabular-nums">d20({numeroEmbaralhado})</span>
        </div>
      </div>
    );
  }

  return (
    <TooltipProvider delayDuration={150}>
      <div className="flex flex-col items-center gap-1 my-2 animate-fade-in" role="status">
        {titulo && <span className="text-[10px] uppercase tracking-widest text-gray-500">{titulo}</span>}
        {/* Rodada de conserto (Parte 2, item I) — o motivo do teste, não só
            o atributo. "Teste de Sabedoria" sozinho não diz se é pra
            perceber uma emboscada ou resistir a medo. */}
        {/* Item 4 da rodada de polish pós-remaster — tirado `max-w-[220px]`
            e `truncate`: o motivo não pode mais terminar em "..." nem ficar
            cortado. `title` continua como reforço de acessibilidade, mesmo
            com o texto inteiro já visível. */}
        {dados.tipo === 'teste' && dados.motivo && (
          <span className="max-w-[90vw] text-[10px] text-gray-500 italic text-center" title={dados.motivo}>
            {dados.motivo}
          </span>
        )}
        <div className={`flex items-center gap-2 px-3 py-1.5 border-2 font-rpg text-xs ${cor}`}>
          <PixelIcon name="dado" size={13} />
          {dados.d20 != null && (
            <span>
              {dados.vantagem != null && dados.d20_extra != null ? (
                <Tooltip>
                  <TooltipTrigger asChild>
                    <span className="underline decoration-dotted decoration-current/50 cursor-help">
                      d20({dados.d20_extra}) d20({dados.d20})
                    </span>
                  </TooltipTrigger>
                  <TooltipContent>
                    {dados.vantagem ? 'Vantagem: fica com o maior dos dois dados.' : 'Desvantagem: fica com o menor dos dois dados.'}
                  </TooltipContent>
                </Tooltip>
              ) : (
                `d20(${dados.d20})`
              )}
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
