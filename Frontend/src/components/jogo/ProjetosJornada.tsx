import { useState } from 'react';
import type { AcaoDireta, MundoPersistente } from '../../lib/gameplay';

interface Props {
  projetos: NonNullable<MundoPersistente['projetos']>;
  bloqueado: boolean;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
}

const BOTAO = 'px-2 py-1.5 border border-gray-600 text-xs font-rpg text-rpg-gold disabled:opacity-40 disabled:cursor-not-allowed focus-visible:outline focus-visible:outline-rpg-gold';

export default function ProjetosJornada({ projetos, bloqueado, aoAgir }: Props) {
  const [ambicao, setAmbicao] = useState('');
  const ativo = projetos.some(p => p.estado === 'ativo');
  // Só limpa o campo quando o projeto realmente nasce (achado da auditoria
  // pré-lançamento: limpar direto no submit perdia o texto — até 500
  // caracteres — se o envio falhasse, sem chance de recuperar). Ajuste de
  // estado durante o render ao detectar a transição, mesmo padrão já usado
  // em DockAcoes.tsx (`chaveSelecao`/`chaveAnterior`), em vez de um
  // `useEffect` com `setState` síncrono no corpo.
  const [ativoAnterior, setAtivoAnterior] = useState(ativo);
  if (ativo !== ativoAnterior) {
    setAtivoAnterior(ativo);
    if (ativo) setAmbicao('');
  }
  return (
    <section className="space-y-3" aria-label="Projetos da jornada">
      <h3 className="text-[10px] text-rpg-gold uppercase font-rpg tracking-widest">O que quero construir</h3>
      {!ativo && (
        <form className="space-y-2" onSubmit={e => {
          e.preventDefault();
          if (bloqueado || !ambicao.trim()) return;
          aoAgir({ acao: 'gerir_projeto', operacao: 'iniciar', proposta: ambicao.trim() }, 'Iniciar meu projeto');
        }}>
          <p className="text-xs text-gray-400">Escolha uma mudança que deseja deixar no mundo. Você decide os meios.</p>
          <textarea aria-label="Minha ambição" value={ambicao} maxLength={500} disabled={bloqueado}
            onChange={e => setAmbicao(e.target.value)} rows={2}
            className="w-full bg-black/40 border border-gray-700 p-2 text-xs text-gray-200 focus:border-rpg-gold outline-none"
            placeholder="O que faria esta jornada valer a pena para você?" />
          <button className={BOTAO} disabled={bloqueado || !ambicao.trim()}>Assumir esta ambição</button>
        </form>
      )}
      {[...projetos].reverse().map(p => (
        <article key={p.id} className="border-2 border-gray-700 bg-black/40 p-2 space-y-2">
          <p className="text-sm text-rpg-gold font-rpg">{p.ambicao}</p>
          <p className="text-[11px] text-gray-400">{p.local} · {p.estado === 'ativo' ? 'Em construção' : p.estado === 'concluido' ? 'Conquista realizada' : 'Deixado para trás'}</p>
          {!p.condicoes.length && p.estado === 'ativo' && <p className="text-xs text-gray-300">Converse com o Mestre sobre o que tornaria isso possível.</p>}
          {p.condicoes.map(c => (
            <div key={c.id} className="border-l-2 border-gray-600 pl-2 text-xs space-y-1">
              <p className="text-gray-200">{c.descricao}</p>
              <p className="text-gray-400">{c.estado === 'aberta' ? 'Em aberto — encontre seu caminho' : c.estado === 'superada' ? 'Um novo caminho tornou isso desnecessário' : 'Mudança realizada'}</p>
              {c.evidencia && <p className="text-emerald-200">{c.evidencia}</p>}
            </div>
          ))}
          {p.estado === 'ativo' && <div className="flex flex-wrap gap-2">
            <button className={BOTAO} disabled={bloqueado || !p.condicoes.length || p.condicoes.some(c => c.estado === 'aberta')}
              onClick={() => aoAgir({ acao: 'gerir_projeto', operacao: 'concluir', alvo: p.id }, 'Celebrar minha conquista')}>Concretizar projeto</button>
            <button className={BOTAO} disabled={bloqueado}
              onClick={() => aoAgir({ acao: 'gerir_projeto', operacao: 'abandonar', alvo: p.id }, 'Deixar este projeto para trás')}>Deixar para trás</button>
          </div>}
          {p.propostas?.map(a => {
            const conflito = p.propostas?.some(v => v.id !== a.id && v.condicao === a.condicao
              && (v.estado === 'aceita' || v.estado === 'cumprida') && (v.exclusiva || a.exclusiva));
            const aberta = p.condicoes.some(c => c.id === a.condicao && c.estado === 'aberta');
            const decidir = (operacao: string) => aoAgir(
              { acao: 'decidir_acordo_projeto', operacao, alvo: p.id, proposta: a.id },
              `${operacao === 'aceitar' ? 'Aceitar' : operacao === 'recusar' ? 'Recusar' : 'Renunciar ao'} acordo`.slice(0, 80),
            );
            return <div key={a.id} className="border border-amber-700/40 p-2 space-y-1.5 text-xs">
              <p className="text-rpg-gold font-rpg">{a.nome_npc}</p>
              {a.nome_organizacao && <p className="text-amber-200">Representa {a.nome_organizacao}</p>}
              <p className="text-gray-200">Oferece: {a.oferta}</p>
              <p className="text-gray-200">Em troca: {a.contrapartida}</p>
              <p className="text-gray-400">{a.motivo_declarado}</p>
              {a.exclusiva && <p className="text-amber-200">Exige exclusividade nesta parte do projeto.</p>}
              <p className="text-gray-400">{({ oferecida: 'Proposta em aberto', aceita: 'Compromisso assumido', recusada: 'Proposta recusada', cumprida: 'Contrapartida cumprida', renunciada: 'Você renunciou' })[a.estado]}</p>
              {a.evidencia && <p className="text-emerald-200">{a.evidencia}</p>}
              {a.estado === 'oferecida' && p.estado === 'ativo' && <>
                <p className="text-gray-400">Aceitar assume a contrapartida. A entrega da oferta acontece na aventura.</p>
                {conflito && <p className="text-amber-200">Há um compromisso incompatível. Renuncie a ele para aceitar este.</p>}
                <div className="flex gap-2">
                  <button className={BOTAO} disabled={bloqueado || conflito || !aberta} onClick={() => decidir('aceitar')}>Aceitar</button>
                  <button className={BOTAO} disabled={bloqueado} onClick={() => decidir('recusar')}>Recusar</button>
                </div>
              </>}
              {(a.estado === 'aceita' || a.estado === 'cumprida') && <button className={BOTAO} disabled={bloqueado}
                onClick={() => decidir('renunciar')}>Renunciar ao compromisso</button>}
            </div>;
          })}
        </article>
      ))}
    </section>
  );
}
