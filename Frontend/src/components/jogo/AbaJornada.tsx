import { useState } from 'react';
import type { AcaoDireta, Capitulo, PassoTrilha } from '../../lib/gameplay';
import PanelFrame from '../PanelFrame';
import PixelIcon from '../PixelIcon';

// Trilha do capítulo (ADR-0039) — a aba responde a três perguntas, nesta
// ordem: o que eu quero, onde estou neste capítulo, o que já ficou para
// trás. Os painéis de projetos, lugares, abastecimento, organizações e
// conflitos saíram da tela; esses sistemas seguem no servidor e o jogador
// mexe neles conversando com o mestre.
interface Props {
  capitulo: Capitulo | null;
  ocupado: boolean;
  combate: boolean;
  erro: string | null;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
}

const RESULTADO: Record<string, string> = {
  acordo: 'acordo', consequencia: 'consequências', vitoria_chefe: 'vitória', abandono: 'abandonado',
};

const TITULO = 'text-[10px] uppercase font-rpg tracking-widest flex items-center gap-1.5';
const CAMPO = 'w-full bg-black/40 border border-gray-700 px-2 py-1.5 text-xs text-gray-200 font-rpg outline-none focus:border-rpg-gold';
const BOTAO = 'px-2.5 py-1.5 border-2 border-gray-700 bg-black/40 text-xs font-rpg text-gray-200 hover:border-rpg-gold hover:text-rpg-gold disabled:opacity-45 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:border-rpg-gold';
const BOTAO_PRIMARIO = `${BOTAO} border-rpg-gold/70 text-rpg-gold`;
const LINK = 'text-[11px] font-rpg text-gray-400 underline underline-offset-2 hover:text-rpg-gold disabled:opacity-45 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:text-rpg-gold';

const MARCA: Record<PassoTrilha['estado'] | 'oculto', { sinal: string; cor: string; rotulo: string }> = {
  feito: { sinal: '✔', cor: 'text-emerald-300', rotulo: 'Cumprido' },
  atual: { sinal: '▶', cor: 'text-rpg-gold', rotulo: 'Passo atual' },
  pulado: { sinal: '–', cor: 'text-gray-500', rotulo: 'Deixado para trás' },
  oculto: { sinal: '○', cor: 'text-gray-600', rotulo: 'Ainda por vir' },
};

function Marca({ tipo }: { tipo: keyof typeof MARCA }) {
  const m = MARCA[tipo];
  return <span className={`w-4 shrink-0 text-center text-xs leading-5 ${m.cor}`} role="img" aria-label={m.rotulo}>{m.sinal}</span>;
}

export default function AbaJornada(p: Props) {
  const [mudando, setMudando] = useState(false);
  const [rumo, setRumo] = useState('');
  const c = p.capitulo;
  const bloqueado = p.ocupado || p.combate;
  const passos = c?.passos ?? [];
  // Só o passo atual existe no servidor; o "???" é o lembrete de que a
  // história continua. Some quando o que resta é fechar o capítulo.
  const haMais = !!c?.ativo && !c.pode_encerrar && passos.some(x => x.estado === 'atual');
  const passado = [...(c?.marcos ?? [])].reverse();
  const anteriores = [...(c?.anteriores ?? [])].reverse();

  return (
    <div className="animate-fade-in space-y-5">
      {/* No celular a ficha é uma gaveta que cobre o chat: o erro e o
          status de uma ação daqui precisam aparecer aqui também. */}
      {p.erro && <p className="text-xs text-red-300 border-2 border-red-900/60 bg-red-950/40 p-2" role="alert">{p.erro}</p>}
      {p.ocupado && <p className="text-[11px] text-gray-400 font-rpg" role="status" aria-live="polite">Resolvendo sua ação…</p>}

      <PanelFrame borderWidth={8} className="bg-black/50 p-3">
        <h3 className={`${TITULO} text-blue-300 mb-2`}><PixelIcon name="seta" size={11} /> Seu objetivo agora</h3>
        {c?.objetivo
          ? <p className="text-base text-blue-100 font-rpg leading-snug">{c.objetivo}</p>
          : <p className="text-sm text-gray-400 font-rpg">Nenhum objetivo definido ainda.</p>}
        {c && !mudando && (
          <button type="button" className={`${LINK} mt-2`} disabled={p.ocupado} onClick={() => setMudando(true)}>Mudar de rumo</button>
        )}
        {c && mudando && (
          <form className="flex gap-1.5 mt-2" onSubmit={e => {
            e.preventDefault();
            if (!rumo.trim()) return;
            p.aoAgir({ acao: 'definir_objetivo', proposta: rumo }, `Meu objetivo: ${rumo}`);
            setRumo('');
            setMudando(false);
          }}>
            <input autoFocus maxLength={500} value={rumo} onChange={e => setRumo(e.target.value)} aria-label="Novo objetivo"
              placeholder="O que você quer agora?" className={CAMPO} />
            <button type="submit" className={BOTAO} disabled={p.ocupado || !rumo.trim()}>Seguir</button>
          </form>
        )}
      </PanelFrame>

      {c?.ativo ? (
        <section className="space-y-2.5" aria-label="Capítulo atual">
          <h3 className="font-rpg text-rpg-gold text-base leading-tight">Capítulo {c.numero} · {c.titulo}</h3>
          {c.premissa && <p className="text-xs text-gray-400 leading-relaxed line-clamp-3">{c.premissa}</p>}
          <ol className="space-y-2" aria-label="Passos do capítulo">
            {passos.map((passo, i) => (
              <li key={i} aria-current={passo.estado === 'atual' ? 'step' : undefined}
                className={`flex gap-2 ${passo.estado === 'atual' ? 'border-l-2 border-rpg-gold bg-rpg-gold/5 -ml-2 pl-1.5 py-1.5 pr-1.5' : ''}`}>
                <Marca tipo={passo.estado} />
                <div className="min-w-0">
                  <p className={`font-rpg leading-snug ${passo.estado === 'atual' ? 'text-sm text-gray-100'
                    : passo.estado === 'feito' ? 'text-xs text-gray-300' : 'text-xs text-gray-500 line-through'}`}>{passo.texto}</p>
                  {passo.evidencia && <p className="text-[11px] text-gray-500 leading-snug">{passo.evidencia}</p>}
                </div>
              </li>
            ))}
            {haMais && <li className="flex gap-2"><Marca tipo="oculto" /><p className="text-xs text-gray-600 font-rpg tracking-widest">???</p></li>}
          </ol>
          {/* O que falta para fechar não aparece como lista de regras: o
              passo atual já diz o que fazer agora. */}
          {c.pode_encerrar && <p className="text-[11px] font-rpg text-emerald-300">Este capítulo pode fechar.</p>}
          <div className="flex flex-wrap items-center gap-3">
            {c.pode_encerrar && (
              <button type="button" className={BOTAO_PRIMARIO} disabled={bloqueado}
                onClick={() => p.aoAgir({ acao: 'encerrar_arco', operacao: 'encerrar' }, `Encerrar o capítulo: ${c.titulo}`)}>Encerrar capítulo</button>
            )}
            <button type="button" className={LINK} disabled={bloqueado}
              onClick={() => { if (window.confirm('Abandonar este capítulo? Sem recompensa; o mundo segue.')) p.aoAgir({ acao: 'encerrar_arco', operacao: 'abandonar' }, `Abandonar o capítulo: ${c.titulo}`); }}>Abandonar</button>
          </div>
        </section>
      ) : c && (
        <p className="text-xs text-gray-400 font-rpg leading-relaxed">Nenhum capítulo aberto. O mundo segue; um novo começa quando algo pedir peso de história.</p>
      )}

      {(passado.length > 0 || anteriores.length > 0) && (
        <section className="space-y-2">
          <h3 className={`${TITULO} text-gray-400`}><PixelIcon name="pergaminho" size={12} /> O que ficou para trás</h3>
          <ul className="space-y-1.5" aria-label="O que ficou para trás">
            {passado.map((marco, i) => (
              <li key={`m${i}`} className="text-[11px] text-gray-300 leading-snug border-l-2 border-gray-700 pl-2">{marco}</li>
            ))}
            {anteriores.map(a => (
              <li key={`c${a.numero}`} className="text-[11px] text-rpg-gold/80 font-rpg leading-snug border-l-2 border-rpg-gold/40 pl-2">
                Capítulo {a.numero} · {a.titulo} ({RESULTADO[a.resultado] ?? a.resultado})
              </li>
            ))}
          </ul>
        </section>
      )}
    </div>
  );
}
