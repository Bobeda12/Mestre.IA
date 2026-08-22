import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  Send, Scroll, Menu, X, Dices, User, Backpack, Map, Sword, Shield, AlertTriangle, Star, Coins, FlaskConical, BookOpen,
  ThumbsUp, ThumbsDown
} from 'lucide-react';
import { Progress } from './ui/progress';
import { api, API_URL } from '../lib/api';
import { postSse } from '../lib/sse';
import { getLocalImage } from '../lib/utils';
import RollCard, { type DadosRolagem } from './RollCard';

type Message =
  // `turnoIndex` (Etapa 9) chega no frame SSE "state", junto do resto do
  // HUD — é a posição desta narração em `historico_chat` no servidor
  // (Personagem.historico_chat), o que o botão 👍/👎 manda pra
  // POST /personagens/:id/feedback. `feedback` é só o que ESTE navegador já
  // votou, pra não deixar votar duas vezes na mesma aba.
  | { kind: 'texto'; role: 'user' | 'assistant' | 'system'; content: string; isError?: boolean; turnoIndex?: number; feedback?: 1 | -1 }
  | { kind: 'rolagem'; dados: DadosRolagem };

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
}

interface CargaJogo extends EstadoJogo {
  nome: string;
  raca: string;
  classe: string;
  local: string;
  atributos?: Record<string, number>;
}

// Ícone por palavra-chave no nome do item — não existe um campo "tipo" em
// data/weapons.json/o inventário do herói, só o nome mesmo (ver
// app/infra/db.py:Personagem.inventario, uma lista de strings).
const _PALAVRAS_POCAO = ['poção', 'pocao', 'elixir', 'frasco'];
const _PALAVRAS_ARMA = ['espada', 'cimitarra', 'machado', 'adaga', 'maça', 'martelo', 'arco', 'lança', 'rapier'];
const _PALAVRAS_ARMADURA = ['armadura', 'cota', 'escudo', 'couro', 'placas'];

function ItemIcon({ nome }: { nome: string }) {
  const nomeLower = nome.toLowerCase();
  if (_PALAVRAS_POCAO.some(p => nomeLower.includes(p))) return <FlaskConical size={12} className="text-emerald-500 shrink-0" />;
  if (_PALAVRAS_ARMA.some(p => nomeLower.includes(p))) return <Sword size={12} className="text-gray-400 shrink-0" />;
  if (_PALAVRAS_ARMADURA.some(p => nomeLower.includes(p))) return <Shield size={12} className="text-blue-500 shrink-0" />;
  return <BookOpen size={12} className="text-gray-500 shrink-0" />;
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
  const [gameOver, setGameOver] = useState(false);
  // Dano flutuante (Etapa 7) — `idx` é a posição no array `enemies`, não o
  // nome (dois inimigos podem ter o mesmo nome).
  const [danosFlutuantes, setDanosFlutuantes] = useState<{ id: number; valor: number; idx: number }[]>([]);

  // EFEITOS
  const [shakeScreen, setShakeScreen] = useState(false);
  const [wasDamaged, setWasDamaged] = useState(false);

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
    // Etapa 8: o retrato gerado por IA na criação não é persistido no
    // servidor (não existe coluna de imagem em Personagem) — só chegava
    // aqui via `location.state` (criação) ou, antes, via localStorage
    // (agora extinto). Entrando por "continuar", cai no retrato genérico
    // da classe em vez de ficar sem imagem nenhuma.
    if (!charImageFromNav) setCharImage(getLocalImage('classes', cargaJogo.classe));
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
        copia[copia.length - 1] = { ...ultima, content: ultima.content + pedaco, isError };
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
          setMessages(prev => [...prev, { kind: 'rolagem', dados: evt.data as DadosRolagem }]);
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
          acrescentarTexto(`*(${(evt.data as { mensagem: string }).mensagem})*`, true);
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
    } catch {
      acrescentarTexto("*(Não consegui falar com o servidor. Confira sua conexão e tente de novo.)*", true);
    }
    finally { setLoading(false); }
  };

  // 👍/👎 por narração (Etapa 9) — sinal humano pro LLM-as-a-judge (ADR-0011)
  // e dataset de preferência. Otimista: marca o voto na hora, sem esperar
  // a resposta do servidor — um turno de RPG não é um formulário crítico.
  const enviarFeedback = (idx: number, turnoIndex: number, valor: 1 | -1) => {
    setMessages(prev => prev.map((m, i) => (i === idx && m.kind === 'texto' ? { ...m, feedback: valor } : m)));
    api.post(`/personagens/${sessionId}/feedback`, { turno_index: turnoIndex, valor }).catch(() => {});
  };

  const handleSendMessage = () => { if (!input.trim()) return; sendAction(input); setInput(""); };
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); handleSendMessage(); } };

  if (notFound) {
    return (
        <div className="h-screen w-screen bg-black flex flex-col items-center justify-center text-gray-300 gap-4">
            <AlertTriangle size={48} className="text-red-600"/>
            <h1 className="text-2xl font-rpg">Essa jornada não existe mais</h1>
            <p className="text-gray-500 text-sm">O save "{sessionId}" não foi encontrado no servidor.</p>
            <button onClick={() => navigate('/')} className="mt-4 border border-gray-700 px-4 py-2 rounded text-gray-400 hover:text-white hover:border-gray-500">Voltar ao menu</button>
        </div>
    );
  }

  return (
    <div className={`flex h-screen w-screen bg-black text-gray-100 font-sans overflow-hidden relative ${shakeScreen ? 'animate-shake' : ''}`}>

      <div className={`absolute inset-0 z-50 bg-red-600 pointer-events-none transition-opacity duration-200 ${wasDamaged ? 'opacity-20' : 'opacity-0'}`} />

      {gameOver && <div className="absolute inset-0 z-[100] bg-black/95 flex flex-col items-center justify-center"><h1 className="text-5xl font-rpg text-red-600">GAME OVER</h1><button onClick={() => navigate('/')} className="mt-4 border px-4 py-2 text-gray-400">Voltar</button></div>}

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
          className={`${showSidebar ? 'w-80 left-0' : 'w-80 -left-80 md:left-0 md:w-0'}
              fixed md:relative top-0 bottom-0 z-50 md:z-auto
              transition-all duration-300 bg-gray-900 border-r border-gray-800 flex flex-col shrink-0 overflow-hidden`}
      >
          <div className="p-4 border-b border-gray-800 flex justify-between items-center bg-black/20">
              <h2 className="font-rpg text-lg text-rpg-gold flex items-center gap-2"><Scroll size={18}/> FICHA</h2>
              <button
                  onClick={() => setShowSidebar(false)}
                  aria-label="Fechar ficha do personagem"
                  className="text-gray-500 hover:text-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold rounded"
              ><X size={18}/></button>
          </div>

          <div className="p-4 space-y-6 overflow-y-auto custom-scrollbar flex-1">
              {/* Foto */}
              <div className="w-full aspect-[3/4] bg-black rounded border border-gray-800 relative shadow-lg overflow-hidden">
                   <img src={charImage} className="w-full h-full object-cover opacity-90" onError={(e) => (e.currentTarget.src = "https://via.placeholder.com/300x400")}/>
                   <div className="absolute bottom-0 w-full bg-gradient-to-t from-black via-black/80 to-transparent p-3 pt-8">
                       <p className="text-white font-rpg text-lg">{charName}</p>
                       <p className="text-xs text-gray-400 uppercase tracking-wide">{charRace} {charClass}</p>
                   </div>
              </div>

              {/* Vida, Nível/XP e Defesa */}
              <div className="bg-gray-800/30 p-3 rounded border border-gray-700 space-y-3">
                  <div>
                    <div className="flex justify-between text-xs font-bold uppercase mb-1"><span>Vida</span><span>{hpAtual}/{hpMax}</span></div>
                    <Progress
                      value={Math.max(0, Math.min(100, (hpAtual / hpMax) * 100))}
                      className="h-1.5 bg-gray-900 [&_[data-slot=progress-indicator]]:bg-red-700 [&_[data-slot=progress-indicator]]:transition-all [&_[data-slot=progress-indicator]]:duration-500"
                    />
                  </div>
                  <div>
                    <div className="flex justify-between text-xs font-bold uppercase mb-1">
                      <span className="flex items-center gap-1"><Star size={11} className="text-rpg-gold"/> Nível {nivel}</span>
                      <span>{xpProximoNivel != null ? `${xp}/${xpProximoNivel} XP` : "XP máximo"}</span>
                    </div>
                    <Progress
                      value={xpProximoNivel != null ? Math.max(0, Math.min(100, (xp / xpProximoNivel) * 100)) : 100}
                      className="h-1.5 bg-gray-900"
                    />
                  </div>
                  <div className="flex justify-between items-center pt-2 border-t border-gray-800/50">
                     <span className="flex items-center gap-2 text-xs text-gray-400 font-bold uppercase"><Shield size={14} className="text-blue-500"/> Defesa</span>
                     <span className="text-blue-200 font-rpg text-lg">{defesa ?? "?"}</span>
                  </div>
              </div>

               {/* Atributos (Sidebar) */}
               <div className="grid grid-cols-3 gap-2">
                  <div className="bg-gray-800/40 p-2 rounded text-center border border-gray-700">
                      <span className="text-[9px] text-gray-500 block">FOR</span>
                      <span className="font-rpg text-gray-200">{attributes.forca}</span>
                  </div>
                  <div className="bg-gray-800/40 p-2 rounded text-center border border-gray-700">
                      <span className="text-[9px] text-gray-500 block">DES</span>
                      <span className="font-rpg text-gray-200">{attributes.destreza}</span>
                  </div>
                  <div className="bg-gray-800/40 p-2 rounded text-center border border-gray-700">
                      <span className="text-[9px] text-gray-500 block">INT</span>
                      <span className="font-rpg text-gray-200">{attributes.inteligencia}</span>
                  </div>
              </div>

              {/* Missão */}
              {quest && (
                  <div className="bg-blue-900/10 border border-blue-900/30 p-3 rounded relative">
                      <h3 className="text-[10px] text-blue-400 uppercase font-bold mb-1 tracking-widest flex items-center gap-2"><Map size={12}/> Missão</h3>
                      <p className="text-sm text-blue-100 font-serif leading-tight">{quest.nome_missao}</p>
                      <p className="text-[10px] text-gray-400 mt-1 italic">"{quest.objetivo_missao}"</p>
                  </div>
              )}

              {/* Inventário */}
              <div>
                  <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xs text-gray-500 uppercase font-bold flex items-center gap-2"><Backpack size={12}/> Inventário</h3>
                      <span className="text-xs text-rpg-gold font-rpg flex items-center gap-1"><Coins size={12}/> {ouro}</span>
                  </div>
                  <ul className="text-xs text-gray-400 space-y-1 max-h-40 overflow-y-auto custom-scrollbar">
                      {inventory.length > 0 ? inventory.map((item, i) => (
                          <li key={i} className="border-b border-gray-800 pb-1 flex items-center gap-2 animate-fade-in">
                              <ItemIcon nome={item} />
                              {item}
                          </li>
                      )) : <li className="italic opacity-50">Mochila vazia...</li>}
                  </ul>
              </div>
          </div>
      </div>

      {/* CHAT AREA */}
      <div className="flex-1 flex flex-col relative bg-[#050505]">
        {!showSidebar && (
            <button
                onClick={() => setShowSidebar(true)}
                aria-label="Abrir ficha do personagem"
                className="absolute top-4 left-4 z-40 p-2 bg-black/50 rounded-full text-gray-400 border border-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold"
            ><Menu size={20}/></button>
        )}

        {/* HUD Inimigos — ordem de iniciativa real (Etapa 7, Fase 1): a
            posição vem de `ordemIniciativa` (índices em `enemies`, -1 é o
            herói), calculada uma vez por `combat.iniciar_combate`. Clicar
            num inimigo sugere o alvo na próxima ação — quem decide o alvo
            de verdade continua sendo o texto interpretado pelo modelo
            (ADR-0006), isto só evita digitar o nome à mão. */}
        {combatActive && enemies.length > 0 && !gameOver && (
            <div className="absolute top-0 w-full bg-gradient-to-b from-red-950/90 to-transparent p-2 z-30 flex justify-center gap-4 animate-fade-in shadow-lg">
                <span className="absolute left-4 top-4 text-red-500 font-rpg text-xs animate-pulse flex items-center gap-2"><Sword size={14}/> COMBATE</span>
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
                            className={`relative min-w-[100px] bg-black/80 p-2 rounded border backdrop-blur-sm text-left transition-colors
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
                                    <span className={`text-[9px] font-mono rounded px-1 shrink-0 ${suaVez ? 'bg-rpg-gold text-black' : 'bg-gray-800 text-gray-400'}`}>
                                        {posicao + 1}
                                    </span>
                                )}
                                <span className="text-[10px] font-bold text-red-100 truncate">{en.nome}</span>
                            </div>
                            <div className="h-1 bg-gray-800 rounded-full overflow-hidden"><div className="h-full bg-red-600 transition-all duration-300" style={{ width: `${(en.hp / en.max_hp) * 100}%` }}></div></div>
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
                    return <RollCard key={idx} dados={msg.dados} />;
                }

                const isUser = msg.role === 'user';
                const isSystem = msg.role === 'system';

                if (isSystem) {
                    return (
                        <div key={idx} className="flex justify-center my-2 animate-fade-in">
                            <div className="bg-yellow-900/20 border border-yellow-700/30 text-yellow-500 px-4 py-2 rounded-full text-xs font-mono flex items-center gap-2">
                                <Dices size={12}/> {msg.content}
                            </div>
                        </div>
                    );
                }

                return (
                    <div key={idx} className={`flex items-start gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'} animate-fade-in`}>
                        <div className={`w-9 h-9 rounded-md shrink-0 flex items-center justify-center border shadow-md overflow-hidden ${isUser ? 'border-blue-900 bg-blue-950' : msg.isError ? 'border-amber-700 bg-amber-950' : 'border-gray-700 bg-gray-900'}`}>
                             {isUser ? (
                                 <img src={charImage} className="w-full h-full object-cover" onError={(e) => {e.currentTarget.style.display='none'}}/>
                             ) : msg.isError ? (
                                 <AlertTriangle size={16} className="text-amber-500"/>
                             ) : (
                                 <Dices size={16} className="text-rpg-gold"/>
                             )}
                             {isUser && <User size={16} className="text-blue-400 absolute -z-10"/>}
                        </div>

                        <div className={`max-w-[85%] p-3.5 rounded-lg text-sm md:text-base leading-relaxed shadow-lg backdrop-blur-sm
                            ${isUser
                                ? 'bg-blue-950/40 border border-blue-900/30 text-blue-100 rounded-tr-none'
                                : msg.isError
                                ? 'bg-amber-950/30 border border-amber-800/40 text-amber-200 rounded-tl-none italic'
                                : 'bg-gray-900/60 border border-gray-800 text-gray-300 rounded-tl-none'
                            }`}>
                            <p className="whitespace-pre-wrap break-words">{msg.content}</p>
                            {!isUser && !msg.isError && msg.turnoIndex !== undefined && (
                                <div className="flex gap-2 mt-2 -mb-1">
                                    <button
                                        type="button"
                                        onClick={() => enviarFeedback(idx, msg.turnoIndex!, 1)}
                                        disabled={msg.feedback !== undefined}
                                        aria-label="Gostei desta narração"
                                        className={`p-1 rounded transition-colors ${msg.feedback === 1 ? 'text-emerald-500' : 'text-gray-600 hover:text-emerald-500 disabled:hover:text-gray-600'}`}
                                    ><ThumbsUp size={13}/></button>
                                    <button
                                        type="button"
                                        onClick={() => enviarFeedback(idx, msg.turnoIndex!, -1)}
                                        disabled={msg.feedback !== undefined}
                                        aria-label="Não gostei desta narração"
                                        className={`p-1 rounded transition-colors ${msg.feedback === -1 ? 'text-red-500' : 'text-gray-600 hover:text-red-500 disabled:hover:text-gray-600'}`}
                                    ><ThumbsDown size={13}/></button>
                                </div>
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
            <div className="max-w-4xl mx-auto flex gap-2 bg-black/40 p-1.5 rounded-xl border border-gray-700 focus-within:border-blue-800 transition-colors shadow-inner">
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
                    className="h-10 w-10 bg-gray-800 hover:bg-gray-700 text-rpg-gold rounded-lg flex items-center justify-center transition-all mt-1 mr-1 border border-gray-600 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold disabled:opacity-40"
                >
                    <Send size={18}/>
                </button>
            </div>
        </div>
      </div>
    </div>
  );
}
