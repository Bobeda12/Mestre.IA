import { useEffect, useRef, useState } from 'react';
import type { AcaoDireta, Cena, EntidadeMundo, ItemInfo, PessoaMundo, Progressao, Selecao } from '../../lib/gameplay';
import { ACEITAM_MEIO, ACOES, ICONE_INTERACAO, SOCIAIS, TATICAS, verbosPara } from '../../lib/verbos';
import { categoriaDe } from '../InventoryGrid';
import PixelIcon, { type PixelIconName } from '../PixelIcon';
import PixelActionCard from '../PixelActionCard';

// Fase 6 ("uma tela só", ADR-0036) — UMA barra de ação, colada ao campo de
// texto, que muda com o contexto:
//   • combate: Atacar / Defender / Técnicas / Táticas / Cena / Itens;
//   • exploração com algo selecionado no palco: os verbos do alvo;
//   • exploração sem seleção: sugestões do narrador ([OPCOES]) + Descansar.
// Verbos sociais (negociar, ajudar…) usam o PRÓPRIO campo de texto como
// proposta. O texto livre continua sempre disponível — os botões são o
// atalho, não a troca do chat por um menu.
interface Props {
  combate: boolean;
  caido: boolean;
  ocupado: boolean;
  encerrado: boolean;
  loading: boolean;
  alvo: string | undefined;
  selecao: Selecao | null;
  pessoaSelecionada: PessoaMundo | undefined;
  entidadeSelecionada: EntidadeMundo | undefined;
  cena: Cena | null;
  progressao: Progressao | null;
  nivel: number;
  inventory: string[];
  catalogoItens: Record<string, ItemInfo>;
  entidades: EntidadeMundo[];
  opcoes: string[];
  erro: string | null;
  input: string;
  setInput: (texto: string) => void;
  handleSendMessage: () => void;
  handleKeyDown: (e: React.KeyboardEvent) => void;
  aoAgir: (acao: AcaoDireta, rotulo: string) => void;
  onAbrirBalcao: (id: string) => void;
  onLimparSelecao: () => void;
}

type Popover = 'tecnicas' | 'taticas' | 'cena' | 'itens' | null;

const BOTAO = 'dock__btn font-rpg';
const ICONE_VERBO: Record<string, PixelIconName> = {
  examinar: 'pergaminho', investigar: 'pergaminho', conversar: 'rosto', negociar: 'moeda', ajudar: 'cura', intimidar: 'alerta',
  distrair: 'rosto', acalmar: 'rosto', atravessar: 'seta', abrir: 'bau', destrancar: 'bau', pegar: 'mochila', quebrar: 'machado',
  acender: 'pocao-vermelha', apagar: 'pocao-azul', mover: 'seta', bloquear: 'escudo', desbloquear: 'escudo', ocultar: 'adaga',
};

export default function DockAcoes(p: Props) {
  const [popover, setPopover] = useState<Popover>(null);
  const [meio, setMeio] = useState('');
  const [verboPendente, setVerboPendente] = useState<{ alvoId: string; alvoNome: string; operacao: string } | null>(null);
  const raiz = useRef<HTMLDivElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);

  const bloqueado = p.ocupado || p.encerrado;
  const alvoSel = p.pessoaSelecionada ?? p.entidadeSelecionada;
  const nomeSel = alvoSel?.nome ?? (p.selecao?.tipo === 'inimigo' ? p.selecao.id : null);
  const foco = p.progressao?.recurso;

  // Trocar de seleção ou entrar em combate limpa popover, meio e proposta.
  // Ajuste de estado durante o render (padrão recomendado pelo React para
  // "resetar estado quando uma prop muda"), em vez de um useEffect com
  // setState síncrono no corpo.
  const chaveSelecao = `${p.selecao?.tipo ?? ''}:${p.selecao?.id ?? ''}:${p.combate}`;
  const [chaveAnterior, setChaveAnterior] = useState(chaveSelecao);
  if (chaveSelecao !== chaveAnterior) {
    setChaveAnterior(chaveSelecao);
    setPopover(null);
    setMeio('');
    setVerboPendente(null);
  }
  useEffect(() => {
    const fora = (e: MouseEvent) => { if (raiz.current && !raiz.current.contains(e.target as Node)) setPopover(null); };
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape') { setPopover(null); setVerboPendente(null); } };
    document.addEventListener('mousedown', fora); document.addEventListener('keydown', esc);
    return () => { document.removeEventListener('mousedown', fora); document.removeEventListener('keydown', esc); };
  }, []);

  const agirNoMundo = (operacao: string, proposta?: string) => {
    if (!alvoSel) return;
    p.aoAgir({ acao: 'agir_no_mundo', alvo: alvoSel.id, operacao, meio: meio || undefined, proposta }, `${ACOES[operacao] ?? operacao}: ${alvoSel.nome}`);
  };
  const clicarVerbo = (operacao: string) => {
    if (!alvoSel) return;
    if (SOCIAIS.includes(operacao) && p.pessoaSelecionada) {
      setVerboPendente({ alvoId: alvoSel.id, alvoNome: alvoSel.nome, operacao });
      textarea.current?.focus();
      return;
    }
    agirNoMundo(operacao);
  };
  const enviar = () => {
    if (verboPendente) {
      if (!p.input.trim()) return;
      agirNoMundo(verboPendente.operacao, p.input.trim());
      p.setInput('');
      setVerboPendente(null);
      return;
    }
    p.handleSendMessage();
  };
  const teclado = (e: React.KeyboardEvent) => {
    if (verboPendente) { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); enviar(); } return; }
    p.handleKeyDown(e);
  };
  const alternarPopover = (qual: Popover) => setPopover(atual => atual === qual ? null : qual);

  const verbos = alvoSel ? verbosPara(alvoSel) : [];
  const meios = [
    ...p.entidades.filter(e => e.propriedades.includes('movel') && e.id !== alvoSel?.id && !['movido', 'destruido'].includes(e.estado)).map(e => ({ id: e.id, nome: e.nome })),
    ...[...new Set(p.inventory)].map(item => ({ id: item, nome: item })),
  ];
  const mostraMeio = !!alvoSel && verbos.some(v => ACEITAM_MEIO.includes(v)) && meios.length > 0;
  const consumiveis = [...new Set(p.inventory)].filter(item => categoriaDe(item, p.catalogoItens[item]).rotulo === 'Consumível');
  const outrosItens = [...new Set(p.inventory)].filter(item => !consumiveis.includes(item));
  const habilidades = p.progressao?.habilidades ?? [];
  const interacoes = p.cena?.interacoes ?? [];

  const placeholder = verboPendente
    ? `${ACOES[verboPendente.operacao]} com ${verboPendente.alvoNome}: o que você propõe?`
    : p.combate ? "Ameaça iminente! (Ex: 'Ataco o inimigo', 'Fujo')" : 'Sua ação...';

  const hint = p.encerrado ? 'Esta jornada chegou ao fim.'
    : p.caido && p.combate ? 'Você está caído. Resista para avançar a rodada e fazer seu teste de morte.'
    : p.caido ? 'Você está caído. Descanse ou peça ajuda ao Mestre.'
    : p.combate && !p.alvo ? 'Clique numa criatura no palco para escolher o alvo.'
    : null;

  return (
    <div ref={raiz} className="dock shrink-0 relative z-10 border-t border-gray-800/60 bg-gray-900 px-3 py-2 md:px-4">
      {p.erro && <p className="dock__error font-rpg" role="alert">{p.erro}</p>}
      {hint && <p className="dock__hint font-rpg">{hint}</p>}

      {/* Popovers: um por vez, abrem acima da barra. */}
      {popover === 'tecnicas' && (
        <div className="dock__popover" role="group" aria-label="Técnicas">
          {habilidades.length === 0 && <p className="dock__hint font-rpg">Nenhuma técnica ainda.</p>}
          {habilidades.map(h => {
            const trancada = h.nivel > p.nivel;
            const semFoco = (foco?.atual ?? 0) < h.custo;
            const motivo = trancada ? `Desbloqueia no nível ${h.nivel}` : semFoco ? 'Foco insuficiente' : h.alvo === 'todos' ? 'Todos os inimigos' : h.alvo === 'heroi' ? 'Seu herói' : `Alvo: ${p.alvo ?? 'selecione um inimigo'}`;
            return (
              <button type="button" key={h.id} className={`dock__card ${trancada ? 'is-locked' : ''}`}
                disabled={bloqueado || p.caido || !h.disponivel || (h.alvo === 'inimigo' && !p.alvo)}
                onClick={() => { p.aoAgir({ acao: 'usar_habilidade', habilidade: h.id, ...(h.alvo === 'inimigo' ? { alvo: p.alvo } : {}) }, `${h.nome}${h.alvo === 'inimigo' ? ` em ${p.alvo}` : ''}`); setPopover(null); }}>
                <span className="dock__card-head font-rpg uppercase tracking-wide"><strong>{h.nome}</strong><span>{h.custo} {foco?.nome ?? 'Foco'}</span></span>
                <span className="dock__card-body font-rpg">{h.descricao}</span>
                <small className="font-rpg">{motivo}</small>
              </button>
            );
          })}
        </div>
      )}
      {popover === 'taticas' && (
        <div className="dock__popover" role="group" aria-label="Táticas">
          {TATICAS.map(t => (
            <button type="button" key={t.acao} className="dock__card" title={t.dica}
              disabled={bloqueado || p.caido || (t.acao === 'investir' && !p.alvo)}
              onClick={() => { p.aoAgir({ acao: t.acao, ...(t.acao === 'investir' ? { alvo: p.alvo } : {}) }, t.nome); setPopover(null); }}>
              <span className="dock__card-head font-rpg uppercase tracking-wide"><PixelIcon name={t.icone} size={14} /><strong>{t.nome}</strong></span>
              <span className="dock__card-body font-rpg">{t.dica}</span>
            </button>
          ))}
        </div>
      )}
      {popover === 'cena' && (
        <div className="dock__popover" role="group" aria-label="Interações do cenário">
          {interacoes.map(i => (
            <button type="button" key={i.id} className="dock__card" disabled={bloqueado || p.caido}
              onClick={() => { p.aoAgir({ acao: 'interagir', interacao: i.id }, i.nome); setPopover(null); }}>
              <span className="dock__card-head font-rpg uppercase tracking-wide"><PixelIcon name={ICONE_INTERACAO[i.id] ?? 'bau'} size={14} /><strong>{i.nome}</strong></span>
              <span className="dock__card-body font-rpg">{i.descricao}</span>
            </button>
          ))}
        </div>
      )}
      {popover === 'itens' && (
        <div className="dock__popover" role="group" aria-label="Itens">
          {p.inventory.length === 0 && <p className="dock__hint font-rpg">Mochila vazia.</p>}
          {consumiveis.map(item => (
            <button type="button" key={`c:${item}`} className="dock__card" disabled={bloqueado || p.caido} title={p.catalogoItens[item]?.descricao}
              onClick={() => { p.aoAgir({ acao: 'usar_item', item }, `Usar ${item}`); setPopover(null); }}>
              <span className="dock__card-head font-rpg uppercase tracking-wide"><PixelIcon name={categoriaDe(item, p.catalogoItens[item]).icone} size={14} /><strong>{item}</strong></span>
              <span className="dock__card-body font-rpg">{p.catalogoItens[item]?.descricao ?? 'Usar agora.'}</span>
            </button>
          ))}
          {outrosItens.map(item => (
            <button type="button" key={`o:${item}`} className="dock__card" disabled={bloqueado} title="Cita o item na sua ação"
              onClick={() => { p.setInput(`${p.input}${p.input && !p.input.endsWith(' ') ? ' ' : ''}[${item}] `); setPopover(null); textarea.current?.focus(); }}>
              <span className="dock__card-head font-rpg uppercase tracking-wide"><PixelIcon name={categoriaDe(item, p.catalogoItens[item]).icone} size={14} /><strong>{item}</strong></span>
              <span className="dock__card-body font-rpg">Citar na ação</span>
            </button>
          ))}
        </div>
      )}

      {/* Item 9 — verbos e campo de texto agora leem como UMA peça
          (`.dock__panel`), não duas caixas empilhadas com bordas diferentes. */}
      <div className="dock__panel">
      {/* Linha 1 — os verbos do contexto. */}
      <div className="dock__row" role="toolbar" aria-label="Ações">
        {nomeSel && !p.combate && (
          <span className="dock__chip font-rpg">
            <PixelIcon name={p.pessoaSelecionada ? 'rosto' : 'bau'} size={12} /> {nomeSel}
            <button type="button" onClick={p.onLimparSelecao} aria-label="Limpar seleção" className="ml-1 opacity-70 hover:opacity-100">×</button>
          </span>
        )}

        {p.combate ? (
          <>
            <button type="button" className={`${BOTAO} dock__btn--primary`} disabled={bloqueado || p.caido || !p.alvo}
              onClick={() => p.aoAgir({ acao: 'atacar', alvo: p.alvo }, `Atacar ${p.alvo}`)}>
              <PixelIcon name="espada" size={16} /> Atacar{p.alvo ? ` ${p.alvo}` : ''}
            </button>
            <button type="button" className={BOTAO} disabled={bloqueado}
              onClick={() => p.aoAgir({ acao: p.caido ? 'resistir' : 'defender' }, p.caido ? 'Resistir e avançar a rodada' : 'Defender')}>
              <PixelIcon name="escudo" size={16} /> {p.caido ? 'Resistir' : 'Defender'}
            </button>
            {habilidades.length > 0 && (
              <button type="button" className={BOTAO} aria-expanded={popover === 'tecnicas'} disabled={p.caido} onClick={() => alternarPopover('tecnicas')}>
                <PixelIcon name="pocao-azul" size={16} /> Técnicas{foco && <small>{foco.atual}/{foco.maximo}</small>} ▾
              </button>
            )}
            <button type="button" className={BOTAO} aria-expanded={popover === 'taticas'} disabled={p.caido} onClick={() => alternarPopover('taticas')}>
              <PixelIcon name="dado" size={16} /> Táticas ▾
            </button>
            {interacoes.length > 0 && (
              <button type="button" className={BOTAO} aria-expanded={popover === 'cena'} disabled={p.caido} onClick={() => alternarPopover('cena')}>
                <PixelIcon name="bau" size={16} /> Cena ▾
              </button>
            )}
            <button type="button" className={BOTAO} aria-expanded={popover === 'itens'} onClick={() => alternarPopover('itens')}>
              <PixelIcon name="mochila" size={16} /> Itens ▾
            </button>
          </>
        ) : alvoSel ? (
          <>
            {verbos.map(v => (
              <button type="button" key={v} className={`${BOTAO} ${verboPendente?.operacao === v ? 'is-active' : ''}`}
                disabled={bloqueado || p.caido || (v === 'bloquear' && !meio)}
                title={v === 'bloquear' && !meio ? 'Escolha com o quê em "Com…"' : undefined}
                onClick={() => clicarVerbo(v)}>
                <PixelIcon name={ICONE_VERBO[v] ?? 'seta'} size={14} /> {ACOES[v] ?? v}
              </button>
            ))}
            {p.pessoaSelecionada && (p.pessoaSelecionada.vitrine?.length ?? 0) > 0 && (
              <button type="button" className={`${BOTAO} dock__btn--primary`} disabled={bloqueado}
                onClick={() => p.onAbrirBalcao(p.pessoaSelecionada!.id)}>
                <PixelIcon name="moeda" size={14} /> Comerciar
              </button>
            )}
            {mostraMeio && (
              <label className="dock__meio font-rpg">Com
                <select value={meio} onChange={e => setMeio(e.target.value)} disabled={bloqueado} aria-label="Usar ou oferecer">
                  <option value="">nada</option>
                  {meios.map(m => <option key={m.id} value={m.id}>{m.nome}</option>)}
                </select>
              </label>
            )}
          </>
        ) : (
          <>
            {p.opcoes.length > 0 && !p.loading && !p.encerrado && p.opcoes.map((op, i) => (
              <PixelActionCard key={i} onClick={() => { p.setInput(op); textarea.current?.focus(); }} className="text-xs md:text-sm px-3 py-2">{op}</PixelActionCard>
            ))}
            {!p.encerrado && (
              <button type="button" className={`${BOTAO} ml-auto`} disabled={bloqueado || p.caido}
                onClick={() => p.aoAgir({ acao: 'descansar' }, 'Fazer um descanso curto')}>
                <PixelIcon name="cura" size={14} /> Descansar
              </button>
            )}
          </>
        )}
      </div>

      {/* Linha 2 — texto livre (ou a proposta do verbo social pendente).
          Sem borda própria: a moldura já é a do `.dock__panel` em volta; só
          uma linha divisória fina separa isto da fileira de verbos acima. */}
      <div className={`flex gap-2 p-1.5 border-t transition-colors ${verboPendente ? 'border-rpg-gold' : 'border-[#3a3626] focus-within:border-rpg-gold/60'}`}>
        {verboPendente && (
          <button type="button" onClick={() => setVerboPendente(null)} aria-label="Cancelar proposta" className="self-center shrink-0 text-[10px] font-rpg uppercase tracking-widest text-rpg-gold px-2 py-1 border border-rpg-gold/50 hover:bg-rpg-gold/10">
            {ACOES[verboPendente.operacao]} ×
          </button>
        )}
        <textarea
          ref={textarea}
          value={p.input}
          onChange={(e) => p.setInput(e.target.value)}
          onKeyDown={teclado}
          placeholder={placeholder}
          aria-label="Sua ação"
          disabled={p.encerrado || p.ocupado}
          className="flex-1 bg-transparent text-gray-200 p-3 outline-none resize-none h-12 max-h-32 custom-scrollbar font-rpg text-sm placeholder-gray-500 disabled:opacity-50"
        />
        <button
          onClick={enviar}
          disabled={p.loading || !p.input.trim() || p.encerrado || p.ocupado}
          aria-label="Enviar ação"
          className="h-10 w-10 bg-gray-800 hover:bg-gray-700 text-rpg-gold flex items-center justify-center transition-all mt-1 mr-1 border border-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold disabled:opacity-40"
        >
          <PixelIcon name="enviar" size={18} />
        </button>
      </div>
      </div>
    </div>
  );
}
