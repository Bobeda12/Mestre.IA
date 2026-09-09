import { useState } from 'react';
import type { AcaoDireta, ArcoAtual, MundoPersistente, Progressao } from '../../lib/gameplay';
import { ACOES } from '../../lib/verbos';
import PanelFrame from '../PanelFrame';
import PixelIcon from '../PixelIcon';

// Fase 6 ("uma tela só", ADR-0036) — a aba MISSÃO da ficha vira JORNADA e
// absorve tudo que era "consulta" espalhado pela tela: o capítulo (arco)
// e os conflitos que viviam no painel Mundo Vivo, o objetivo do jogador, os
// fatos descobertos e a trilha de níveis 1–10 que ficava numa aba dentro
// do palco. Especialização 3/7 não vem para cá: LevelUpModal já cobre.
interface Props {
  quest: { nome_missao?: string; objetivo_missao?: string } | null;
  resumoJornada: string | null;
  jornadaAberta: boolean;
  setJornadaAberta: (aberta: boolean) => void;
  arco: ArcoAtual | null;
  mundo: MundoPersistente | null;
  progressao: Progressao | null;
  marcos: string[];
  nivel: number;
  ocupado: boolean;
  combate: boolean;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
}

const ABORDAGENS: { id: string; nome: string }[] = [
  { id: 'atrasar', nome: 'Ganhar tempo' },
  { id: 'apoiar', nome: 'Apoiar a iniciativa' },
  { id: 'resolver', nome: 'Construir um acordo' },
];

function Secao({ titulo, icone, children }: { titulo: string; icone: Parameters<typeof PixelIcon>[0]['name']; children: React.ReactNode }) {
  return (
    <section className="space-y-2">
      <h3 className="text-[10px] text-gray-300 uppercase font-rpg tracking-widest flex items-center gap-2"><PixelIcon name={icone} size={12} /> {titulo}</h3>
      {children}
    </section>
  );
}

const CAMPO = 'w-full bg-black/40 border border-gray-700 px-2 py-1.5 text-xs text-gray-200 font-rpg outline-none focus:border-rpg-gold';
const BOTAO = 'px-2.5 py-1.5 border-2 border-gray-700 bg-black/40 text-xs font-rpg text-gray-200 hover:border-rpg-gold hover:text-rpg-gold disabled:opacity-45 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:border-rpg-gold';
const BOTAO_PRIMARIO = `${BOTAO} border-rpg-gold/70 text-rpg-gold`;

export default function AbaJornada(p: Props) {
  const [objetivo, setObjetivo] = useState('');
  const [conflitoSelecionado, setConflito] = useState('');
  const [abordagem, setAbordagem] = useState('atrasar');
  const [proposta, setProposta] = useState('');

  const conflitos = p.mundo?.conflitos ?? [];
  const ativos = conflitos.filter(c => c.estado === 'ativo');
  const conflito = ativos.find(c => c.id === conflitoSelecionado) ?? ativos[0];
  const bloqueado = p.ocupado || p.combate;

  return (
    <div className="animate-fade-in space-y-5">
      {p.quest?.nome_missao ? (
        <PanelFrame borderWidth={8} className="bg-black/50 p-3">
          <h3 className="text-[10px] text-blue-300 uppercase font-rpg mb-2 tracking-widest flex items-center gap-1"><PixelIcon name="pergaminho" size={11} /> Missão atual</h3>
          <p className="text-base text-blue-100 font-rpg leading-tight mb-2">{p.quest.nome_missao}</p>
          <p className="text-xs text-gray-200 leading-relaxed">{p.quest.objetivo_missao}</p>
        </PanelFrame>
      ) : (
        <p className="text-sm text-gray-400 font-rpg text-center py-4">Nenhuma missão em andamento.</p>
      )}

      {p.arco?.ativo && (
        <Secao titulo="Capítulo atual" icone="estrela">
          <div className="border-2 border-rpg-gold/50 bg-black/50 p-2.5 space-y-1.5" aria-label="Arco atual">
            <p className="font-rpg text-rpg-gold text-base leading-tight">{p.arco.titulo}</p>
            {p.arco.premissa && <p className="text-xs text-gray-300 leading-relaxed">{p.arco.premissa}</p>}
            <p className="text-[11px] text-gray-400 font-rpg">Conflito central: {p.arco.conflito} ({p.arco.estado_conflito}) · {p.arco.turnos} turnos · {p.arco.marcos} fatos registrados</p>
            <p className={`text-[11px] font-rpg ${p.arco.pode_encerrar ? 'text-emerald-300' : 'text-gray-400'}`}>
              {p.arco.pode_encerrar ? 'O servidor confirma: este capítulo pode fechar.' : `Para fechar: ${p.arco.motivo_bloqueio}`}
            </p>
            <div className="flex flex-wrap gap-1.5 pt-1">
              <button type="button" className={BOTAO_PRIMARIO} disabled={bloqueado || !p.arco.pode_encerrar}
                onClick={() => p.aoAgir({ acao: 'encerrar_arco', operacao: 'encerrar' }, `Encerrar o capítulo: ${p.arco?.titulo}`)}>Encerrar capítulo</button>
              <button type="button" className={BOTAO} disabled={bloqueado}
                onClick={() => { if (window.confirm('Abandonar este capítulo? Sem recompensa; o mundo segue.')) p.aoAgir({ acao: 'encerrar_arco', operacao: 'abandonar' }, `Abandonar o capítulo: ${p.arco?.titulo}`); }}>Abandonar</button>
            </div>
          </div>
        </Secao>
      )}

      {p.mundo && (
        <Secao titulo="O mundo continua" icone="alerta">
          {conflitos.length === 0 && <p className="text-xs text-gray-400 font-rpg">Nenhum conflito conhecido neste local.</p>}
          {conflitos.map(c => (
            <article key={c.id} className="border-2 border-gray-700 bg-black/40 p-2 space-y-1">
              <p className="font-rpg text-sm text-gray-100">{c.nome}</p>
              <p className="text-[11px] text-gray-300 leading-snug">{c.estado === 'ativo' ? c.sinal : c.desfecho}</p>
              {c.estado === 'ativo' && (
                <>
                  <progress max={c.etapas} value={c.progresso} className="block w-full h-1.5 [accent-color:#daa64c]" />
                  <span className="block text-[10px] text-gray-400 font-rpg">{c.progresso}/{c.etapas} · próximo avanço em {c.minutos_restantes} min de jogo</span>
                </>
              )}
            </article>
          ))}
          {conflito && (
            <div className="border-2 border-gray-700 bg-black/40 p-2 space-y-1.5">
              <label className="block text-[10px] text-gray-400 font-rpg uppercase tracking-widest">Intervir em
                <select value={conflito.id} onChange={e => setConflito(e.target.value)} className={CAMPO} disabled={p.ocupado}>
                  {ativos.map(c => <option value={c.id} key={c.id}>{c.nome}</option>)}
                </select>
              </label>
              <label className="block text-[10px] text-gray-400 font-rpg uppercase tracking-widest">Como
                <select value={abordagem} onChange={e => setAbordagem(e.target.value)} className={CAMPO} disabled={p.ocupado}>
                  {ABORDAGENS.map(a => <option value={a.id} key={a.id}>{a.nome}</option>)}
                </select>
              </label>
              <label className="block text-[10px] text-gray-400 font-rpg uppercase tracking-widest">Proposta concreta
                <input value={proposta} maxLength={500} onChange={e => setProposta(e.target.value)} className={CAMPO} disabled={p.ocupado} />
              </label>
              <p className="text-[10px] text-gray-500 font-rpg">Um acordo exige cooperação do responsável e duas intervenções bem-sucedidas.</p>
              <button type="button" className={BOTAO_PRIMARIO} disabled={p.ocupado || !proposta.trim()}
                onClick={() => { p.aoAgir({ acao: 'intervir_conflito', alvo: conflito.id, operacao: abordagem, proposta }, `${ABORDAGENS.find(a => a.id === abordagem)?.nome ?? abordagem}: ${conflito.nome}`); setProposta(''); }}>Intervir</button>
            </div>
          )}
        </Secao>
      )}

      {p.mundo && (
        <Secao titulo="Meu objetivo" icone="seta">
          {p.mundo.objetivos.length > 0 && <p className="text-xs text-gray-200 font-rpg">{p.mundo.objetivos[p.mundo.objetivos.length - 1]}</p>}
          <form className="flex gap-1.5" onSubmit={e => { e.preventDefault(); if (objetivo.trim()) { p.aoAgir({ acao: 'definir_objetivo', proposta: objetivo }, `Meu objetivo: ${objetivo}`); setObjetivo(''); } }}>
            <input maxLength={500} value={objetivo} onChange={e => setObjetivo(e.target.value)} placeholder="Você pode mudar de rumo." aria-label="O que você quer fazer agora?" className={CAMPO} />
            <button type="submit" className={BOTAO} disabled={p.ocupado || !objetivo.trim()}>Seguir</button>
          </form>
          <p className="text-[11px] text-gray-400 font-rpg">{p.mundo.aptidao.nome}: +{p.mundo.aptidao.bonus} em {p.mundo.aptidao.acoes.map(a => ACOES[a] ?? a).join(', ')}.</p>
        </Secao>
      )}

      {(p.mundo?.conhecimento.length ?? 0) > 0 && (
        <Secao titulo="O que você descobriu" icone="pergaminho">
          {p.mundo!.conhecimento.slice(-12).reverse().map((f, i) => (
            <p key={`${f.turno}:${i}`} className="border-l-2 border-rpg-gold/60 pl-2 text-[11px] text-gray-300 leading-snug">
              <span className="text-rpg-gold font-rpg">{f.natureza}</span> · {f.texto}
              <span className="block text-[10px] text-gray-500">Fonte: {f.fonte}</span>
            </p>
          ))}
        </Secao>
      )}

      {p.progressao && (
        <Secao titulo={`Jornada 1–${p.progressao.nivel_maximo}`} icone="estrela">
          <p className="text-[11px] text-rpg-gold font-rpg">{p.progressao.estilo || 'Explore, resolva situações e vença encontros para evoluir.'}</p>
          <ol className="space-y-1">
            {p.progressao.niveis.map(etapa => {
              const atual = etapa.nivel === p.nivel;
              const feito = etapa.nivel < p.nivel;
              return (
                <li key={etapa.nivel} aria-current={atual ? 'step' : undefined}
                  className={`flex gap-2 border p-1.5 ${atual ? 'border-rpg-gold bg-rpg-gold/10 text-gray-100' : feito ? 'border-gray-600 text-gray-200' : 'border-gray-800 text-gray-500'}`}>
                  <span className="font-pixel-title text-[10px] min-w-6 text-center pt-0.5 text-rpg-gold/80">{etapa.nivel}</span>
                  <div className="min-w-0">
                    <p className="text-[11px] font-rpg leading-snug">{etapa.descricao}</p>
                    <p className="text-[10px] text-gray-500">{etapa.xp} XP{atual ? ' · Você está aqui' : feito ? ' · Conquistado' : ''}</p>
                  </div>
                </li>
              );
            })}
          </ol>
        </Secao>
      )}

      {p.marcos.length > 0 && (
        <Secao titulo="As marcas da sua história" icone="estrela">
          {p.marcos.map((marco, i) => <p key={`${i}-${marco}`} className="text-[11px] text-gray-300 flex gap-1.5"><PixelIcon name="estrela" size={11} />{marco}</p>)}
        </Secao>
      )}

      {p.resumoJornada && (
        <div className="border-2 border-gray-700 bg-black/40">
          <button type="button" onClick={() => p.setJornadaAberta(!p.jornadaAberta)} aria-expanded={p.jornadaAberta} aria-controls="jornada-ate-aqui"
            className="w-full flex items-center justify-between gap-2 px-2.5 py-2 text-[10px] uppercase tracking-widest font-rpg text-gray-300 hover:text-rpg-gold transition-colors">
            <span>A Jornada Até Aqui</span>
            <PixelIcon name="seta" size={10} className={`transition-transform ${p.jornadaAberta ? 'rotate-90' : ''}`} />
          </button>
          {p.jornadaAberta && <p id="jornada-ate-aqui" className="px-2.5 pb-2.5 text-xs text-gray-400 leading-relaxed italic animate-fade-in">{p.resumoJornada}</p>}
        </div>
      )}
    </div>
  );
}
