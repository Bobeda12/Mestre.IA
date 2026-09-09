import { useState } from 'react';
import type { AcaoDireta, ArcoAtual, ItemInfo, MundoPersistente } from '../lib/gameplay';
import PixelIcon from './PixelIcon';
import { getLocalImage } from '../lib/utils';

interface Props {
  mundo: MundoPersistente;
  nivel: number;
  inventario: string[];
  ocupado: boolean;
  combate: boolean;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
  aoIdeia: (texto: string) => void;
  /** Fase 6 — o balcão virou modal (jogo/BalcaoMercador.tsx). */
  aoAbrirBalcao: (id: string) => void;
  /** Fase 1 (ADR-0033) — ficha dos itens do herói (preço de venda) e ouro atual, para o balcão do mercador. */
  catalogo?: Record<string, ItemInfo>;
  ouro?: number;
  /** Fase 4 (ADR-0035) — o arco atual e o que falta para encerrar. */
  arco?: ArcoAtual | null;
}

const ACOES: Record<string, string> = {
  examinar: 'Examinar', investigar: 'Investigar', mover: 'Mover', bloquear: 'Bloquear com um objeto',
  desbloquear: 'Remover o bloqueio', abrir: 'Abrir', destrancar: 'Destrancar', quebrar: 'Quebrar',
  acender: 'Acender', apagar: 'Apagar', atravessar: 'Seguir por aqui', ocultar: 'Esconder-se aqui',
  conversar: 'Conversar', negociar: 'Negociar', ajudar: 'Oferecer ajuda', intimidar: 'Intimidar',
  distrair: 'Distrair', acalmar: 'Acalmar',
  pegar: 'Recolher',
};

export default function LivingWorld(p: Props) {
  const [selecao, setSelecao] = useState('');
  const [operacao, setOperacao] = useState('examinar');
  const [meio, setMeio] = useState('');
  const [proposta, setProposta] = useState('');
  const [ideia, setIdeia] = useState('');
  const entidade = p.mundo.entidades.find(e => e.id === selecao);
  const pessoa = p.mundo.pessoas.find(n => n.id === selecao);
  const alvo = entidade ?? pessoa;
  const sociais = ['negociar', 'ajudar', 'intimidar', 'distrair', 'acalmar'];
  const opcoes = pessoa ? ['examinar', 'conversar', ...sociais] : entidade ? [
    'examinar', 'investigar',
    ...(entidade.tipo === 'saida' ? ['atravessar', 'bloquear'] : []),
    ...(entidade.estado === 'bloqueado' ? ['desbloquear'] : []),
    ...(entidade.propriedades.includes('trancado') ? ['destrancar'] : ['abrir']),
    ...(entidade.propriedades.includes('movel') ? ['mover'] : []),
    ...(entidade.propriedades.includes('coletavel') ? ['pegar'] : []),
    ...(entidade.propriedades.includes('inflamavel') ? ['acender'] : []),
    ...(entidade.estado === 'aceso' ? ['apagar'] : []),
    ...(entidade.propriedades.includes('cobertura') ? ['ocultar'] : []),
    ...(entidade.tipo === 'animal' ? ['acalmar'] : ['quebrar']),
  ] : [];
  const acao = opcoes.includes(operacao) ? operacao : 'examinar';
  const meios = [...p.mundo.entidades.filter(e => e.propriedades.includes('movel') && e.id !== selecao
    && !['movido', 'destruido'].includes(e.estado)).map(e => ({id: e.id, nome: e.nome})),
    ...[...new Set(p.inventario)].map(item => ({id: item, nome: item}))];
  const agir = () => {
    if (!alvo) return;
    p.aoAgir({acao: 'agir_no_mundo', alvo: alvo.id, operacao: acao, meio: meio || undefined, proposta},
      `${ACOES[acao]}: ${alvo.nome}`);
  };

  return <section className="living-world font-rpg" aria-label="Mundo vivo">
    <div className="living-world__title"><PixelIcon name="seta" size={20}/><strong>Ao seu redor</strong>
      <span>{p.mundo.local}</span></div>
    {p.mundo.descricao && <p>{p.mundo.descricao}</p>}
    <div className="living-world__entities" aria-label="Pessoas e objetos presentes">
      {p.mundo.pessoas.map(npc => <button type="button" key={`npc:${npc.id}`} disabled={p.ocupado}
        aria-pressed={selecao === npc.id} onClick={() => {setSelecao(npc.id); setOperacao('conversar'); setMeio('');}}>
        <img src={getLocalImage('races', npc.raca || 'Humano')} alt="" width={48} height={48}/>
        <strong>{npc.nome}</strong><small>{npc.disposicao} · confiança {npc.confianca}</small>
      </button>)}
      {p.mundo.entidades.map(e => <button type="button" key={`obj:${e.id}`} disabled={p.ocupado}
        aria-pressed={selecao === e.id} onClick={() => {setSelecao(e.id); setOperacao('examinar'); setMeio('');}}>
        <PixelIcon name={e.tipo === 'saida' ? 'seta' : e.propriedades.includes('investigavel') ? 'pergaminho' : 'bau'} size={36}/>
        <strong>{e.nome}</strong><small>{e.estado}{e.descoberto ? ' · examinado' : ''}</small>
      </button>)}
    </div>
    {!p.mundo.entidades.length && !p.mundo.pessoas.length && <p>Observe este lugar com o Mestre para descobrir quem e o que está aqui.</p>}
    {alvo && <div className="living-world__interaction">
      <strong>{alvo.nome}</strong><p>{alvo.descricao}</p>
      {entidade?.pista && <p className="living-world__fact">Descoberta: {entidade.pista}</p>}
      {pessoa?.necessidade && <p>Pode oferecer: {pessoa.necessidade}.</p>}
      {pessoa?.depoimento && <p>Depoimento não verificado: {pessoa.depoimento}</p>}
      <div className="living-world__controls">
        <label>Ação<select value={acao} onChange={e => setOperacao(e.target.value)} disabled={p.ocupado}>
          {opcoes.map(op => <option key={op} value={op}>{ACOES[op]}</option>)}
        </select></label>
        <label>Usar ou oferecer<select value={meio} onChange={e => setMeio(e.target.value)} disabled={p.ocupado}>
          <option value="">Sem objeto</option>{meios.map(m => <option key={m.id} value={m.id}>{m.nome}</option>)}
        </select></label>
      </div>
      {pessoa && sociais.includes(acao) && <label>Sua proposta<input maxLength={500} value={proposta}
        onChange={e => setProposta(e.target.value)} placeholder="O que você oferece, pede ou tenta fazer?"/></label>}
      <button type="button" className="living-world__primary" onClick={agir}
        disabled={p.ocupado || (!!pessoa && sociais.includes(acao) && !proposta.trim()) || (acao === 'bloquear' && !meio)}>
        {ACOES[acao]}{p.ocupado ? '…' : ''}
      </button>
      {pessoa && pessoa.lembrancas.length > 0 && <details><summary>O que aconteceu entre vocês</summary>
        {pessoa.lembrancas.slice(-4).map((m, i) => <p key={i}>{m}</p>)}</details>}
      {pessoa && (pessoa.vitrine?.length ?? 0) > 0 && <button type="button" className="living-world__primary" disabled={p.ocupado || p.combate}
        onClick={() => p.aoAbrirBalcao(pessoa.id)}>Ver o balcão de {pessoa.nome}</button>}
    </div>}
    <form className="living-world__free" onSubmit={e => {e.preventDefault(); if (ideia.trim()) {p.aoIdeia(ideia); setIdeia('');}}}>
      <label>Outra ideia?<input value={ideia} maxLength={1800} onChange={e => setIdeia(e.target.value)}
        placeholder="Descreva sua intenção. Os controles são só sugestões."/></label>
      <button type="submit" disabled={p.ocupado || !ideia.trim()}>Tentar com o Mestre</button>
    </form>
  </section>;
}
