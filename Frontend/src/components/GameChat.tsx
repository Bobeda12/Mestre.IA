import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api, API_URL } from '../lib/api';
import { postSse } from '../lib/sse';
import { getLocalImage, limparMarkdownLeve } from '../lib/utils';
import { useAuth, useInvalidarAuth } from '../lib/auth';
import { useTrilha, calcularTema } from '../lib/trilha';
import RollCard, { type DadosRolagem } from './RollCard';
import StatusCard, { type EventoStatus } from './StatusCard';
import PixelBar from './PixelBar';
import Prologo from './Prologo';
import PixelIcon, { type PixelIconName } from './PixelIcon';
import PanelFrame from './PanelFrame';
import PixelButton from './PixelButton';
import InventoryGrid from './InventoryGrid';
import Carregando from './Carregando';
import RetratoPixelado from './RetratoPixelado';
import MenuConfiguracao from './MenuConfiguracao';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

// Etapa 14 (revisão) — a ficha virou menu de abas estilo JRPG. Antes tudo
// (retrato, barras, atributos, missão, inventário) era uma pilha só numa
// coluna de 320px: ficava espremido e obrigava a rolar pra achar qualquer
// coisa. Três telas curtas leem melhor e é o vocabulário de menu de console.
const ABAS = [
  { id: 'status', rotulo: 'STATUS', icone: 'coracao' },
  { id: 'itens', rotulo: 'ITENS', icone: 'mochila' },
  { id: 'missao', rotulo: 'MISSÃO', icone: 'pergaminho' },
] as const satisfies readonly { id: string; rotulo: string; icone: PixelIconName }[];

type AbaFicha = (typeof ABAS)[number]['id'];

// Ordem e siglas dos atributos, na mesma sequência da ficha de criação.
const ATRIBUTOS = [
  ['forca', 'FOR'], ['destreza', 'DES'], ['constituicao', 'CON'],
  ['inteligencia', 'INT'], ['sabedoria', 'SAB'], ['carisma', 'CAR'],
] as const;

type Message =
  // `turnoIndex` (Etapa 9) chega no frame SSE "state", junto do resto do
  // HUD — é a posição desta narração em `historico_chat` no servidor
  // (Personagem.historico_chat), o que o botão 👍/👎 manda pra
  // POST /personagens/:id/feedback. `feedback` é só o que ESTE navegador já
  // votou, pra não deixar votar duas vezes na mesma aba.
  | { kind: 'texto'; role: 'user' | 'assistant' | 'system'; content: string; isError?: boolean; turnoIndex?: number; feedback?: 1 | -1 }
  // Etapa 10 (A-7): cura e morte de inimigo chegam pelo mesmo frame
  // `tool_event` que ataque/teste, só com um `dados.tipo` diferente.
  | { kind: 'rolagem'; dados: DadosRolagem | EventoStatus };

// Espelha domain/state.py:Inimigo (só os campos que o HUD lê).
interface Inimigo {
  nome: string;
  hp: number;
  max_hp: number;
  ca: number;
}

// O frame SSE final "state" (Etapa 7) — mesmo shape de `_resposta()` no
// backend (Backend/app/routers/game.py) — e também o corpo de `/load_game`
// (que reaproveita `_resposta()` do lado do servidor, ver routers/game.py).
interface EstadoJogo {
  hp_atual: number;
  hp_max?: number;
  defesa?: number;
  ouro?: number;
  nivel?: number;
  xp?: number;
  xp_proximo_nivel?: number | null;
  ordem_iniciativa?: number[];
  turno_atual?: number;
  inventory?: string[];
  combat_active: boolean;
  inimigos?: Inimigo[];
  missao?: unknown;
  turno_index?: number;
  // Etapa 11 (B-6) — turno do MUNDO (world_state.turno), não o turno da
  // rodada de combate (`turno_atual`, que reseta a cada luta): é o que a
  // tela de morte usa pra mostrar "quantos turnos você viveu".
  turno_mundo?: number;
}

interface CargaJogo extends EstadoJogo {
  nome: string;
  raca: string;
  classe: string;
  local: string;
  atributos?: Record<string, number>;
  imagem?: string | null;
  // Etapa 11 (B-7) — tela de abertura da campanha.
  clima?: string | null;
  background?: string | null;
  objetivo?: string | null;
  historia_texto?: string | null;
  historico_chat?: { role: string; content: string }[];
}

export default function GameChat() {
  const location = useLocation();
  const navigate = useNavigate();
  // A sessão vive na URL (/jogar/:sessionId) — não em estado do React nem
  // só no localStorage. Recarregar a página não perde mais o personagem.
  const { sessionId } = useParams<{ sessionId: string }>();
  const { charImage: charImageFromNav } = location.state || {};

  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [showSidebar, setShowSidebar] = useState(true);
  const [abaAtiva, setAbaAtiva] = useState<AbaFicha>('status');
  const [retratoAberto, setRetratoAberto] = useState(false);
  const [configAberta, setConfigAberta] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // FICHA — sempre a verdade que vem do backend (load_game / chat)
  const [charName, setCharName] = useState("");
  const [charRace, setCharRace] = useState("");
  const [charClass, setCharClass] = useState("");
  const [charImage, setCharImage] = useState(charImageFromNav || "");
  const [hpAtual, setHpAtual] = useState(10);
  const [hpMax, setHpMax] = useState(10);
  const [defesa, setDefesa] = useState<number | null>(null);
  const [ouro, setOuro] = useState(0);
  const [nivel, setNivel] = useState(1);
  const [xp, setXp] = useState(0);
  const [xpProximoNivel, setXpProximoNivel] = useState<number | null>(null);
  const [inventory, setInventory] = useState<string[]>([]);
  const [attributes, setAttributes] = useState<any>({ forca: 10, destreza: 10, inteligencia: 10 });
  const [quest, setQuest] = useState<any>(null);

  // COMBATE
  const [combatActive, setCombatActive] = useState(false);
  const [enemies, setEnemies] = useState<Inimigo[]>([]);
  const [ordemIniciativa, setOrdemIniciativa] = useState<number[]>([]);
  const [turnoAtual, setTurnoAtual] = useState(0);
  const [turnoMundo, setTurnoMundo] = useState(0);
  const [gameOver, setGameOver] = useState(false);
  // Etapa 11 (B-7) — a tela de abertura aparece só na primeira visita
  // (historico_chat ainda com só o prólogo, nenhum turno jogado) e some
  // pro resto da sessão assim que o jogador clica "Começar" — não volta a
  // cada re-render, só se a página for recarregada antes do 1º turno.
  const [prologoConcluido, setPrologoConcluido] = useState(false);
  // Dano flutuante (Etapa 7) — `idx` é a posição no array `enemies`, não o
  // nome (dois inimigos podem ter o mesmo nome).
  const [danosFlutuantes, setDanosFlutuantes] = useState<{ id: number; valor: number; idx: number }[]>([]);

  // EFEITOS
  const [shakeScreen, setShakeScreen] = useState(false);
  const [wasDamaged, setWasDamaged] = useState(false);

  // CONVITE PRA REIVINDICAR (Etapa 10, A-1) — só aparece pra convidado
  // (`usuario.email === null`), depois do primeiro momento bom: o primeiro
  // combate resolvido sem morrer, ou 8 turnos jogados (proxy pro "fim da
  // primeira cena"), o que vier primeiro. `combateFoiAtivoRef` é o que
  // permite detectar "combate que acabou" sem um campo de vitória dedicado
  // no backend — combatActive true → false, sem game over, é a transição.
  const { usuario } = useAuth();
  const invalidarAuth = useInvalidarAuth();
  const ehConvidado = usuario !== null && usuario.email === null;
  const combateFoiAtivoRef = useRef(false);
  const [primeiroCombateResolvido, setPrimeiroCombateResolvido] = useState(false);
  const [conviteDispensado, setConviteDispensado] = useState(
    () => sessionStorage.getItem('mestre_ia_convite_reivindicar_dispensado') === '1'
  );
  const [modalReivindicarAberto, setModalReivindicarAberto] = useState(false);
  const [reivindicarEmail, setReivindicarEmail] = useState('');
  const [reivindicarSenha, setReivindicarSenha] = useState('');
  const [reivindicarErro, setReivindicarErro] = useState<string | null>(null);
  const [reivindicarEnviando, setReivindicarEnviando] = useState(false);

  useEffect(() => {
    if (combatActive) combateFoiAtivoRef.current = true;
    else if (combateFoiAtivoRef.current && !gameOver) setPrimeiroCombateResolvido(true);
  }, [combatActive, gameOver]);

  // Etapa 11 (B-4) — trilha por tema. O tema é derivado do estado (combate,
  // HP baixo, game over), nunca pedido ao modelo.
  const temaMusical = calcularTema({ gameOver, combateAtivo: combatActive, hpAtual, hpMax });
  const trilha = useTrilha(temaMusical);

  const maiorTurnoIndex = messages.reduce(
    (max, m) => (m.kind === 'texto' && m.turnoIndex !== undefined ? Math.max(max, m.turnoIndex) : max),
    -1
  );
  const mostrarConviteReivindicar =
    ehConvidado && !conviteDispensado && !gameOver && (primeiroCombateResolvido || maiorTurnoIndex >= 8);

  const dispensarConvite = () => {
    setConviteDispensado(true);
    sessionStorage.setItem('mestre_ia_convite_reivindicar_dispensado', '1');
  };

  const reivindicar = async (e: React.FormEvent) => {
    e.preventDefault();
    setReivindicarEnviando(true);
    setReivindicarErro(null);
    try {
      await api.post('/auth/reivindicar', { email: reivindicarEmail, senha: reivindicarSenha });
      invalidarAuth();
      setModalReivindicarAberto(false);
      dispensarConvite();
    } catch (err) {
      const detalhe = isAxiosError<{ detail?: string }>(err) ? err.response?.data?.detail : undefined;
      setReivindicarErro(detalhe ?? 'Não deu para criar a conta. Confira o e-mail e a senha.');
    } finally {
      setReivindicarEnviando(false);
    }
  };

  // Etapa 7, ADR-0013: TanStack Query no lugar do `useEffect` +
  // `try/catch` + `setNotFound` escritos à mão — a troca real não é
  // estética, é ganhar de graça o cache por `sessionId` (voltar duas telas
  // e voltar pro jogo não refaz a chamada à toa) e o estado de
  // loading/erro consistente com o resto do app.
  const { data: cargaJogo, isError: notFound } = useQuery({
    queryKey: ['load_game', sessionId],
    queryFn: async () => {
      const res = await api.post<CargaJogo>('/load_game', { session_id: sessionId });
      return res.data;
    },
    enabled: !!sessionId,
    staleTime: 0, // HP/inventário mudam a cada turno — nunca servir do cache sem revalidar
  });

  useEffect(() => {
    if (!cargaJogo) return;
    setCharName(cargaJogo.nome);
    setCharRace(cargaJogo.raca);
    setCharClass(cargaJogo.classe);
    // Etapa 11 (B-3): o retrato agora persiste em Personagem.imagem — a
    // navegação (criação, primeiro paint) ainda tem prioridade porque
    // chega mais rápido, mas recarregar a página usa o que o servidor
    // guardou em vez de cair direto no retrato genérico da classe.
    if (!charImageFromNav) setCharImage(cargaJogo.imagem || getLocalImage('classes', cargaJogo.classe));
    setHpAtual(cargaJogo.hp_atual);
    setHpMax(cargaJogo.hp_max ?? 10);
    setDefesa(cargaJogo.defesa ?? null);
    setOuro(cargaJogo.ouro ?? 0);
    setNivel(cargaJogo.nivel ?? 1);
    setXp(cargaJogo.xp ?? 0);
    setXpProximoNivel(cargaJogo.xp_proximo_nivel ?? null);
    setInventory(cargaJogo.inventory || []);
    setAttributes(cargaJogo.atributos || {});
    setQuest(cargaJogo.missao);
    setCombatActive(cargaJogo.combat_active);
    setEnemies(cargaJogo.inimigos || []);
    setOrdemIniciativa(cargaJogo.ordem_iniciativa || []);
    setTurnoAtual(cargaJogo.turno_atual ?? 0);
    setTurnoMundo(cargaJogo.turno_mundo ?? 0);

    if (cargaJogo.hp_atual <= 0) setGameOver(true);
    setMessages([{ kind: 'texto', role: 'assistant', content: `Conectado ao mundo. Local: ${cargaJogo.local}.` }]);
  }, [cargaJogo, charImageFromNav]);

  const scrollToBottom = () => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); };
  useEffect(() => { scrollToBottom(); }, [messages]);

  // Adiciona texto à ÚLTIMA mensagem se ela for uma bolha de assistente
  // aberta (`aberta=true`), ou cria uma nova — é o que dá o efeito de
  // máquina de escrever real: o token já chegou do modelo, só falta
  // aparecer na tela (Etapa 7, ADR-0012).
  const acrescentarTexto = (pedaco: string, isError = false) => {
    setMessages(prev => {
      const ultima = prev[prev.length - 1];
      if (ultima && ultima.kind === 'texto' && ultima.role === 'assistant' && !ultima.isError === !isError) {
        const copia = [...prev];
        // Etapa 10 (A-7): limpeza leve sobre o texto ACUMULADO, nunca só o
        // pedaço novo — um `**` pode chegar partido entre dois frames SSE.
        // A limpeza de verdade é no servidor, antes de persistir; isto é
        // só pra tela não piscar o markdown cru por meio segundo.
        copia[copia.length - 1] = { ...ultima, content: limparMarkdownLeve(ultima.content + pedaco), isError };
        return copia;
      }
      return [...prev, { kind: 'texto', role: 'assistant', content: pedaco, isError }];
    });
  };

  const sendAction = async (text: string) => {
    if (!sessionId || gameOver) return;
    setMessages(prev => [...prev, { kind: 'texto', role: 'user', content: text }]);
    setLoading(true);

    try {
      const stream = await postSse(`${API_URL}/chat/stream`, { session_id: sessionId, action: text });

      for await (const evt of stream) {
        if (evt.event === 'token') {
          acrescentarTexto((evt.data as { texto: string }).texto);
        } else if (evt.event === 'tool_event') {
          // Etapa 10 (A-7): cura e morte de inimigo chegam pelo mesmo
          // frame, discriminados por `dados.tipo` na hora de renderizar.
          setMessages(prev => [...prev, { kind: 'rolagem', dados: evt.data as DadosRolagem | EventoStatus }]);
        } else if (evt.event === 'correcao') {
          // O guardrail reescreveu a narrativa depois de já ter sido
          // mostrada ao vivo — a versão persistida (memória futura) é a
          // corrigida, então a tela também passa a refletir ela.
          const narrativaCorrigida = (evt.data as { narrativa: string }).narrativa;
          setMessages(prev => {
            const copia = [...prev];
            for (let i = copia.length - 1; i >= 0; i--) {
              const m = copia[i];
              if (m.kind === 'texto' && m.role === 'assistant') {
                copia[i] = { ...m, content: narrativaCorrigida };
                break;
              }
            }
            return copia;
          });
        } else if (evt.event === 'erro') {
          // Etapa 10 (A-7): mensagem de sistema, sem `*(...)*` — a bolha
          // com `isError=true` já é visualmente distinta (ícone e cor
          // âmbar), não precisa de asterisco pra parecer "fora da narração".
          acrescentarTexto((evt.data as { mensagem: string }).mensagem, true);
        } else if (evt.event === 'state') {
          const d = evt.data as EstadoJogo;
          if (d.hp_atual !== undefined && d.hp_atual < hpAtual) {
              setWasDamaged(true); setShakeScreen(true);
              setTimeout(() => { setWasDamaged(false); setShakeScreen(false); }, 500);
          }
          setHpAtual(d.hp_atual); setHpMax(d.hp_max || hpMax);
          if (d.defesa !== undefined) setDefesa(d.defesa);
          if (d.ouro !== undefined) setOuro(d.ouro);
          if (d.nivel !== undefined) setNivel(d.nivel);
          if (d.xp !== undefined) setXp(d.xp);
          if (d.xp_proximo_nivel !== undefined) setXpProximoNivel(d.xp_proximo_nivel);
          setInventory(d.inventory || []);
          setCombatActive(d.combat_active);

          const novosInimigos = d.inimigos || [];
          const novasFlutuantes = novosInimigos
            .map((novo, idx) => ({ novo, idx, antigo: enemies[idx] }))
            .filter(({ novo, antigo }) => antigo && novo.hp < antigo.hp)
            .map(({ novo, idx, antigo }) => ({ id: Date.now() + idx, valor: antigo.hp - novo.hp, idx }));
          if (novasFlutuantes.length > 0) {
            setDanosFlutuantes(prev => [...prev, ...novasFlutuantes]);
            novasFlutuantes.forEach(f => {
              setTimeout(() => setDanosFlutuantes(prev => prev.filter(x => x.id !== f.id)), 1200);
            });
          }
          setEnemies(novosInimigos);
          setOrdemIniciativa(d.ordem_iniciativa || []);
          setTurnoAtual(d.turno_atual ?? 0);
          if (d.turno_mundo !== undefined) setTurnoMundo(d.turno_mundo);
          if (d.missao) setQuest(d.missao);
          if (d.hp_atual <= 0) setGameOver(true);

          if (d.turno_index !== undefined) {
            const turnoIndex = d.turno_index;
            setMessages(prev => {
              const copia = [...prev];
              for (let i = copia.length - 1; i >= 0; i--) {
                const m = copia[i];
                if (m.kind === 'texto' && m.role === 'assistant') {
                  copia[i] = { ...m, turnoIndex };
                  break;
                }
              }
              return copia;
            });
          }
        }
      }
    } catch (err) {
      // Etapa 10 (A-3): `postSse` agora propaga o `detail` do backend
      // quando existe (teto diário, sessão sumida...) — só cai no genérico
      // quando o problema é mesmo de rede/conexão, sem resposta nenhuma.
      const mensagem = err instanceof Error && err.message ? err.message : "Não consegui falar com o servidor. Confira sua conexão e tente de novo.";
      acrescentarTexto(`*(${mensagem})*`, true);
    }
    finally { setLoading(false); }
  };

  // 👍/👎 por narração (Etapa 9) — sinal humano pro LLM-as-a-judge (ADR-0011)
  // e dataset de preferência. Otimista: marca o voto na hora, sem esperar
  // a resposta do servidor — um turno de RPG não é um formulário crítico.
  const enviarFeedback = (idx: number, turnoIndex: number, valor: 1 | -1, comentario?: string) => {
    setMessages(prev => prev.map((m, i) => (i === idx && m.kind === 'texto' ? { ...m, feedback: valor } : m)));
    api.post(`/personagens/${sessionId}/feedback`, { turno_index: turnoIndex, valor, comentario }).catch(() => {});
  };

  // "Isso ficou estranho" (Etapa 10, A-4) — o 👎 abre um campo opcional em
  // vez de mandar direto: um clique continua funcionando (botão "Pular"),
  // mas quem quiser dizer *o quê* incomodou tem onde. Só uma bolha por vez
  // tem o campo aberto.
  const [comentarioAbertoIdx, setComentarioAbertoIdx] = useState<number | null>(null);
  const [comentarioTexto, setComentarioTexto] = useState('');

  const handleSendMessage = () => { if (!input.trim()) return; sendAction(input); setInput(""); };
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } };

  if (notFound) {
    return (
        <div className="h-screen w-screen bg-black flex flex-col items-center justify-center text-gray-300 gap-4">
            <PixelIcon name="alerta" size={48}/>
            <h1 className="text-2xl font-rpg">Essa jornada não existe mais</h1>
            <p className="text-gray-500 text-sm">O save "{sessionId}" não foi encontrado no servidor.</p>
            <button onClick={() => navigate('/')} className="mt-4 border-2 border-gray-700 px-4 py-2 text-gray-400 hover:text-white hover:border-gray-500">Voltar ao menu</button>
        </div>
    );
  }

  // Etapa 11 (B-7) — só o primeiro carregamento (nenhum turno jogado
  // ainda) mostra a tela de abertura; `historico_chat[0]` é sempre o
  // prólogo (routers/character.py:create_character).
  const primeiroTurno = (cargaJogo?.historico_chat?.length ?? 0) === 1;
  if (cargaJogo && primeiroTurno && !prologoConcluido && !gameOver) {
    return (
      <Prologo
        nome={cargaJogo.nome}
        raca={cargaJogo.raca}
        classe={cargaJogo.classe}
        local={cargaJogo.local}
        clima={cargaJogo.clima}
        background={cargaJogo.background}
        objetivo={cargaJogo.objetivo}
        charImage={charImage || getLocalImage('classes', cargaJogo.classe)}
        texto={cargaJogo.historico_chat![0].content}
        onComecar={() => setPrologoConcluido(true)}
      />
    );
  }

  return (
    <div className={`flex h-screen w-screen bg-black text-gray-100 font-sans overflow-hidden relative ${shakeScreen ? 'animate-shake' : ''}`}>

      <div className={`absolute inset-0 z-50 bg-red-600 pointer-events-none transition-opacity duration-200 ${wasDamaged ? 'opacity-20' : 'opacity-0'}`} />

      {gameOver && (
        <div className="absolute inset-0 z-[100] bg-black/95 flex flex-col items-center justify-center px-6 text-center overflow-y-auto py-10">
          <h1 className="text-3xl md:text-5xl font-pixel-title text-red-600 tracking-widest leading-relaxed">GAME OVER</h1>
          <p className="text-gray-500 mt-2 font-serif italic">{charName || 'O herói'} não resistiu.</p>

          <div className="grid grid-cols-3 gap-8 mt-8">
            <div>
              <div className="text-2xl font-rpg text-rpg-gold">{turnoMundo}</div>
              <div className="text-[10px] uppercase tracking-widest text-gray-500 mt-1">Turnos</div>
            </div>
            <div>
              <div className="text-2xl font-rpg text-rpg-gold">{nivel}</div>
              <div className="text-[10px] uppercase tracking-widest text-gray-500 mt-1">Nível</div>
            </div>
            <div>
              <div className="text-2xl font-rpg text-rpg-gold flex items-center justify-center gap-1">
                <PixelIcon name="moeda" size={16} />{ouro}
              </div>
              <div className="text-[10px] uppercase tracking-widest text-gray-500 mt-1">Ouro</div>
            </div>
          </div>

          {quest?.nome_missao && (
            <p className="text-xs text-gray-500 mt-6 max-w-sm italic">
              Missão inacabada: "{quest.nome_missao}"
            </p>
          )}

          {/* Etapa 12b (C-4): aqui entra a retrospectiva gerada por IA sobre
              esta run (memórias mais marcantes + epitáfio de uma linha) —
              por enquanto o placar acima é tudo que existe. */}
          <div className="mt-8 border-t border-gray-800 pt-4 w-full max-w-sm">
            <p className="text-[10px] uppercase tracking-widest text-gray-600">O relato do mestre</p>
            <p className="text-sm text-gray-500 italic mt-1">Em breve, o mestre vai contar como termina esta jornada.</p>
          </div>

          <button
            onClick={() => navigate('/')}
            className="mt-8 border-2 border-gray-700 px-4 py-2 text-gray-400 hover:text-white hover:border-gray-500 transition-colors"
          >
            Voltar
          </button>
        </div>
      )}

      {/* Fundo escurecido atrás da ficha em telas estreitas (Etapa 7) — no
          desktop a ficha empurra o layout ao lado; no mobile ela vira uma
          gaveta sobreposta, e este fundo é o que permite fechar tocando fora. */}
      {showSidebar && (
          <div
              onClick={() => setShowSidebar(false)}
              className="md:hidden fixed inset-0 z-40 bg-black/60"
              aria-hidden="true"
          />
      )}

      {/* SIDEBAR (Ficha) — abre/fecha com `left`, não `translate-x`: Tailwind
          v4 compõe translate a partir de `--tw-translate-x/y`, e o reset
          universal que zera essas variáveis vive atrás de um
          `@supports` de sintaxe de cor relativa (ver index.css gerado);
          nem todo motor de renderização honra isso, e sem o reset o
          `translate` inteiro fica inválido — a gaveta simplesmente não
          se move. `left`/`-left-80` é uma propriedade física comum, sem
          essa dependência. */}
      <div
          className={`${showSidebar ? 'w-80 md:w-96 left-0' : 'w-80 -left-80 md:left-0 md:w-0'}
              fixed md:relative top-0 bottom-0 z-50 md:z-auto
              transition-all duration-300 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0 overflow-hidden`}
      >
          <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-black/20">
              <h2 className="font-pixel-title text-sm text-rpg-gold flex items-center gap-2 truncate"><PixelIcon name="pergaminho" size={18}/> FICHA</h2>
              <div className="flex items-center gap-3">
                  {/* Som e "voltar ao menu" saíram daqui: viraram itens do
                      menu de opções, que é onde o jogador procura por eles e
                      onde cabem os próximos ajustes. */}
                  <button
                      onClick={() => setConfigAberta(true)}
                      aria-label="Abrir configurações"
                      title="Configurações"
                      className="text-gray-300 hover:text-rpg-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold"
                  ><PixelIcon name="config" size={18}/></button>
                  <button
                      onClick={() => setShowSidebar(false)}
                      aria-label="Fechar ficha do personagem"
                      className="text-gray-500 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold"
                  ><PixelIcon name="fechar" size={18}/></button>
              </div>
          </div>

          {/* Retrato COMPACTO. O busto grande ocupava 343px de altura — mais
              que todo o conteúdo da aba STATUS junto (293px, medido), e num
              notebook de 768px sobrava pouco pro resto. Em linha ele custa
              ~88px e continua sendo a âncora de identidade do menu; quem
              quiser ver grande clica e abre em tela cheia. */}
          <button
              onClick={() => setRetratoAberto(true)}
              className="shrink-0 m-3 mb-0 flex items-center gap-3 p-2 border-2 border-gray-700 hover:border-rpg-gold bg-black/50 transition-colors text-left focus-visible:outline-none focus-visible:border-rpg-gold"
              aria-label={`Ver retrato de ${charName} em tamanho grande`}
          >
              <div className="pixel-frame w-16 h-16 shrink-0 bg-black overflow-hidden">
                  <RetratoPixelado src={charImage} alt="" className="w-full h-full object-cover object-top" />
              </div>
              <div className="min-w-0">
                  <p className="text-white font-rpg text-lg leading-tight truncate">{charName}</p>
                  <p className="text-[10px] text-gray-300 uppercase tracking-wide font-rpg truncate">{charRace} {charClass}</p>
              </div>
          </button>

          {/* Abas. A ficha inteira empilhada numa coluna de 320px ficava
              espremida e obrigava a rolar pra achar qualquer coisa; separada em
              três telas, cada uma respira. Um `role="tablist"` de verdade, pra
              seta do teclado e leitor de tela funcionarem como o esperado. */}
          <div role="tablist" aria-label="Ficha do personagem" className="flex shrink-0 px-3 pt-3 gap-1">
              {ABAS.map((aba) => (
                  <button
                      key={aba.id}
                      role="tab"
                      id={`aba-${aba.id}`}
                      aria-selected={abaAtiva === aba.id}
                      aria-controls={`painel-${aba.id}`}
                      onClick={() => setAbaAtiva(aba.id)}
                      // `font-rpg` (VT323) e nao `font-pixel-title`: a Press
                      // Start 2P nao tem glifos acentuados, e "MISSÃO" saia
                      // renderizado como "MISSAO" na aba.
                      className={`flex-1 flex items-center justify-center gap-1 py-2 border-2 text-sm tracking-wider font-rpg transition-colors focus-visible:outline-none focus-visible:border-rpg-gold ${
                          abaAtiva === aba.id
                              ? 'border-rpg-gold bg-rpg-gold/20 text-rpg-gold'
                              : 'border-gray-700 bg-black/40 text-gray-400 hover:text-gray-200 hover:border-gray-500'
                      }`}
                  >
                      <PixelIcon name={aba.icone} size={12} />
                      <span className="hidden sm:inline">{aba.rotulo}</span>
                  </button>
              ))}
          </div>

          <div
              role="tabpanel"
              id={`painel-${abaAtiva}`}
              aria-labelledby={`aba-${abaAtiva}`}
              className="p-3 space-y-4 overflow-y-auto custom-scrollbar flex-1"
          >
              {abaAtiva === 'status' && (
                <div className="space-y-4 animate-fade-in">
                  {/* Vida, nível e defesa NÃO estão mais aqui: viraram a faixa
                      sobre o chat (HudVitais). São o que se precisa olhar no
                      meio da luta, e ali ficam visíveis com a ficha fechada.
                      Esta aba guarda o que é consulta, não urgência. */}
                  {/* Os SEIS atributos. Antes só FOR/DES/INT apareciam, fixos
                      no código, embora o backend sempre mandasse os seis em
                      `atributos` — quem jogava de Clérigo ou Bardo não via o
                      atributo que mais importa pra ele. */}
                  <div className="grid grid-cols-3 gap-2">
                     {ATRIBUTOS.map(([chave, sigla]) => (
                       <div key={chave} className="bg-black/50 p-2 text-center border-2 border-gray-700">
                           <span className="text-[9px] text-gray-300 block font-rpg">{sigla}</span>
                           <span className="font-rpg text-xl text-gray-100">{attributes?.[chave] ?? '-'}</span>
                       </div>
                     ))}
                  </div>
                </div>
              )}

              {abaAtiva === 'itens' && (
                <div className="space-y-2 animate-fade-in">
                    <div className="flex items-center justify-between">
                        <h3 className="text-[10px] text-gray-300 uppercase font-rpg tracking-widest flex items-center gap-2"><PixelIcon name="mochila" size={12}/> Mochila</h3>
                        <span className="text-sm text-rpg-gold font-rpg flex items-center gap-1"><PixelIcon name="moeda" size={14}/> {ouro}</span>
                    </div>
                    <InventoryGrid items={inventory} />
                </div>
              )}

              {abaAtiva === 'missao' && (
                <div className="animate-fade-in">
                  {quest ? (
                      <div className="bg-black/50 border-2 border-blue-800 p-3">
                          <h3 className="text-[10px] text-blue-300 uppercase font-rpg mb-2 tracking-widest">Missão atual</h3>
                          <p className="text-base text-blue-100 font-rpg leading-tight mb-2">{quest.nome_missao}</p>
                          <p className="text-xs text-gray-200 leading-relaxed">{quest.objetivo_missao}</p>
                      </div>
                  ) : (
                      <p className="text-sm text-gray-400 font-rpg text-center py-8">Nenhuma missão em andamento.</p>
                  )}
                </div>
              )}
          </div>
      </div>

      {/* Retrato em tamanho grande, sob demanda. A ficha mostra a versão
          compacta pra não gastar 343px de altura com algo que se olha uma vez;
          quem quiser admirar clica e vem parar aqui. */}
      {retratoAberto && (
          <div
              className="fixed inset-0 z-[60] bg-black/85 flex items-center justify-center p-6 animate-fade-in"
              onClick={() => setRetratoAberto(false)}
              role="dialog"
              aria-modal="true"
              aria-label={`Retrato de ${charName}`}
          >
              <div className="pixel-frame bg-black max-w-sm w-full aspect-[3/4] relative overflow-hidden" onClick={(e) => e.stopPropagation()}>
                  <RetratoPixelado src={charImage} alt={`Retrato de ${charName}`} grade={110} className="w-full h-full object-cover object-top" />
                  <div className="absolute bottom-0 w-full bg-gradient-to-t from-black via-black/85 to-transparent p-3 pt-10">
                      <p className="text-white font-rpg text-xl leading-tight">{charName}</p>
                      <p className="text-[11px] text-gray-300 uppercase tracking-wide font-rpg">{charRace} {charClass}</p>
                  </div>
                  <button
                      onClick={() => setRetratoAberto(false)}
                      aria-label="Fechar retrato"
                      className="absolute top-2 right-2 p-1 bg-black/70 border-2 border-gray-600 hover:border-rpg-gold focus-visible:outline-none focus-visible:border-rpg-gold"
                  ><PixelIcon name="fechar" size={16}/></button>
              </div>
          </div>
      )}

      <MenuConfiguracao aberto={configAberta} aoFechar={() => setConfigAberta(false)} trilha={trilha} />

      {/* CHAT AREA */}
      <div className="flex-1 flex flex-col relative bg-[#050505]">
        {/* Vitais sobre a área de jogo, não dentro da ficha: vida, nível e
            defesa são o que se olha NO MEIO da luta, e aqui continuam
            visíveis mesmo com a ficha fechada — que é como jogo faz. De
            quebra devolveram ~150px de altura pra barra lateral. */}
        <div className="shrink-0 flex items-center gap-3 md:gap-4 px-3 py-2 border-b-2 border-gray-800 bg-black/60">
            {/* Abrir a ficha mora DENTRO da faixa, nao flutuando sobre ela.
                Antes era `absolute top-4 left-4` e cobria o numero de vida
                quando a ficha estava fechada — parecia defeito de layout. */}
            {!showSidebar && (
                <button
                    onClick={() => setShowSidebar(true)}
                    aria-label="Abrir ficha do personagem"
                    className="shrink-0 p-1 border-2 border-gray-700 hover:border-rpg-gold text-gray-300 hover:text-rpg-gold transition-colors focus-visible:outline-none focus-visible:border-rpg-gold"
                ><PixelIcon name="menu" size={16}/></button>
            )}
            {/* As tres medidas reagem ao mouse e dizem o que sao. Sem isso a
                faixa era uma fileira de barras coloridas sem legenda: dava pra
                jogar sem saber qual e vida e qual e experiencia. O mesmo
                `ui/tooltip` que o RollCard e o inventario ja usam. */}
            <TooltipProvider delayDuration={120}>
                <Tooltip>
                    <TooltipTrigger asChild>
                        <div tabIndex={0} className="flex items-center gap-2 min-w-0 max-w-[260px] cursor-help px-1 py-0.5 border-2 border-transparent hover:border-gray-700 focus-visible:outline-none focus-visible:border-rpg-gold transition-colors">
                            <PixelIcon name="coracao" size={14} />
                            <span className="text-[11px] font-rpg text-gray-200 shrink-0">{hpAtual}/{hpMax}</span>
                            <div className="flex-1 min-w-[60px] max-w-[180px]"><PixelBar value={hpAtual} max={hpMax} colorClass="bg-red-600" /></div>
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>
                        Vida: {hpAtual} de {hpMax}
                        {hpMax > 0 && ` (${Math.round((hpAtual / hpMax) * 100)}%)`}
                    </TooltipContent>
                </Tooltip>

                <Tooltip>
                    <TooltipTrigger asChild>
                        <div tabIndex={0} className="hidden sm:flex items-center gap-2 min-w-0 max-w-[260px] cursor-help px-1 py-0.5 border-2 border-transparent hover:border-gray-700 focus-visible:outline-none focus-visible:border-rpg-gold transition-colors">
                            <PixelIcon name="estrela" size={14} />
                            <span className="text-[11px] font-rpg text-gray-200 shrink-0">Nv {nivel}</span>
                            <div className="flex-1 min-w-[60px] max-w-[180px]">
                                <PixelBar
                                    value={xpProximoNivel != null ? xp : 1}
                                    max={xpProximoNivel != null ? xpProximoNivel : 1}
                                    colorClass="bg-rpg-gold"
                                />
                            </div>
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>
                        {xpProximoNivel != null
                            ? `Experiência: ${xp} de ${xpProximoNivel} para o nível ${nivel + 1}`
                            : `Nível ${nivel} — experiência no máximo`}
                    </TooltipContent>
                </Tooltip>

                <Tooltip>
                    <TooltipTrigger asChild>
                        <div tabIndex={0} className="flex items-center gap-1 shrink-0 ml-auto cursor-help px-1 py-0.5 border-2 border-transparent hover:border-gray-700 focus-visible:outline-none focus-visible:border-rpg-gold transition-colors">
                            <PixelIcon name="escudo" size={14} />
                            <span className="text-[11px] font-rpg text-blue-200">{defesa ?? "?"}</span>
                        </div>
                    </TooltipTrigger>
                    <TooltipContent>
                        Defesa {defesa ?? "?"} — o número que um ataque precisa alcançar para acertar você.
                    </TooltipContent>
                </Tooltip>
            </TooltipProvider>
        </div>

        {/* Convite pra reivindicar (Etapa 10, A-1) — aparece só pro
            convidado, depois do primeiro momento bom. Fica embaixo, longe
            do HUD de combate lá em cima, e some sozinho se o jogador
            dispensar (não volta na mesma aba). */}
        {mostrarConviteReivindicar && !modalReivindicarAberto && (
            <div className="absolute bottom-24 left-1/2 -translate-x-1/2 z-40 w-[calc(100%-2rem)] max-w-md animate-fade-in">
                <PanelFrame borderWidth={6} className="bg-gray-900/95 p-3 flex items-center gap-3 shadow-xl backdrop-blur-sm">
                    <PixelIcon name="coroa" size={20} className="shrink-0" />
                    <p className="text-xs text-gray-300 flex-1">Curtindo? Crie uma conta pra não perder esse herói.</p>
                    <button
                        onClick={() => setModalReivindicarAberto(true)}
                        className="text-xs font-bold text-black bg-rpg-gold hover:bg-white px-3 py-1.5 shrink-0"
                    >
                        Criar conta
                    </button>
                    <button onClick={dispensarConvite} aria-label="Dispensar convite" className="text-gray-500 hover:text-white shrink-0">
                        <PixelIcon name="fechar" size={16} />
                    </button>
                </PanelFrame>
            </div>
        )}

        {modalReivindicarAberto && (
            <div className="absolute inset-0 z-[90] bg-black/80 flex items-center justify-center p-4">
                <PanelFrame borderWidth={10} className="w-full max-w-sm">
                <form onSubmit={reivindicar} className="bg-gray-900 p-6">
                    <h2 className="font-rpg text-lg text-rpg-gold mb-1">Criar conta</h2>
                    <p className="text-xs text-gray-500 mb-4">{charName} continua exatamente como está — só ganha um dono de verdade.</p>
                    <div className="flex flex-col gap-3">
                        <input
                            type="email"
                            required
                            autoFocus
                            placeholder="seu@email.com"
                            className="bg-black/60 border-2 border-gray-700 px-3 py-2 text-white text-sm outline-none focus:border-rpg-gold"
                            value={reivindicarEmail}
                            onChange={(e) => setReivindicarEmail(e.target.value)}
                        />
                        <input
                            type="password"
                            required
                            minLength={8}
                            placeholder="Mínimo 8 caracteres"
                            className="bg-black/60 border-2 border-gray-700 px-3 py-2 text-white text-sm outline-none focus:border-rpg-gold"
                            value={reivindicarSenha}
                            onChange={(e) => setReivindicarSenha(e.target.value)}
                        />
                        {reivindicarErro && <p className="text-red-500 text-xs">{reivindicarErro}</p>}
                        <div className="flex gap-2 mt-1">
                            <button
                                type="button"
                                onClick={() => setModalReivindicarAberto(false)}
                                className="flex-1 border-2 border-gray-700 text-gray-400 hover:text-white py-2 text-sm"
                            >
                                Cancelar
                            </button>
                            <PixelButton
                                type="submit"
                                variant="dourado"
                                disabled={reivindicarEnviando}
                                className="flex-1 py-2 text-sm"
                            >
                                {reivindicarEnviando ? <Carregando rotulo="Salvando" /> : 'Salvar'}
                            </PixelButton>
                        </div>
                    </div>
                </form>
                </PanelFrame>
            </div>
        )}

        {/* HUD Inimigos — ordem de iniciativa real (Etapa 7, Fase 1): a
            posição vem de `ordemIniciativa` (índices em `enemies`, -1 é o
            herói), calculada uma vez por `combat.iniciar_combate`. Clicar
            num inimigo sugere o alvo na próxima ação — quem decide o alvo
            de verdade continua sendo o texto interpretado pelo modelo
            (ADR-0006), isto só evita digitar o nome à mão. */}
        {combatActive && enemies.length > 0 && !gameOver && (
            <div className="absolute top-0 w-full bg-gradient-to-b from-red-950/90 to-transparent p-2 z-30 flex justify-center gap-4 animate-fade-in shadow-lg">
                <span className="absolute left-4 top-4 text-red-500 font-rpg text-xs animate-pulse flex items-center gap-2"><PixelIcon name="espada" size={14}/> COMBATE</span>
                {enemies.map((en, i) => {
                    const posicao = ordemIniciativa.indexOf(i);
                    const suaVez = posicao !== -1 && ordemIniciativa[turnoAtual] === i;
                    const morto = en.hp <= 0;
                    return (
                        <button
                            key={i}
                            type="button"
                            onClick={() => !morto && setInput(`Eu ataco ${en.nome}`)}
                            disabled={morto}
                            aria-label={morto ? `${en.nome} (derrotado)` : `Atacar ${en.nome}`}
                            className={`relative min-w-[100px] bg-black/80 p-2 border-2 backdrop-blur-sm text-left transition-colors
                                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold
                                ${morto ? 'border-gray-800 opacity-40 cursor-default' : 'border-red-900/50 hover:border-rpg-gold cursor-pointer'}
                                ${suaVez && !morto ? 'ring-1 ring-rpg-gold' : ''}`}
                        >
                            {danosFlutuantes.filter(f => f.idx === i).map(f => (
                                <span key={f.id} className="absolute left-1/2 top-0 -translate-x-1/2 text-red-400 font-bold text-sm pointer-events-none animate-float-up">
                                    -{f.valor}
                                </span>
                            ))}
                            <div className="flex justify-between items-center mb-1 gap-1">
                                {posicao !== -1 && (
                                    <span className={`text-[9px] font-mono px-1 shrink-0 ${suaVez ? 'bg-rpg-gold text-black' : 'bg-gray-800 text-gray-400'}`}>
                                        {posicao + 1}
                                    </span>
                                )}
                                {/* Etapa 11 (B-1) — sprite do monstro pelo nome; bestiário
                                    fora do catálogo simplesmente não mostra imagem
                                    (onError some com o ícone em vez de quebrar o layout). */}
                                <img
                                    src={getLocalImage('monstros', en.nome)}
                                    alt=""
                                    className="w-4 h-4 shrink-0"
                                    onError={(e) => { e.currentTarget.style.display = 'none'; }}
                                />
                                <span className="text-[10px] font-bold text-red-100 truncate">{en.nome}</span>
                            </div>
                            <PixelBar value={en.hp} max={en.max_hp} segments={8} colorClass="bg-red-600" />
                        </button>
                    );
                })}
            </div>
        )}

        {/* `aria-live="polite"` avisa leitor de tela sobre narração/rolagens
            chegando — a ressalva honesta (Lição 08, Etapa 7) é que o
            streaming token a token pode soar picotado num leitor de tela
            real, já que cada pedacinho de texto é uma mudança no live
            region; mitigar isso de verdade (debounce por frase) ficou
            para depois. */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 custom-scrollbar scroll-smooth" role="log" aria-live="polite" aria-atomic="false">
            <div className="h-12"></div>
            {messages.map((msg, idx) => {
                if (msg.kind === 'rolagem') {
                    // Etapa 10 (A-7): cura/morte de inimigo usam o card de
                    // status; o resto (ataque, teste, dano, morte do herói)
                    // continua no RollCard de sempre.
                    if (msg.dados.tipo === 'cura' || msg.dados.tipo === 'morte_inimigo') {
                        return <StatusCard key={idx} dados={msg.dados} />;
                    }
                    return <RollCard key={idx} dados={msg.dados as DadosRolagem} />;
                }

                const isUser = msg.role === 'user';
                const isSystem = msg.role === 'system';

                if (isSystem) {
                    return (
                        <div key={idx} className="flex justify-center my-2 animate-fade-in">
                            <div className="bg-yellow-900/20 border border-yellow-700/30 text-yellow-500 px-4 py-2 text-xs font-mono flex items-center gap-2">
                                <PixelIcon name="dado" size={12}/> {msg.content}
                            </div>
                        </div>
                    );
                }

                return (
                    <div key={idx} className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} animate-fade-in`}>
                        <div className={`w-9 h-9 shrink-0 flex items-center justify-center border shadow-md overflow-hidden ${isUser ? 'border-blue-900 bg-blue-950' : msg.isError ? 'border-amber-700 bg-amber-950' : 'border-gray-700 bg-gray-900'}`}>
                             {isUser ? (
                                 <img src={charImage} className="w-full h-full object-cover" onError={(e) => {e.currentTarget.style.display='none'}}/>
                             ) : msg.isError ? (
                                 <PixelIcon name="alerta" size={16}/>
                             ) : (
                                 <PixelIcon name="dado" size={16}/>
                             )}
                             {isUser && <PixelIcon name="rosto" size={16} className="absolute -z-10"/>}
                        </div>

                        <div className={`max-w-[85%] p-3.5 text-sm md:text-base leading-relaxed shadow-lg backdrop-blur-sm
                            ${isUser
                                ? 'bg-blue-950/40 border border-blue-900/30 text-blue-100'
                                : msg.isError
                                ? 'bg-amber-950/30 border border-amber-800/40 text-amber-200 italic'
                                : 'bg-gray-900/60 border border-gray-800 text-gray-300'
                            }`}>
                            <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                            {!isUser && !msg.isError && msg.turnoIndex !== undefined && (
                                comentarioAbertoIdx === idx ? (
                                    <div className="mt-2 -mb-1 flex flex-col gap-1.5">
                                        <input
                                            type="text"
                                            autoFocus
                                            value={comentarioTexto}
                                            onChange={(e) => setComentarioTexto(e.target.value)}
                                            onKeyDown={(e) => {
                                                if (e.key === 'Enter') {
                                                    enviarFeedback(idx, msg.turnoIndex!, -1, comentarioTexto.trim() || undefined);
                                                    setComentarioAbertoIdx(null);
                                                    setComentarioTexto('');
                                                }
                                            }}
                                            maxLength={500}
                                            placeholder="O que ficou estranho? (opcional)"
                                            aria-label="O que ficou estranho? Opcional."
                                            className="bg-black/40 border border-gray-700 px-2 py-1 text-xs text-gray-200 outline-none focus:border-red-700 w-full max-w-xs"
                                        />
                                        <div className="flex gap-2">
                                            <button
                                                type="button"
                                                onClick={() => {
                                                    enviarFeedback(idx, msg.turnoIndex!, -1, comentarioTexto.trim() || undefined);
                                                    setComentarioAbertoIdx(null);
                                                    setComentarioTexto('');
                                                }}
                                                className="text-[11px] font-bold text-red-400 hover:text-red-300"
                                            >Enviar</button>
                                            <button
                                                type="button"
                                                onClick={() => { setComentarioAbertoIdx(null); setComentarioTexto(''); }}
                                                className="text-[11px] text-gray-500 hover:text-gray-300"
                                            >Cancelar</button>
                                        </div>
                                    </div>
                                ) : (
                                    <div className="flex gap-2 mt-2 -mb-1">
                                        <button
                                            type="button"
                                            onClick={() => enviarFeedback(idx, msg.turnoIndex!, 1)}
                                            disabled={msg.feedback !== undefined}
                                            aria-label="Gostei desta narração"
                                            className={`p-1 transition-colors ${msg.feedback === 1 ? 'text-emerald-500' : 'text-gray-600 hover:text-emerald-500 disabled:hover:text-gray-600'}`}
                                        ><PixelIcon name="polegar-cima" size={13}/></button>
                                        <button
                                            type="button"
                                            onClick={() => { if (msg.feedback === undefined) setComentarioAbertoIdx(idx); }}
                                            disabled={msg.feedback !== undefined}
                                            aria-label="Não gostei desta narração"
                                            className={`p-1 transition-colors ${msg.feedback === -1 ? 'text-red-500' : 'text-gray-600 hover:text-red-500 disabled:hover:text-gray-600'}`}
                                        ><PixelIcon name="polegar-baixo" size={13}/></button>
                                    </div>
                                )
                            )}
                        </div>
                    </div>
                );
            })}

            {loading && <div className="text-center py-4 text-xs text-gray-600 animate-pulse italic">O mestre está narrando...</div>}
            <div ref={messagesEndRef} className="h-4" />
        </div>

        {/* INPUT AREA */}
        <div className="p-4 border-t border-gray-800 bg-gray-900 z-40 relative">
            <div className="max-w-4xl mx-auto flex gap-2 bg-black/40 p-1.5 border-2 border-gray-700 focus-within:border-rpg-gold transition-colors shadow-inner">
                <textarea
                    value={input}
                    onChange={(e) => setInput(e.target.value)}
                    onKeyDown={handleKeyDown}
                    placeholder={combatActive ? "Ameaça iminente! (Ex: 'Ataco o inimigo', 'Fujo')" : "Sua ação..."}
                    aria-label="Sua ação"
                    disabled={gameOver}
                    className="flex-1 bg-transparent text-gray-200 p-3 outline-none resize-none h-12 max-h-32 custom-scrollbar font-serif text-sm placeholder-gray-500 disabled:opacity-50"
                />
                <button
                    onClick={handleSendMessage}
                    disabled={loading || !input.trim() || gameOver}
                    aria-label="Enviar ação"
                    className="h-10 w-10 bg-gray-800 hover:bg-gray-700 text-rpg-gold flex items-center justify-center transition-all mt-1 mr-1 border border-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold disabled:opacity-40"
                >
                    <PixelIcon name="enviar" size={18}/>
                </button>
            </div>
        </div>
      </div>
    </div>
  );
}
