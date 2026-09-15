import type { AcaoDireta, MundoPersistente } from '../../lib/gameplay';

interface Props {
  mundo: MundoPersistente;
  bloqueado: boolean;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
}

const BOTAO = 'px-2 py-1.5 border border-gray-600 text-xs font-rpg text-rpg-gold disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-rpg-gold';
const ATRIBUTOS: Record<string, string> = { forca: 'Força', destreza: 'Destreza', constituicao: 'Constituição', inteligencia: 'Inteligência', sabedoria: 'Sabedoria', carisma: 'Carisma' };

export default function LugaresDaJornada({ mundo, bloqueado, aoAgir }: Props) {
  const dados = mundo.instalacoes;
  if (!dados || (!dados.lugares.length && !dados.preparacao)) {
    return <section className="space-y-2" aria-label="Lugares que você transformou">
      <h3 className="text-[10px] text-rpg-gold uppercase font-rpg tracking-widest">Lugares que você transformou</h3>
      <p className="text-xs text-gray-400 font-rpg">Nenhum lugar transformado ainda.</p>
    </section>;
  }
  return <section className="space-y-2" aria-label="Lugares que você transformou">
    <h3 className="text-[10px] text-rpg-gold uppercase font-rpg tracking-widest">Lugares que você transformou</h3>
    {dados.preparacao && <p className="text-xs text-emerald-200">
      Preparação de {dados.preparacao.nome}: +1 no próximo teste livre de {ATRIBUTOS[dados.preparacao.atributo] ?? dados.preparacao.atributo}.
      {' '}Expira em {Math.max(0, dados.preparacao.expira_em - mundo.minutos)} min de jogo.
    </p>}
    {dados.lugares.map(i => <article key={i.id} className="border-2 border-gray-700 bg-black/40 p-2 space-y-2">
      <p className="font-rpg text-sm text-rpg-gold">{i.nome}</p>
      <p className="text-xs text-gray-200">{i.descricao}</p>
      <p className="text-[11px] text-gray-400">{i.local} · {i.tipo === 'abrigo' ? 'Abrigo' : 'Oficina'}</p>
      <p className="text-xs text-gray-300">{i.evidencia}</p>
      <p className="text-xs text-gray-400">{i.tipo === 'abrigo'
        ? 'Permite descanso longo aqui. Oito horas passam e o mundo continua.'
        : `Uma hora de preparação: +1 no próximo teste livre de ${ATRIBUTOS[i.atributo] ?? i.atributo}. Válido por 24 horas; não acumula.`}</p>
      {!i.ativa ? <button className={BOTAO} disabled={bloqueado || i.local !== mundo.local}
        onClick={() => aoAgir({ acao: 'usar_instalacao', alvo: i.id, operacao: 'inaugurar' }, 'Inaugurar melhoria')}>Inaugurar</button>
        : i.tipo === 'abrigo' ? <button className={BOTAO} disabled={bloqueado || !i.disponivel}
          onClick={() => aoAgir({ acao: 'descansar', tipo: 'longo' }, 'Descansar no abrigo')}>Descansar — 8 horas</button>
          : <button className={BOTAO} disabled={bloqueado || !i.disponivel || !!dados.preparacao}
            onClick={() => aoAgir({ acao: 'usar_instalacao', alvo: i.id, operacao: 'preparar' }, 'Preparar próxima expedição')}>Preparar — 1 hora</button>}
      {i.ativa && !i.disponivel && <p className="text-[11px] text-gray-400">
        {i.local !== mundo.local ? 'Visite este lugar para usar a melhoria.' : 'A melhoria está inacessível ou perdeu as condições de uso.'}
      </p>}
    </article>)}
  </section>;
}
