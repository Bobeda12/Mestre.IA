import { useState } from 'react';
import type { AcaoDireta, MundoPersistente } from '../lib/gameplay';
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
  const [objetivo, setObjetivo] = useState('');
  const [conflitoSelecionado, setConflito] = useState('');
  const [abordagem, setAbordagem] = useState('atrasar');
  const entidade = p.mundo.entidades.find(e => e.id === selecao);
  const pessoa = p.mundo.pessoas.find(n => n.id === selecao);
  const alvo = entidade ?? pessoa;
  const conflitos = p.mundo.conflitos.filter(c => c.estado === 'ativo');
  const conflito = conflitos.find(c => c.id === conflitoSelecionado) ?? conflitos[0];
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
    </div>}
    <form className="living-world__free" onSubmit={e => {e.preventDefault(); if (ideia.trim()) {p.aoIdeia(ideia); setIdeia('');}}}>
      <label>Outra ideia?<input value={ideia} maxLength={1800} onChange={e => setIdeia(e.target.value)}
        placeholder="Descreva sua intenção. Os controles são só sugestões."/></label>
      <button type="submit" disabled={p.ocupado || !ideia.trim()}>Tentar com o Mestre</button>
    </form>
    <details><summary>O mundo continua</summary>
      {p.mundo.conflitos.length === 0 && <p>Nenhum conflito conhecido neste local.</p>}
      {p.mundo.conflitos.map(c => <article key={c.id} className="living-world__conflict">
        <strong>{c.nome}</strong><p>{c.estado === 'ativo' ? c.sinal : c.desfecho}</p>
        {c.estado === 'ativo' && <><progress max={c.etapas} value={c.progresso}/><span>{c.progresso}/{c.etapas} · próximo avanço em {c.minutos_restantes} min de jogo</span></>}
      </article>)}
      {conflito && <div className="living-world__interaction">
        <label>Em qual conflito?<select value={conflito.id} onChange={e => setConflito(e.target.value)}>
          {conflitos.map(c => <option value={c.id} key={c.id}>{c.nome}</option>)}
        </select></label>
        <label>Como intervir<select value={abordagem} onChange={e => setAbordagem(e.target.value)}>
          <option value="atrasar">Ganhar tempo</option><option value="apoiar">Apoiar a iniciativa</option><option value="resolver">Construir um acordo</option>
        </select></label>
        <label>Proposta concreta<input value={proposta} maxLength={500} onChange={e => setProposta(e.target.value)}/></label>
        <small>Um acordo exige cooperação do responsável e duas intervenções bem-sucedidas.</small>
        <button type="button" disabled={p.ocupado || !proposta.trim()} onClick={() => p.aoAgir({acao:'intervir_conflito',
          alvo:conflito.id, operacao:abordagem, proposta}, `${abordagem}: ${conflito.nome}`)}>Intervir</button>
      </div>}
    </details>
    <details><summary>Meu caminho e minhas descobertas</summary>
      <p>{p.mundo.aptidao.nome}: +{p.mundo.aptidao.bonus} em {p.mundo.aptidao.acoes.map(a => ACOES[a] ?? a).join(', ')}.</p>
      <form onSubmit={e => {e.preventDefault(); if (objetivo.trim()) {p.aoAgir({acao:'definir_objetivo', proposta:objetivo}, `Meu objetivo: ${objetivo}`); setObjetivo('');}}}>
        <label>O que você quer fazer agora?<input maxLength={500} value={objetivo} onChange={e => setObjetivo(e.target.value)} placeholder="Você pode mudar de rumo."/></label>
        <button type="submit" disabled={p.ocupado || !objetivo.trim()}>Seguir este objetivo</button>
      </form>
      {(['3','7'] as const).map(marco => <div className="living-world__paths" key={marco}>
        <strong>Nível {marco} · {p.mundo.especializacoes[marco] ?? 'Escolha opcional'}</strong>
        {(['explorador','diplomata','combatente'] as const).map(caminho => <button type="button" key={caminho}
          disabled={p.ocupado || p.combate || p.nivel < Number(marco)} aria-pressed={p.mundo.especializacoes[marco] === caminho}
          onClick={() => p.aoAgir({acao:'escolher_especializacao', marco, escolha:caminho}, `Especializar: ${caminho}`)}>
          {caminho}<small>{caminho === 'combatente' ? '+1 dano' : caminho === 'diplomata' ? '+1 testes sociais' : '+1 testes de exploração'}</small>
        </button>)}
        <small>Pode trocar entre encontros.</small>
      </div>)}
      {p.mundo.conhecimento.slice(-12).reverse().map((f, i) => <p className="living-world__fact" key={`${f.turno}:${i}`}>
        <strong>{f.natureza}</strong> · {f.texto}<small>Fonte: {f.fonte}</small>
      </p>)}
    </details>
  </section>;
}
