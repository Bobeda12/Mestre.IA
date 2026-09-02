import { useState, useEffect, useRef } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { isAxiosError } from 'axios';
import { api, API_URL } from '../lib/api';
import { prefereMovimentoReduzido } from '../lib/acessibilidade';
import { ErroSse, postSse } from '../lib/sse';
import { esconderTagOpcoes, getLocalImage, limparMarkdownLeve, renderizarNarrativa } from '../lib/utils';
import { useAuth } from '../lib/auth';
import { useTrilha, calcularTema } from '../lib/trilha';
import { useSfx } from '../lib/sfx';
import RollCard, { DURACAO_ANIMACAO_DADO_MS, type DadosRolagem } from './RollCard';
import StatusCard, { type EventoStatus } from './StatusCard';
import PixelBar from './PixelBar';
import Prologo from './Prologo';
import PixelIcon, { type PixelIconName } from './PixelIcon';
import PanelFrame from './PanelFrame';
import PixelButton from './PixelButton';
import InventoryGrid from './InventoryGrid';
import Carregando from './Carregando';
import MenuConfiguracao from './MenuConfiguracao';
import PainelRegrasModal from './PainelRegrasModal';
import ConfirmeEmail from './ConfirmeEmail';
import PixelActionCard from './PixelActionCard';
import SistemaFeedbackToast, { type ToastItem } from './SistemaFeedbackToast';
import FloatingCombatText, { type FlutuanteHeroi } from './FloatingCombatText';
import LootRevealOverlay, { type LootAtivo } from './LootRevealOverlay';
import FichaModal from './FichaModal';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';
import HudPersonagem from './HudPersonagem';
import CabecalhoRegiao from './CabecalhoRegiao';
import PixelTooltip from './PixelTooltip';
import DetalheMonstroModal from './DetalheMonstroModal';
import GuiaAventureiro from './GuiaAventureiro';

// Etapa 14 (revisão) — a ficha virou menu de abas estilo JRPG. Antes tudo
// (retrato, barras, atributos, missão, inventário) era uma pilha só numa
// coluna de 320px: ficava espremido e obrigava a rolar pra achar qualquer
// coisa. Três telas curtas leem melhor e é o vocabulário de menu de console.
const ABAS = [
  { id: 'status', rotulo: 'STATUS', icone: 'coracao' },
  { id: 'itens', rotulo: 'ITENS', icone: 'mochila' },
  { id: 'missao', rotulo: 'MISSÃO', icone: 'pergaminho' },
  { id: 'relacoes', rotulo: 'RELAÇÕES', icone: 'rosto' },
  // Fase 3 do remaster UX (PLANO_REMASTER_UX.md) — "Bestiário": só os
  // monstros encontrados NESTA sessão (o backend não guarda um histórico
  // de abates por personagem, então não dá pra prometer um bestiário que
  // sobrevive a um recarregar de página — ver comentário na aba abaixo).
  { id: 'bestiario', rotulo: 'BESTIÁRIO', icone: 'caveira' },
] as const satisfies readonly { id: string; rotulo: string; icone: PixelIconName }[];
// "Regras" saiu daqui na correção de UX pós Fase 1 — a faixa de abas estava
// cheia demais. Virou um botão dedicado ("Manual do Jogo", ícone `dado`
// reaproveitado) que abre PainelRegrasModal em tela cheia — ver esse arquivo
// e os botões perto de setConfigAberta/setManualAberto mais abaixo.

type AbaFicha = (typeof ABAS)[number]['id'];

// Pendência do remaster UX resolvida (PLANO_REMASTER_UX.md, item 2) —
// espelha `rules_engine.periodo_do_dia` (Backend/app/services/
// rules_engine.py): mesmos limiares, só que do lado que exibe, não do que
// decide. `w_state.hora_do_dia` é a fonte da verdade; isto só traduz.
function periodoDoDia(hora: number): string {
  const h = ((hora % 24) + 24) % 24;
  if (h < 6) return 'madrugada';
  if (h < 12) return 'manhã';
  if (h < 18) return 'tarde';
  return 'noite';
}

// Ordem e siglas dos atributos, na mesma sequência da ficha de criação.
const ATRIBUTOS = [
  ['forca', 'FOR'], ['destreza', 'DES'], ['constituicao', 'CON'],
  ['inteligencia', 'INT'], ['sabedoria', 'SAB'], ['carisma', 'CAR'],
] as const;

// Fase 4 do remaster UX (PLANO_REMASTER_UX.md) — "o jogador nunca deve se
// sentir perdido": passar o mouse num atributo explica o modificador e pra
// que ele serve, no mesmo espírito das siglas CD/CA que RollCard.tsx já
// explica em tooltip. Nome completo + uso reaproveitado por ATRIBUTOS
// acima (mesma sigla como chave).
const ATRIBUTOS_INFO: Record<(typeof ATRIBUTOS)[number][0], { nome: string; uso: string }> = {
  forca: { nome: 'Força', uso: 'Ataques corpo a corpo e testes de atletismo.' },
  destreza: { nome: 'Destreza', uso: 'Ataques à distância, furtividade e Classe de Armadura.' },
  constituicao: { nome: 'Constituição', uso: 'Pontos de vida e resistência a venenos e fadiga.' },
  inteligencia: { nome: 'Inteligência', uso: 'Conhecimento, investigação e magias de Mago.' },
  sabedoria: { nome: 'Sabedoria', uso: 'Percepção, intuição e magias de Clérigo/Druida.' },
  carisma: { nome: 'Carisma', uso: 'Persuasão, intimidação e magias de Bardo/Feiticeiro.' },
};

type Message =
  // `turnoIndex` (Etapa 9) chega no frame SSE "state", junto do resto do
  // HUD — é a posição desta narração em `historico_chat` no servidor
  // (Personagem.historico_chat), o que o botão 👍/👎 manda pra
  // POST /personagens/:id/feedback. `feedback` é só o que ESTE navegador já
  // votou, pra não deixar votar duas vezes na mesma aba.
  // `raw` (Fase 1, revisão de gameplay) só existe em bolhas de assistente
  // em streaming: o texto CRU acumulado, nunca limpo/truncado — precisa
  // viver no estado (não numa ref) porque o updater de `setMessages` roda
  // puro a partir de `prev`; uma ref mutada dentro do updater duplica
  // texto sob o StrictMode do React (chama o updater duas vezes).
  // `id` (rodada de conserto) — chave estável pro `key` do React, em vez
  // do índice do array. Hoje o log só cresce por trás (nunca reordena nem
  // remove do meio), então `key={idx}` funcionava; mas o reenvio em modo
  // de emergência (ver `tentarComChaveDoServidor`) passou a poder cortar
  // mensagens do fim da lista, e qualquer feature futura que remova do
  // meio reiniciaria a animação de todo card vizinho sem isto.
  | { kind: 'texto'; id: number; role: 'user' | 'assistant' | 'system'; content: string; raw?: string; isError?: boolean; turnoIndex?: number; feedback?: 1 | -1 }
  // Etapa 10 (A-7): cura e morte de inimigo chegam pelo mesmo frame
  // `tool_event` que ataque/teste, só com um `dados.tipo` diferente.
  | { kind: 'rolagem'; id: number; dados: DadosRolagem | EventoStatus };

// Espelha domain/state.py:Inimigo (só os campos que o HUD lê).
interface Inimigo {
  nome: string;
  hp: number;
  max_hp: number;
  ca: number;
  // Rodada de conserto (Parte 2, item I) — já vinha do backend
  // (`domain/state.py:Inimigo`, preenchido a partir de `data/monsters.json`
  // desde a Fase 0 da revisão de gameplay) sem nenhum consumidor na tela.
  // Descreve o ESTILO de luta do inimigo (ex: "Covarde. Ataca e foge"), não
  // a próxima ação exata — é o dado que já existe, não uma previsão nova.
  comportamento?: string;
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
  // Fase 1 (revisão de gameplay) — testes de morte visíveis. Antes disto o
  // front não sabia diferenciar "caído, em teste de morte" de "morto de
  // verdade" — os dois eram só `hp_atual <= 0`.
  sucessos_morte?: number;
  falhas_morte?: number;
  resultado_combate?: 'vitoria' | 'morte' | 'estabilizado' | null;
  // Fase 1 — as 3 sugestões de ação extraídas da tag [OPCOES].
  opcoes?: string[];
  // Fase 7 (revisão de gameplay) — gerado uma vez quando resultado_combate
  // vira "morte"; já vem preenchido no mesmo frame que confirma a morte
  // (o servidor gera antes de narrar o turno).
  epitafio?: { retrospectiva: string; epitafio_curto: string } | null;
  // Fase 8 — a ferramenta ajustar_reputacao_npc (Etapa 5) já existia sem
  // nenhum consumidor no frontend.
  reputacao_npcs?: Record<string, number>;
  inventory?: string[];
  combat_active: boolean;
  inimigos?: Inimigo[];
  missao?: unknown;
  turno_index?: number;
  // Etapa 11 (B-6) — turno do MUNDO (world_state.turno), não o turno da
  // rodada de combate (`turno_atual`, que reseta a cada luta): é o que a
  // tela de morte usa pra mostrar "quantos turnos você viveu".
  turno_mundo?: number;
  // Pendência do remaster UX (PLANO_REMASTER_UX.md) — antes só chegavam no
  // carregamento (`CargaJogo`); agora o backend manda em todo frame
  // `state` (routers/game.py:_resposta), então local/clima já não ficam
  // desatualizados depois de uma viagem no meio da sessão.
  local?: string;
  clima?: string | null;
  // Item 2 — hora do dia (0-23), avança por ação lógica no backend
  // (mover/descansar em services/tools.py), não por turno.
  hora_do_dia?: number;
  // Item 1 — as três flags táticas de CombatState, sem consumidor até aqui.
  heroi_escondido?: boolean;
  heroi_bonus_ca?: number;
  heroi_vantagem_inimiga?: boolean | null;
  // Item 3 — bestiário persistente: nome do bestiário -> quantas vezes já
  // morreu para ESTE herói, ao longo de toda a vida do personagem (não só
  // desta sessão de jogo, ao contrário do rascunho anterior).
  monstros_derrotados?: Record<string, number>;
  // Item 4 — Hall da Fama: `null`/`null` enquanto o herói está vivo.
  morto_em?: string | null;
  pontuacao_final?: number | null;
}

interface CargaJogo extends EstadoJogo {
  nome: string;
  raca: string;
  classe: string;
  local: string;
  atributos?: Record<string, number>;
  imagem?: string | null;
  // Etapa 11 (B-7) — tela de abertura da campanha.
  background?: string | null;
  objetivo?: string | null;
  historia_texto?: string | null;
  historico_chat?: { role: string; content: string }[];
  // Rodada de conserto (Parte 2, item G) — "Anteriormente…": recap curto
  // do resumo rolante, `null` quando não há nada resumido ainda.
  anteriormente?: string | null;
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
  const [configAberta, setConfigAberta] = useState(false);
  const [manualAberto, setManualAberto] = useState(false);
  // Item 11 da rodada de polish pós-remaster — onboarding conceitual.
  const [guiaAberto, setGuiaAberto] = useState(false);
  // Item 10 — nome do monstro cuja "página de bestiário" está aberta,
  // `null` quando fechado.
  const [monstroDetalheAberto, setMonstroDetalheAberto] = useState<string | null>(null);
  const [atributoInspecionado, setAtributoInspecionado] = useState<(typeof ATRIBUTOS)[number][0] | null>(null);
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
  // Fase 8 (revisão de gameplay) — cards de atitude de NPC.
  const [reputacoes, setReputacoes] = useState<Record<string, number>>({});
  // Fase 2 do remaster UX (PLANO_REMASTER_UX.md) — card de Mundo/Clima da
  // sidebar. `local`/`clima` só chegam no carregamento (CargaJogo), não em
  // todo frame `state` — o backend hoje não manda local/clima por turno,
  // só `turno_mundo`. Fica como retrato do início da sessão: se o herói
  // viajar no meio dela, o card só atualiza no próximo load da página. O
  // resumo rolante ("Jornada até aqui") é o mesmo `anteriormente` que já
  // existe pro recap do log — antes só virava uma bolha de sistema, agora
  // também fica disponível pro accordion da ficha.
  const [localAtual, setLocalAtual] = useState('');
  const [climaAtual, setClimaAtual] = useState('');
  const [resumoJornada, setResumoJornada] = useState<string | null>(null);
  const [jornadaAberta, setJornadaAberta] = useState(false);
  // Fase 3 do remaster UX — FichaModal.tsx precisa de origem/objetivo/
  // história, os mesmos três campos que a tela de Prólogo já usa direto de
  // `cargaJogo`; copiados pro estado local pelo mesmo motivo dos outros
  // campos acima (o resto do componente nunca lê `cargaJogo` depois do
  // primeiro carregamento, só o snapshot local).
  const [origemAtual, setOrigemAtual] = useState<string | null>(null);
  const [objetivoAtual, setObjetivoAtual] = useState<string | null>(null);
  const [historiaAtual, setHistoriaAtual] = useState<string | null>(null);
  const [fichaModalAberta, setFichaModalAberta] = useState(false);
  // Pendência do remaster UX resolvida — "Bestiário": `monstrosDerrotados`
  // agora é o dado real e persistente do backend (Personagem.
  // monstros_derrotados, incrementado só em ToolExecutor._conceder_xp).
  // `monstrosAvistados` continua sendo um registro só desta sessão — não
  // existe endpoint que exponha o catálogo completo de monstros
  // (`data/monsters.json` é só do servidor), então "visto mas não morto"
  // só é rastreável enquanto o inimigo está na tela. (o efeito que popula
  // isto vive mais abaixo, depois de `enemies` ser declarado.)
  const [monstrosDerrotados, setMonstrosDerrotados] = useState<Record<string, number>>({});
  const [monstrosAvistados, setMonstrosAvistados] = useState<Set<string>>(new Set());
  // Pendência do remaster UX — item 1: as três flags táticas de
  // CombatState, sem consumidor visual até aqui.
  const [heroiEscondido, setHeroiEscondido] = useState(false);
  const [heroiBonusCa, setHeroiBonusCa] = useState(0);
  const [heroiVantagemInimiga, setHeroiVantagemInimiga] = useState<boolean | null>(null);
  // Pendência do remaster UX — item 2: hora do dia (0-23), vem do backend.
  const [horaDoDia, setHoraDoDia] = useState<number | null>(null);
  // Pendência do remaster UX — item 4: Hall da Fama.
  const [mortoEm, setMortoEm] = useState<string | null>(null);
  const [pontuacaoFinal, setPontuacaoFinal] = useState<number | null>(null);

  // COMBATE
  const [combatActive, setCombatActive] = useState(false);
  const [enemies, setEnemies] = useState<Inimigo[]>([]);
  useEffect(() => {
    if (enemies.length === 0) return;
    setMonstrosAvistados(prev => {
      const novos = enemies.map(en => en.nome).filter(nome => !prev.has(nome));
      if (novos.length === 0) return prev;
      const copia = new Set(prev);
      novos.forEach(nome => copia.add(nome));
      return copia;
    });
  }, [enemies]);
  const [ordemIniciativa, setOrdemIniciativa] = useState<number[]>([]);
  const [turnoAtual, setTurnoAtual] = useState(0);
  const [turnoMundo, setTurnoMundo] = useState(0);
  const [gameOver, setGameOver] = useState(false);
  // Fase 1 da revisão de gameplay — o momento mais tenso do jogo (herói a
  // 0 PV, três falhas = morte) já era calculado no backend e nunca chegava
  // à tela; agora vem em todo frame "state" (routers/game.py:_resposta).
  const [sucessosMorte, setSucessosMorte] = useState(0);
  const [falhasMorte, setFalhasMorte] = useState(0);
  // As 3 sugestões de ação da narração ([OPCOES], Fase 1) — nunca aparecem
  // como texto (GameChat esconde a tag ao vivo, o servidor a remove antes
  // de persistir); viram botões que preenchem a caixa de texto livre, sem
  // enviar sozinhos — o jogador ainda decide a frase final.
  const [opcoes, setOpcoes] = useState<string[]>([]);
  // Fase 7 — a retrospectiva/epitáfio gerados quando o herói morre de
  // verdade (resultado_combate === 'morte').
  const [epitafio, setEpitafio] = useState<{ retrospectiva: string; epitafio_curto: string } | null>(null);
  // Etapa 11 (B-7) — a tela de abertura aparece só na primeira visita
  // (historico_chat ainda com só o prólogo, nenhum turno jogado) e some
  // pro resto da sessão assim que o jogador clica "Começar" — não volta a
  // cada re-render, só se a página for recarregada antes do 1º turno.
  const [prologoConcluido, setPrologoConcluido] = useState(false);
  // Dano flutuante (Etapa 7) — `idx` é a posição no array `enemies`, não o
  // nome (dois inimigos podem ter o mesmo nome).
  const [danosFlutuantes, setDanosFlutuantes] = useState<{ id: number; valor: number; idx: number }[]>([]);
  // Fase 3 do remaster UX (PLANO_REMASTER_UX.md) — generaliza o dano
  // flutuante pro HERÓI: cura (verde) e XP ganho (dourado), ancorados nos
  // ícones de coração/estrela da faixa de vitais. Ouro já tem o toast da
  // Fase 1 (não existe ícone de ouro fixo na faixa hoje — duplicar o
  // feedback ali seria ruído, não reforço).
  const [flutuantesHeroi, setFlutuantesHeroi] = useState<(FlutuanteHeroi & { alvo: 'hp' | 'xp' })[]>([]);
  const spawnFlutuanteHeroi = (alvo: 'hp' | 'xp', texto: string, cor: string) => {
    const id = Date.now() + Math.random();
    setFlutuantesHeroi(prev => [...prev, { id, alvo, texto, cor }]);
    setTimeout(() => setFlutuantesHeroi(prev => prev.filter(f => f.id !== id)), 1200);
  };

  // Fase 3 do remaster UX — fila de loot: cada item novo do `state` entra
  // na fila, e um efeito abaixo mostra um de cada vez em LootRevealOverlay
  // (`dar_item` pode, em teoria, entregar mais de um item no mesmo turno —
  // mostrar todos ao mesmo tempo empilhado não seria a mesma dose de
  // dopamina que o documento de design pede).
  const [lootQueue, setLootQueue] = useState<string[]>([]);
  const [lootAtivo, setLootAtivo] = useState<LootAtivo | null>(null);
  useEffect(() => {
    if (!lootAtivo && lootQueue.length > 0) {
      setLootAtivo({ id: Date.now(), item: lootQueue[0] });
      setLootQueue(prev => prev.slice(1));
    }
  }, [lootQueue, lootAtivo]);

  // Fase 1 do remaster UX (PLANO_REMASTER_UX.md) — "Feedback Visual de
  // Sistema": ouro/item mudando não gera hoje nenhum tool_event dedicado
  // (só ataque/teste/dano/morte/cura têm tipo próprio) — o sinal que temos
  // é o diff do frame `state` contra o valor local anterior, o mesmo truque
  // já usado abaixo pra `danosFlutuantes`. `toastIdRef` evita colidir com
  // `proximoIdMsg()` (namespaces de id diferentes, sem relação com mensagens).
  const [toasts, setToasts] = useState<ToastItem[]>([]);
  const toastIdRef = useRef(0);
  const pushToast = (icone: ToastItem['icone'], texto: string, tom: ToastItem['tom'] = 'neutro') => {
    const id = ++toastIdRef.current;
    setToasts(prev => [...prev, { id, icone, texto, tom }]);
    setTimeout(() => setToasts(prev => prev.filter(t => t.id !== id)), 3200);
  };

  // EFEITOS
  const [shakeScreen, setShakeScreen] = useState(false);
  const [wasDamaged, setWasDamaged] = useState(false);
  // Fase 2 do remaster UX — glow dourado na barra de XP ao subir de nível.
  // `nivelAnteriorRef` guarda o nível já visto pra detectar só o AUMENTO
  // (o `state` de recarregar a página também traz `nivel`, e isso não é
  // level up — sem a ref, o efeito abaixo dispararia glow em toda visita).
  const [levelUpGlow, setLevelUpGlow] = useState(false);
  const nivelAnteriorRef = useRef(nivel);
  useEffect(() => {
    if (nivel > nivelAnteriorRef.current) {
      setLevelUpGlow(true);
      sfx.tocar('levelup');
      const t = setTimeout(() => setLevelUpGlow(false), 1300);
      nivelAnteriorRef.current = nivel;
      return () => clearTimeout(t);
    }
    nivelAnteriorRef.current = nivel;
  }, [nivel]);

  // CONVITE PRA REIVINDICAR (Etapa 10, A-1) — só aparece pra convidado
  // (`usuario.email === null`), depois do primeiro momento bom: o primeiro
  // combate resolvido sem morrer, ou 8 turnos jogados (proxy pro "fim da
  // primeira cena"), o que vier primeiro. `combateFoiAtivoRef` é o que
  // permite detectar "combate que acabou" sem um campo de vitória dedicado
  // no backend — combatActive true → false, sem game over, é a transição.
  const { usuario } = useAuth();
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
  // Revisão registro-sem-estado — POST /auth/reivindicar não grava mais nada
  // no banco na hora (só quando o link do e-mail é confirmado), então o
  // modal não pode fechar como se a conta já existisse: mostra a mesma tela
  // "confirme seu e-mail" do registro comum antes de dar por encerrado.
  const [reivindicarPendente, setReivindicarPendente] = useState<string | null>(null);
  const [reivindicarReenviado, setReivindicarReenviado] = useState(false);

  // BYOK (Etapa 15) — dois avisos distintos, cada um do seu lado do fluxo:
  // `modalTetoAberto` aparece quando a COTA COMPARTILHADA do servidor
  // acabou por hoje (antes de qualquer chamada à IA — vem do `postSse`
  // rejeitando o POST); `modalEmergenciaAberto` aparece quando é a CHAVE
  // PRÓPRIA do jogador que falhou no meio de um turno (vem do frame SSE
  // `erro`) — os dois têm causas e ações diferentes, por isso não são o
  // mesmo modal com texto trocado.
  const [modalTetoAberto, setModalTetoAberto] = useState(false);
  const [modalEmergenciaAberto, setModalEmergenciaAberto] = useState(false);
  const [mensagemEmergencia, setMensagemEmergencia] = useState('');
  const ultimaAcaoRef = useRef('');
  // Rodada de conserto — contador monotônico pro `id` de cada mensagem
  // nova (ver o comentário no tipo `Mensagem` acima).
  const proximoIdMsgRef = useRef(0);
  const proximoIdMsg = () => proximoIdMsgRef.current++;

  useEffect(() => {
    if (combatActive) combateFoiAtivoRef.current = true;
    else if (combateFoiAtivoRef.current && !gameOver) setPrimeiroCombateResolvido(true);
  }, [combatActive, gameOver]);

  // Etapa 11 (B-4) — trilha por tema. O tema é derivado do estado (combate,
  // HP baixo, game over), nunca pedido ao modelo.
  const temaMusical = calcularTema({ gameOver, combateAtivo: combatActive, hpAtual, hpMax });
  const trilha = useTrilha(temaMusical);
  const sfx = useSfx();

  // Item 9 da rodada de polish pós-remaster — vida ≤10% dispara a tela
  // piscando vermelho em loop contínuo (decisão aprovada: para só quando a
  // vida sobe do patamar ou o jogo acaba), distinto do flash de um tiro só
  // de `wasDamaged`. `hpAtual > 0` evita o pisca continuar por cima da tela
  // de GAME OVER.
  const hpCritico = hpMax > 0 && hpAtual > 0 && hpAtual / hpMax <= 0.10;

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

  const reivindicar = async (e?: React.FormEvent) => {
    e?.preventDefault();
    setReivindicarEnviando(true);
    setReivindicarErro(null);
    try {
      await api.post('/auth/reivindicar', { email: reivindicarEmail, senha: reivindicarSenha });
      // Nada foi gravado no banco ainda — só quando o link do e-mail for
      // confirmado. Se já estava mostrando a tela de confirmação, este
      // sucesso é um reenvio; senão é o primeiro envio.
      if (reivindicarPendente) {
        setReivindicarReenviado(true);
      } else {
        setReivindicarPendente(reivindicarEmail);
      }
    } catch (err) {
      const detalhe = isAxiosError<{ detail?: string }>(err) ? err.response?.data?.detail : undefined;
      setReivindicarErro(detalhe ?? 'Não deu para criar a conta. Confira o e-mail e a senha.');
    } finally {
      setReivindicarEnviando(false);
    }
  };

  const fecharModalReivindicar = () => {
    setModalReivindicarAberto(false);
    setReivindicarPendente(null);
    setReivindicarReenviado(false);
    dispensarConvite();
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
    // Fase 2 do remaster UX — sem isto, carregar um personagem que já
    // estava acima do nível 1 disparava o glow (e agora o som) de "subiu de
    // nível" no load: `nivelAnteriorRef` nascia em 1 (valor inicial do
    // `useState`) e via o nível carregado como um AUMENTO. Reprimir a ref
    // aqui, no mesmo lugar que carrega o nível, evita o falso positivo sem
    // acoplar o efeito de level up à lógica de carregamento.
    nivelAnteriorRef.current = cargaJogo.nivel ?? 1;
    setXp(cargaJogo.xp ?? 0);
    setXpProximoNivel(cargaJogo.xp_proximo_nivel ?? null);
    setSucessosMorte(cargaJogo.sucessos_morte ?? 0);
    setFalhasMorte(cargaJogo.falhas_morte ?? 0);
    setEpitafio(cargaJogo.epitafio ?? null);
    setReputacoes(cargaJogo.reputacao_npcs || {});
    setInventory(cargaJogo.inventory || []);
    setAttributes(cargaJogo.atributos || {});
    setQuest(cargaJogo.missao);
    setLocalAtual(cargaJogo.local ?? '');
    setClimaAtual(cargaJogo.clima ?? '');
    setResumoJornada(cargaJogo.anteriormente ?? null);
    setMonstrosDerrotados(cargaJogo.monstros_derrotados ?? {});
    setHeroiEscondido(cargaJogo.heroi_escondido ?? false);
    setHeroiBonusCa(cargaJogo.heroi_bonus_ca ?? 0);
    setHeroiVantagemInimiga(cargaJogo.heroi_vantagem_inimiga ?? null);
    if (cargaJogo.hora_do_dia !== undefined) setHoraDoDia(cargaJogo.hora_do_dia);
    setMortoEm(cargaJogo.morto_em ?? null);
    setPontuacaoFinal(cargaJogo.pontuacao_final ?? null);
    setOrigemAtual(cargaJogo.background ?? null);
    setObjetivoAtual(cargaJogo.objetivo ?? null);
    setHistoriaAtual(cargaJogo.historia_texto ?? null);
    setCombatActive(cargaJogo.combat_active);
    setEnemies(cargaJogo.inimigos || []);
    setOrdemIniciativa(cargaJogo.ordem_iniciativa || []);
    setTurnoAtual(cargaJogo.turno_atual ?? 0);
    setTurnoMundo(cargaJogo.turno_mundo ?? 0);

    if (cargaJogo.resultado_combate === 'morte') setGameOver(true);

    // Rodada de conserto (Parte 2, item G) — antes disto, recarregar uma
    // partida em andamento jogava fora a conversa inteira e mostrava só
    // "Conectado ao mundo": `historico_chat` já guardava tudo, gerado com
    // capricho pelo narrador, e nunca chegava à tela. `historico_chat[0]`
    // é o texto do prólogo — a tela `Prologo` mostra ele com efeito de
    // digitação na primeira visita (ver `primeiroTurno` abaixo), mas depois
    // de "Começar" esse texto nunca mais aparecia em lugar nenhum: nem essa
    // primeira versão do fix trazia ele de volta pro log persistente, só os
    // turnos jogados depois dele. Agora ele sempre entra como a primeira
    // bolha — é a história que o jogador acabou de ler, não devia sumir do
    // scrollback assim que a tela de abertura fecha.
    const historico = cargaJogo.historico_chat ?? [];
    if (historico.length === 0) {
      setMessages([{ kind: 'texto', id: proximoIdMsg(), role: 'assistant', content: `Conectado ao mundo. Local: ${cargaJogo.local}.` }]);
    } else {
      const JANELA_HISTORICO = 12;
      const turnosJogados = historico.slice(1);
      const recentes = turnosJogados.slice(-JANELA_HISTORICO);
      const bolhas: Message[] = [
        { kind: 'texto', id: proximoIdMsg(), role: 'assistant', content: historico[0].content },
      ];
      // "Anteriormente…" só aparece quando a janela de fato cortou algo —
      // senão o histórico completo já está logo abaixo, e recapitular o
      // que o jogador está prestes a ler de novo seria redundante.
      if (cargaJogo.anteriormente && turnosJogados.length > recentes.length) {
        bolhas.push({
          kind: 'texto', id: proximoIdMsg(), role: 'system',
          content: `Anteriormente: ${cargaJogo.anteriormente}`,
        });
      }
      // Índice de `recentes[0]` dentro de `historico_chat` de verdade — é
      // o que o 👍/👎 (POST /personagens/:id/feedback) espera em `turnoIndex`.
      const offsetNoHistorico = 1 + (turnosJogados.length - recentes.length);
      recentes.forEach((m, i) => {
        const role = m.role === 'user' ? 'user' : 'assistant';
        bolhas.push({
          kind: 'texto', id: proximoIdMsg(), role, content: m.content,
          turnoIndex: role === 'assistant' ? offsetNoHistorico + i : undefined,
        });
      });
      setMessages(bolhas);
    }
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
        const raw = (ultima.raw ?? ultima.content) + pedaco;
        const copia = [...prev];
        // Etapa 10 (A-7) + Fase 1 (revisão de gameplay): limpeza leve sobre
        // o texto CRU acumulado, nunca só o pedaço novo — um `**` ou a tag
        // `[OPCOES` podem chegar partidos entre dois frames SSE. A limpeza
        // de verdade (markdown e a tag [OPCOES]) é no servidor, antes de
        // persistir; isto é só pra tela não piscar por meio segundo. `raw`
        // precisa viver na mensagem (não numa ref) porque este updater
        // roda puro a partir de `prev` — uma ref mutada aqui dentro
        // duplicaria texto sob o StrictMode do React.
        copia[copia.length - 1] = { ...ultima, raw, content: limparMarkdownLeve(esconderTagOpcoes(raw)), isError };
        return copia;
      }
      return [...prev, { kind: 'texto', id: proximoIdMsg(), role: 'assistant', raw: pedaco, content: limparMarkdownLeve(esconderTagOpcoes(pedaco)), isError }];
    });
  };

  const sendAction = async (text: string, opts?: { modoEmergencia?: boolean }) => {
    if (!sessionId || gameOver) return;
    ultimaAcaoRef.current = text;
    // Reenvio em modo de emergência (Etapa 15, BYOK): a ação já apareceu na
    // tela como bolha do jogador na tentativa original — não duplica aqui.
    if (!opts?.modoEmergencia) setMessages(prev => [...prev, { kind: 'texto', id: proximoIdMsg(), role: 'user', content: text }]);
    setLoading(true);
    setOpcoes([]); // as sugestões do turno anterior não valem mais pro novo turno

    try {
      const stream = await postSse(`${API_URL}/chat/stream`, { session_id: sessionId, action: text }, opts);

      for await (const evt of stream) {
        if (evt.event === 'token') {
          acrescentarTexto((evt.data as { texto: string }).texto);
        } else if (evt.event === 'tool_event') {
          // Etapa 10 (A-7): cura e morte de inimigo chegam pelo mesmo
          // frame, discriminados por `dados.tipo` na hora de renderizar.
          const dadosEvento = evt.data as DadosRolagem | EventoStatus;
          setMessages(prev => [...prev, { kind: 'rolagem', id: proximoIdMsg(), dados: dadosEvento }]);
          // Fase 4 do remaster UX (PLANO_REMASTER_UX.md) — som de dado em
          // toda rolagem estruturada (ataque/teste), não só nas de combate.
          if ('d20' in dadosEvento && dadosEvento.d20 != null) sfx.tocar('dado');
          // Fase 8 (revisão de gameplay) — "fator cassino": segura o
          // consumo do stream (então a narração que vem a seguir) pela
          // mesma duração da animação do dado em RollCard.tsx, pra ela
          // nunca aparecer resolvida antes do dado "parar de girar".
          // Rodada de conserto — quem pediu menos movimento no sistema não
          // via o dado girar (a animação CSS já morre em `index.css`), mas
          // continuava esperando os mesmos 700ms à toa — a narração parecia
          // travar sem nenhum giro pra justificar. `RollCard` já revela o
          // resultado na hora nesse caso; a espera aqui acompanha.
          if ('d20' in dadosEvento && dadosEvento.d20 != null && !prefereMovimentoReduzido()) {
            await new Promise(resolve => setTimeout(resolve, DURACAO_ANIMACAO_DADO_MS));
          }
        } else if (evt.event === 'correcao') {
          // O guardrail reescreveu a narrativa depois de já ter sido
          // mostrada ao vivo — a versão persistida (memória futura) é a
          // corrigida, então a tela também passa a refletir ela.
          //
          // Rodada de conserto — o backend já limpa e extrai a tag antes
          // de mandar este frame (game.py), mas a mesma limpeza aqui é uma
          // segunda defesa: a tag crua na tela é o pior sintoma possível
          // (expõe a tripa do prompt), então blindar o cliente também vale
          // a pena mesmo com o backend corrigido. `raw` precisa acompanhar
          // `content` — senão o próximo pedaço de `token` (se algum ainda
          // chegar) reconstruiria a versão suja a partir do `raw` antigo.
          const narrativaCorrigida = (evt.data as { narrativa: string }).narrativa;
          const narrativaLimpa = limparMarkdownLeve(esconderTagOpcoes(narrativaCorrigida));
          setMessages(prev => {
            const copia = [...prev];
            for (let i = copia.length - 1; i >= 0; i--) {
              const m = copia[i];
              if (m.kind === 'texto' && m.role === 'assistant') {
                copia[i] = { ...m, content: narrativaLimpa, raw: narrativaLimpa };
                break;
              }
            }
            return copia;
          });
        } else if (evt.event === 'erro') {
          // Etapa 10 (A-7): mensagem de sistema, sem `*(...)*` — a bolha
          // com `isError=true` já é visualmente distinta (ícone e cor
          // âmbar), não precisa de asterisco pra parecer "fora da narração".
          const dadosErro = evt.data as { mensagem: string; codigo?: string };
          acrescentarTexto(dadosErro.mensagem, true);
          // BYOK (Etapa 15) — só a CHAVE PRÓPRIA do jogador falha assim, no
          // meio de um turno já em andamento (a chave do servidor cai na
          // cadeia de fallback, que já tenta outro modelo sozinha). Oferece
          // usar a do servidor "por enquanto" em vez de deixar o jogador
          // preso sem saber o que fazer.
          if (dadosErro.codigo === 'chave_usuario_falhou') {
            setMensagemEmergencia(dadosErro.mensagem);
            setModalEmergenciaAberto(true);
          }
        } else if (evt.event === 'state') {
          const d = evt.data as EstadoJogo;
          if (d.hp_atual !== undefined && d.hp_atual < hpAtual) {
              setWasDamaged(true); setShakeScreen(true);
              setTimeout(() => { setWasDamaged(false); setShakeScreen(false); }, 500);
              spawnFlutuanteHeroi('hp', `-${hpAtual - d.hp_atual}`, 'text-red-400');
              sfx.tocar('golpe');
          } else if (d.hp_atual !== undefined && d.hp_atual > hpAtual) {
              spawnFlutuanteHeroi('hp', `+${d.hp_atual - hpAtual}`, 'text-emerald-400');
          }
          setHpAtual(d.hp_atual); setHpMax(d.hp_max || hpMax);
          if (d.defesa !== undefined) setDefesa(d.defesa);
          if (d.ouro !== undefined) {
            if (d.ouro !== ouro) {
              const delta = d.ouro - ouro;
              pushToast('moeda', `${delta > 0 ? '+' : ''}${delta} Ouro`, delta > 0 ? 'positivo' : 'negativo');
            }
            setOuro(d.ouro);
          }
          if (d.nivel !== undefined) setNivel(d.nivel);
          // XP some (reseta) quando sobe de nível — nesse turno o "delta"
          // seria negativo e sem sentido pro jogador (o glow da barra já
          // celebra o level up sozinho, não precisa de número aqui).
          if (d.xp !== undefined) {
            if (d.nivel === nivel && d.xp > xp) {
              spawnFlutuanteHeroi('xp', `+${d.xp - xp}`, 'text-rpg-gold');
            }
            setXp(d.xp);
          }
          if (d.xp_proximo_nivel !== undefined) setXpProximoNivel(d.xp_proximo_nivel);
          if (d.inventory) {
            // Fase 3 do remaster UX — item novo ganhou a animação de loot
            // (LootRevealOverlay) no lugar do toast simples da Fase 1; ouro
            // continua no toast (não é um objeto com ícone próprio pra
            // justificar a cena inteira).
            const itensNovos = d.inventory.filter(item => !inventory.includes(item));
            if (itensNovos.length > 0) {
              setLootQueue(prev => [...prev, ...itensNovos]);
              sfx.tocar('item');
            }
          }
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
          setSucessosMorte(d.sucessos_morte ?? 0);
          setFalhasMorte(d.falhas_morte ?? 0);
          if (d.epitafio) setEpitafio(d.epitafio);
          if (d.reputacao_npcs) setReputacoes(d.reputacao_npcs);
          setOpcoes(d.opcoes || []);
          if (d.turno_mundo !== undefined) setTurnoMundo(d.turno_mundo);
          if (d.missao) setQuest(d.missao);
          // Pendências do remaster UX — o backend agora manda estes campos
          // em todo frame `state` (antes só no load), então local/clima/
          // hora do dia já não ficam presos no valor do início da sessão.
          if (d.local !== undefined) setLocalAtual(d.local);
          if (d.clima !== undefined) setClimaAtual(d.clima ?? '');
          if (d.hora_do_dia !== undefined) setHoraDoDia(d.hora_do_dia);
          if (d.heroi_escondido !== undefined) setHeroiEscondido(d.heroi_escondido);
          if (d.heroi_bonus_ca !== undefined) setHeroiBonusCa(d.heroi_bonus_ca);
          if (d.heroi_vantagem_inimiga !== undefined) setHeroiVantagemInimiga(d.heroi_vantagem_inimiga);
          if (d.monstros_derrotados) setMonstrosDerrotados(d.monstros_derrotados);
          if (d.morto_em !== undefined) setMortoEm(d.morto_em);
          if (d.pontuacao_final !== undefined) setPontuacaoFinal(d.pontuacao_final);
          if (d.resultado_combate === 'morte') setGameOver(true);

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
      // BYOK (Etapa 15) — este é o teto da COTA COMPARTILHADA (checado
      // antes da stream abrir, por isso chega aqui e não no frame `erro`
      // acima). Oferece a própria chave como saída, em vez de só dizer
      // "volte amanhã".
      if (err instanceof ErroSse && err.codigo === 'teto_diario_atingido') {
        setModalTetoAberto(true);
      }
    }
    finally { setLoading(false); }
  };

  const tentarComChaveDoServidor = () => {
    setModalEmergenciaAberto(false);
    // Rodada de conserto — o turno que falhou pode ter deixado destroços no
    // log: um card de rolagem que "aconteceu" na tela mas nunca foi
    // persistido (o servidor devolve erro antes do `db.commit()`), e a
    // bolha de erro em si. Sem limpar isso, o reenvio parece que o jogo
    // trapaceou (um dado rolou, sumiu, e rolou de novo com outro número).
    // A ação do jogador nunca se perde — já está em `ultimaAcaoRef`.
    setMessages(prev => {
      const ultimoIndiceDoJogador = prev.findLastIndex(m => m.kind === 'texto' && m.role === 'user');
      return ultimoIndiceDoJogador === -1 ? prev : prev.slice(0, ultimoIndiceDoJogador + 1);
    });
    if (ultimaAcaoRef.current) sendAction(ultimaAcaoRef.current, { modoEmergencia: true });
  };

  // 👍/👎 por narração (Etapa 9) — sinal humano pro LLM-as-a-judge (ADR-0011)
  // e dataset de preferência. Otimista: marca o voto na hora, sem esperar
  // a resposta do servidor — um turno de RPG não é um formulário crítico.
  const enviarFeedback = (idx: number, turnoIndex: number, valor: 1 | -1, comentario?: string) => {
    setMessages(prev => prev.map((m, i) => (i === idx && m.kind === 'texto' ? { ...m, feedback: valor } : m)));
    api.post(`/personagens/${sessionId}/feedback`, { turno_index: turnoIndex, valor, comentario }).catch(() => {});
  };

  // Fase 7 (revisão de gameplay) — "Exportar Crônica": baixa um .txt com a
  // campanha inteira costurada em prosa (services/narrator.gerar_cronica).
  // Download client-side de verdade (Blob + <a download>) — este é o
  // próprio app, não um Artifact publicado, então o link funciona normal.
  const [exportandoCronica, setExportandoCronica] = useState(false);
  const exportarCronica = async () => {
    if (!sessionId || exportandoCronica) return;
    setExportandoCronica(true);
    try {
      const res = await api.get<{ nome: string; cronica: string }>(`/personagens/${sessionId}/cronica`);
      const blob = new Blob([res.data.cronica], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${res.data.nome} - Cronica.txt`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      // Exportar não é crítico o bastante pra travar a tela de fim de jogo com um erro.
    } finally {
      setExportandoCronica(false);
    }
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

      <SistemaFeedbackToast toasts={toasts} />
      <LootRevealOverlay loot={lootAtivo} onFinish={() => setLootAtivo(null)} />

      <div className={`absolute inset-0 z-50 bg-red-600 pointer-events-none transition-opacity duration-200 ${wasDamaged ? 'opacity-20' : 'opacity-0'}`} />
      {/* Item 9 — pisca contínuo enquanto a vida fica ≤10%, separado do
          flash de um tiro só acima (`wasDamaged`). */}
      {hpCritico && (
        <div className="absolute inset-0 z-50 bg-red-700 pointer-events-none animate-tela-critica" aria-hidden="true" />
      )}

      {/* Fase 4 do remaster UX (PLANO_REMASTER_UX.md) — "fade to black": a
          trilha já muda pra `tristeza` sozinha (calcularTema, acima) assim
          que `gameOver` vira true, então a música triste já acompanha esta
          transição sem precisar de nada novo aqui — só faltava a tela em
          si não aparecer com um corte seco. */}
      {gameOver && (
        <div className="absolute inset-0 z-[100] bg-black/95 flex flex-col items-center justify-center px-6 text-center overflow-y-auto py-10 animate-fade-in">
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

          {/* Pendência do remaster UX resolvida (PLANO_REMASTER_UX.md, item
              4) — pontuação real (XP + turnos sobreviventes + abates do
              bestiário, fórmula em routers/game.py:
              _persistir_epitafio_se_confirmado), a mesma que aparece no
              Salão dos Heróis Mortos da Home. */}
          {pontuacaoFinal != null && (
            <div className="mt-4 flex items-center gap-2 text-rpg-gold font-pixel-title text-sm">
              <PixelIcon name="estrela" size={16} /> {pontuacaoFinal} pontos
            </div>
          )}
          {mortoEm && (
            <p className="text-[10px] text-gray-600 mt-1 font-rpg">
              {new Date(mortoEm).toLocaleDateString('pt-BR', { day: '2-digit', month: 'long', year: 'numeric' })}
            </p>
          )}

          {quest?.nome_missao && (
            <p className="text-xs text-gray-500 mt-6 max-w-sm italic">
              Missão inacabada: "{quest.nome_missao}"
            </p>
          )}

          {/* Fase 7 (revisão de gameplay) — retrospectiva + epitáfio
              gerados por IA uma vez, na primeira morte confirmada
              (routers/game.py:_persistir_epitafio_se_confirmado). */}
          <div className="mt-8 border-t border-gray-800 pt-4 w-full max-w-sm">
            <p className="text-[10px] uppercase tracking-widest text-gray-600">O relato do mestre</p>
            {epitafio ? (
              <>
                <p className="text-sm text-gray-400 mt-2 whitespace-pre-wrap text-left">{epitafio.retrospectiva}</p>
                <p className="text-sm text-rpg-gold italic mt-3">"{epitafio.epitafio_curto}"</p>
              </>
            ) : (
              <p className="text-sm text-gray-500 italic mt-1">O mestre ainda está reunindo as palavras...</p>
            )}
          </div>

          <div className="mt-8 flex gap-3">
            <button
              onClick={() => navigate('/')}
              className="border-2 border-gray-700 px-4 py-2 text-gray-400 hover:text-white hover:border-gray-500 transition-colors"
            >
              Voltar
            </button>
            <button
              onClick={exportarCronica}
              disabled={exportandoCronica}
              className="border-2 border-gray-700 px-4 py-2 text-gray-400 hover:text-rpg-gold hover:border-rpg-gold transition-colors disabled:opacity-50"
            >
              {exportandoCronica ? 'Escrevendo...' : 'Exportar Crônica'}
            </button>
          </div>
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
          <div className="p-6 border-b border-gray-800 flex justify-between items-center bg-black/20">
              <h2 className="font-pixel-title text-sm text-rpg-gold flex items-center gap-2 truncate"><PixelIcon name="pergaminho" size={18}/> FICHA</h2>
              {/* Rodada de conserto — restaurado aqui: o botão que eu tinha
                  movido pra faixa de vitais só é renderizado quando a ficha
                  está FECHADA (ver abaixo), então com a ficha aberta esta é
                  a única entrada pra configurações de novo. */}
              <div className="flex items-center gap-3">
                  <button
                      onClick={() => setManualAberto(true)}
                      aria-label="Abrir manual do jogo"
                      title="Manual do Jogo"
                      className="text-gray-300 hover:text-rpg-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold"
                  ><PixelIcon name="dado" size={18}/></button>
                  {/* Item 11 da rodada de polish pós-remaster — "Guia do
                      Aventureiro": não existe ícone de interrogação em
                      PixelIcon.tsx, então usa um glifo de texto no mesmo
                      chrome dos outros botões de ícone (mesmo espírito de
                      "FICHA"/"MESTRE", que também são texto). */}
                  <button
                      onClick={() => setGuiaAberto(true)}
                      aria-label="Abrir guia do aventureiro"
                      title="Guia do Aventureiro"
                      className="w-[18px] h-[18px] flex items-center justify-center font-pixel-title text-[10px] text-gray-300 hover:text-rpg-gold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold"
                  >?</button>
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

          {/* Item 1 da rodada de polish pós-remaster — "a barra lateral deve
              concentrar tudo do herói": retrato + nome + HP/XP/Ouro (com
              barras) juntos, extraídos pra HudPersonagem.tsx. Local/Clima
              saiu daqui (foi pro topo central, CabecalhoRegiao.tsx). */}
          <HudPersonagem
              charName={charName}
              charRace={charRace}
              charClass={charClass}
              charImage={charImage}
              hpAtual={hpAtual}
              hpMax={hpMax}
              xp={xp}
              nivel={nivel}
              xpProximoNivel={xpProximoNivel}
              ouro={ouro}
              defesa={defesa}
              wasDamaged={wasDamaged}
              levelUpGlow={levelUpGlow}
              flutuantesHeroi={flutuantesHeroi}
              heroiEscondido={heroiEscondido}
              heroiBonusCa={heroiBonusCa}
              heroiVantagemInimiga={heroiVantagemInimiga}
              onAbrirFicha={() => setFichaModalAberta(true)}
          />

          {/* Abas. A ficha inteira empilhada numa coluna de 320px ficava
              espremida e obrigava a rolar pra achar qualquer coisa; separada em
              três telas, cada uma respira. Um `role="tablist"` de verdade, pra
              seta do teclado e leitor de tela funcionarem como o esperado.
              Item 6 (respiro) — `pt-3`→`pt-4` e `gap-1`→`gap-1.5`: os botões
              de aba estavam colados no bloco de cima. */}
          <div role="tablist" aria-label="Ficha do personagem" className="flex shrink-0 px-3 pt-4 gap-1.5">
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
              className="p-6 space-y-6 overflow-y-auto custom-scrollbar flex-1"
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
                  {/* Correção de UX pós Fase 1: o TooltipContent tinha z-index
                      fixo (z-50, mesmo nível da sidebar) e sem `side`, então
                      às vezes abria por cima da faixa de abas. `side="left"` +
                      `z-[75]` (via className, tailwind-merge resolve o
                      conflito de utilitário sem tocar em ui/tooltip.tsx, que é
                      reusado em outros lugares) resolvem isso só aqui. Junto,
                      um "Inspetor" fixo abaixo do grid — mesmo padrão do
                      painel de descrição do InventoryGrid — porque tooltip
                      sozinho não funciona em touch (sem hover de verdade). */}
                  <TooltipProvider delayDuration={150}>
                    <div className="grid grid-cols-3 gap-2">
                       {ATRIBUTOS.map(([chave, sigla]) => {
                         const valor = attributes?.[chave];
                         const info = ATRIBUTOS_INFO[chave];
                         const modificador = typeof valor === 'number' ? Math.floor((valor - 10) / 2) : null;
                         const selecionado = atributoInspecionado === chave;
                         return (
                           <Tooltip key={chave}>
                             <TooltipTrigger asChild>
                               <div
                                 tabIndex={0}
                                 onClick={() => setAtributoInspecionado(chave)}
                                 onFocus={() => setAtributoInspecionado(chave)}
                                 className={`bg-black/50 p-2 text-center border-2 cursor-help focus-visible:outline-none focus-visible:border-rpg-gold transition-colors ${
                                   selecionado ? 'border-rpg-gold' : 'border-gray-700 hover:border-gray-500'
                                 }`}
                               >
                                   <span className="text-[9px] text-gray-300 block font-rpg">{sigla}</span>
                                   <span className="font-rpg text-xl text-gray-100">{valor ?? '-'}</span>
                               </div>
                             </TooltipTrigger>
                             <TooltipContent side="left" className="z-[75]">
                               {info.nome}{modificador != null && ` — Modificador ${modificador >= 0 ? '+' : ''}${modificador}`}.{' '}
                               {info.uso}
                             </TooltipContent>
                           </Tooltip>
                         );
                       })}
                    </div>
                  </TooltipProvider>

                  <div className="border-2 border-gray-700 bg-black/60 p-2 min-h-[3.5rem] flex items-center">
                    {atributoInspecionado ? (
                      <div className="animate-fade-in">
                        <p className="font-rpg text-rpg-gold leading-tight">
                          {ATRIBUTOS_INFO[atributoInspecionado].nome}
                          {(() => {
                            const valor = attributes?.[atributoInspecionado];
                            const mod = typeof valor === 'number' ? Math.floor((valor - 10) / 2) : null;
                            return mod != null ? ` — Modificador ${mod >= 0 ? '+' : ''}${mod}` : '';
                          })()}
                        </p>
                        <p className="text-[11px] text-gray-300 font-rpg leading-snug">
                          {ATRIBUTOS_INFO[atributoInspecionado].uso}
                        </p>
                      </div>
                    ) : (
                      <p className="text-[11px] text-gray-400 font-rpg">Toque num atributo para ver o que ele faz.</p>
                    )}
                  </div>
                </div>
              )}

              {abaAtiva === 'itens' && (
                <div className="space-y-2 animate-fade-in">
                    <div className="flex items-center justify-between">
                        <h3 className="text-[10px] text-gray-300 uppercase font-rpg tracking-widest flex items-center gap-2"><PixelIcon name="mochila" size={12}/> Mochila</h3>
                        <span className="text-sm text-rpg-gold font-rpg flex items-center gap-1"><PixelIcon name="moeda" size={14}/> {ouro}</span>
                    </div>
                    <InventoryGrid
                      items={inventory}
                      onUsarItem={(item) => setInput(prev => `${prev}${prev && !prev.endsWith(' ') ? ' ' : ''}[${item}] `)}
                    />
                </div>
              )}

              {/* Fase 2 do remaster UX (PLANO_REMASTER_UX.md) — "Diário de
                  Bordo": a missão vira card de pergaminho (PanelFrame já
                  usado na narração da Fase 1), e o resumo rolante que o
                  próprio backend já gera pra memória do LLM (`anteriormente`,
                  antes só virava uma bolha de sistema) ganha um segundo uso
                  aqui como accordion — reler o que já aconteceu sem rolar o
                  chat inteiro pra cima. */}
              {abaAtiva === 'missao' && (
                <div className="animate-fade-in space-y-3">
                  {quest ? (
                      <PanelFrame borderWidth={8} className="bg-black/50 p-3">
                          <h3 className="text-[10px] text-blue-300 uppercase font-rpg mb-2 tracking-widest flex items-center gap-1">
                              <PixelIcon name="pergaminho" size={11} /> Missão atual
                          </h3>
                          <p className="text-base text-blue-100 font-rpg leading-tight mb-2">{quest.nome_missao}</p>
                          <p className="text-xs text-gray-200 leading-relaxed">{quest.objetivo_missao}</p>
                      </PanelFrame>
                  ) : (
                      <p className="text-sm text-gray-400 font-rpg text-center py-8">Nenhuma missão em andamento.</p>
                  )}

                  {resumoJornada && (
                      <div className="border-2 border-gray-700 bg-black/40">
                          <button
                              type="button"
                              onClick={() => setJornadaAberta(a => !a)}
                              aria-expanded={jornadaAberta}
                              aria-controls="jornada-ate-aqui"
                              className="w-full flex items-center justify-between gap-2 px-2.5 py-2 text-[10px] uppercase tracking-widest font-rpg text-gray-300 hover:text-rpg-gold transition-colors"
                          >
                              <span>A Jornada Até Aqui</span>
                              <PixelIcon name="seta" size={10} className={`transition-transform ${jornadaAberta ? 'rotate-90' : ''}`} />
                          </button>
                          {jornadaAberta && (
                              <p id="jornada-ate-aqui" className="px-2.5 pb-2.5 text-xs text-gray-400 leading-relaxed italic animate-fade-in">
                                  {resumoJornada}
                              </p>
                          )}
                      </div>
                  )}
                </div>
              )}

              {/* Fase 8 (revisão de gameplay) — cards de atitude de NPC.
                  A ferramenta `ajustar_reputacao_npc` (Etapa 5) já existia
                  e já entrava no contexto do narrador; até aqui não tinha
                  nenhum consumidor no frontend. -100 (Inimigo) a +100
                  (Aliado); a barra reaproveita PixelBar deslocando o
                  intervalo pra 0..200. */}
              {/* Fase 2 do remaster UX — cards de NPC ganham "juice" de
                  hover (levantam 2px, como o documento de design pede) e um
                  tooltip com a leitura por extenso da reputação, no lugar
                  de só o número — reaproveita o Tooltip que RollCard e a
                  faixa de vitais já usam. */}
              {abaAtiva === 'relacoes' && (
                <TooltipProvider delayDuration={150}>
                  <div className="space-y-2 animate-fade-in">
                    {Object.keys(reputacoes).length > 0 ? (
                      Object.entries(reputacoes).map(([npc, valor]) => {
                        const cor = valor > 15 ? 'bg-emerald-600' : valor < -15 ? 'bg-red-600' : 'bg-gray-500';
                        const leitura = valor > 50 ? `${npc} confia profundamente em você.`
                          : valor > 15 ? `${npc} confia em você.`
                          : valor < -50 ? `${npc} é seu inimigo declarado.`
                          : valor < -15 ? `${npc} desconfia de você.`
                          : `${npc} ainda não formou opinião sobre você.`;
                        return (
                          <Tooltip key={npc}>
                            <TooltipTrigger asChild>
                              <div tabIndex={0} className="bg-black/50 border-2 border-gray-700 p-2 transition-transform hover:-translate-y-0.5 hover:border-gray-500 cursor-help focus-visible:outline-none focus-visible:border-rpg-gold">
                                <div className="flex items-center justify-between mb-1">
                                  <span className="text-xs text-gray-200 font-rpg truncate">{npc}</span>
                                  <span className="text-[10px] text-gray-400 font-rpg shrink-0">{valor > 0 ? `+${valor}` : valor}</span>
                                </div>
                                <PixelBar value={valor + 100} max={200} segments={10} colorClass={cor} />
                                <div className="flex justify-between mt-0.5 text-[8px] text-gray-600 uppercase tracking-widest">
                                  <span>Inimigo</span>
                                  <span>Aliado</span>
                                </div>
                              </div>
                            </TooltipTrigger>
                            <TooltipContent>{leitura}</TooltipContent>
                          </Tooltip>
                        );
                      })
                    ) : (
                      <p className="text-sm text-gray-400 font-rpg text-center py-8">Nenhum NPC conhecido ainda.</p>
                    )}
                  </div>
                </TooltipProvider>
              )}
              {/* Fase 3 do remaster UX — grid de cards de monstro, sprites
                  reais de `/assets/monstros/` (mesmos usados no card de
                  combate). `onError` some com a imagem em vez de quebrar o
                  layout — a maioria dos nomes gerados pelo narrador não tem
                  sprite dedicado (só 5 existem hoje), então "sem sprite" é
                  o caso comum, não a exceção. */}
              {abaAtiva === 'bestiario' && (() => {
                // Pendência do remaster UX resolvida — os abates agora
                // persistem de verdade (Personagem.monstros_derrotados);
                // "avistado sem contagem" continua só desta sessão, porque
                // ainda não existe um endpoint com o catálogo completo.
                const nomes = Array.from(new Set([...Object.keys(monstrosDerrotados), ...monstrosAvistados]));
                return (
                  <div className="animate-fade-in">
                    {nomes.length > 0 ? (
                      <div className="grid grid-cols-3 gap-2">
                        {nomes.map((nome) => {
                          const abates = monstrosDerrotados[nome] ?? 0;
                          return (
                            // Item 10 da rodada de polish pós-remaster —
                            // tooltip pixelado (não mais silêncio total no
                            // hover) e clique abre a "página de bestiário".
                            <PixelTooltip
                              key={nome}
                              content={abates > 0 ? `Derrotado ×${abates} — clique para ver mais` : 'Avistado, nunca derrotado — clique para ver mais'}
                            >
                              <button
                                type="button"
                                onClick={() => setMonstroDetalheAberto(nome)}
                                className="bg-black/50 border-2 border-gray-700 hover:border-rpg-gold p-2 flex flex-col items-center gap-1 text-center transition-colors focus-visible:outline-none focus-visible:border-rpg-gold"
                              >
                                <img
                                  src={getLocalImage('monstros', nome)}
                                  alt=""
                                  className="w-8 h-8"
                                  onError={(e) => { e.currentTarget.style.display = 'none'; }}
                                />
                                <span className="text-[10px] font-rpg text-gray-300 leading-tight truncate w-full">{nome}</span>
                                <span className={`text-[8px] uppercase tracking-widest font-rpg ${abates > 0 ? 'text-red-400' : 'text-gray-500'}`}>
                                  {abates > 0 ? `Derrotado ×${abates}` : 'Avistado'}
                                </span>
                              </button>
                            </PixelTooltip>
                          );
                        })}
                      </div>
                    ) : (
                      <p className="text-sm text-gray-400 font-rpg text-center py-8">Nenhum monstro encontrado ainda.</p>
                    )}
                  </div>
                );
              })()}
          </div>
      </div>

      {/* Fase 3 do remaster UX (PLANO_REMASTER_UX.md) — "Ficha de
          Personagem": substitui o antigo modal de só-o-retrato (mesma
          informação de nome/raça/classe já cabe dentro da ficha inteira,
          não precisa dos dois). */}
      <FichaModal
          aberto={fichaModalAberta}
          onFechar={() => setFichaModalAberta(false)}
          nome={charName}
          raca={charRace}
          classe={charClass}
          charImage={charImage}
          atributos={attributes}
          hpAtual={hpAtual}
          hpMax={hpMax}
          defesa={defesa}
          origem={origemAtual}
          objetivo={objetivoAtual}
          historia={historiaAtual}
      />

      <MenuConfiguracao aberto={configAberta} aoFechar={() => setConfigAberta(false)} trilha={trilha} sfx={sfx} />
      <PainelRegrasModal aberto={manualAberto} aoFechar={() => setManualAberto(false)} />
      {/* Item 11 da rodada de polish pós-remaster. */}
      <GuiaAventureiro aberto={guiaAberto} aoFechar={() => setGuiaAberto(false)} />
      {/* Item 10 da rodada de polish pós-remaster. */}
      {monstroDetalheAberto && (
          <DetalheMonstroModal
              aberto
              onFechar={() => setMonstroDetalheAberto(null)}
              nome={monstroDetalheAberto}
              abates={monstrosDerrotados[monstroDetalheAberto] ?? 0}
          />
      )}

      {/* CHAT AREA. Pendência do remaster UX resolvida (item 2) — ambiência
          reage à hora do dia de verdade (`horaDoDia`, vinda do backend),
          com um véu de cor sutil em vez de arte de cenário nova (o jogo
          não tem nenhum fundo por local/bioma hoje — produzir isso é
          escopo de arte, não só de código; ver PLANO_REMASTER_UX.md §5). */}
      <div className={`flex-1 flex flex-col relative bg-[#050505] ${horaDoDia != null ? `periodo-${periodoDoDia(horaDoDia).replace('ã', 'a')}` : ''}`}>
        {/* Item 1+2 da rodada de polish pós-remaster — a faixa antiga de
            vitais (HP/nível/defesa) virou CabecalhoRegiao.tsx (Local/Clima
            + pílula de HP compacta): HP/XP/Ouro detalhados agora moram na
            sidebar (HudPersonagem.tsx), mas a pílula de HP continua fora
            dela — decisão de HUD híbrido aprovada com o usuário, porque no
            mobile a ficha é `fixed` e cobre a tela inteira: sem uma pílula
            aqui, fechar a ficha durante combate apagaria a vida da tela. */}
        <div className="shrink-0 flex items-center gap-1 px-2 pt-2 bg-black/60">
            {/* Rodada de conserto — o HUD de combate (antes `absolute`)
                cobria este botão inteiro em combate, deixando o jogador sem
                gesto nenhum pra reabrir a ficha; corrigido tirando o HUD do
                posicionamento absoluto. Uma tentativa anterior desta mesma
                correção deixava o botão SEMPRE visível (mesmo com a ficha
                aberta) — no mobile, com a gaveta aberta, a faixa de vitais
                fica espremida numa fatia estreita ao lado dela E por baixo
                do fundo escurecido (mesmo z-index da faixa, maior que o
                dela): o botão ficava semi-invisível e o clique caía no
                fundo, fechando a ficha em vez de abrir configurações. Só
                aparece com a ficha FECHADA — quando ela está aberta, os
                mesmos botões já existem no cabeçalho da própria ficha. */}
            {!showSidebar && (
                <button
                    onClick={() => setShowSidebar(true)}
                    aria-label="Abrir ficha do personagem"
                    className="shrink-0 p-1 border-2 border-gray-700 hover:border-rpg-gold text-gray-300 hover:text-rpg-gold transition-colors focus-visible:outline-none focus-visible:border-rpg-gold"
                ><PixelIcon name="menu" size={16}/></button>
            )}
            {!showSidebar && (
                <button
                    onClick={() => setManualAberto(true)}
                    aria-label="Abrir manual do jogo"
                    title="Manual do Jogo"
                    className="shrink-0 p-1 border-2 border-gray-700 hover:border-rpg-gold text-gray-300 hover:text-rpg-gold transition-colors focus-visible:outline-none focus-visible:border-rpg-gold"
                ><PixelIcon name="dado" size={16}/></button>
            )}
            {!showSidebar && (
                <button
                    onClick={() => setGuiaAberto(true)}
                    aria-label="Abrir guia do aventureiro"
                    title="Guia do Aventureiro"
                    className="shrink-0 w-[26px] h-[26px] flex items-center justify-center border-2 border-gray-700 hover:border-rpg-gold font-pixel-title text-[9px] text-gray-300 hover:text-rpg-gold transition-colors focus-visible:outline-none focus-visible:border-rpg-gold"
                >?</button>
            )}
            {!showSidebar && (
                <button
                    onClick={() => setConfigAberta(true)}
                    aria-label="Abrir configurações"
                    title="Configurações"
                    className="shrink-0 p-1 border-2 border-gray-700 hover:border-rpg-gold text-gray-300 hover:text-rpg-gold transition-colors focus-visible:outline-none focus-visible:border-rpg-gold"
                ><PixelIcon name="config" size={16}/></button>
            )}
        </div>
        <CabecalhoRegiao
            localAtual={localAtual}
            climaAtual={climaAtual}
            horaDoDia={horaDoDia}
            periodoDoDia={periodoDoDia}
            hpAtual={hpAtual}
            hpMax={hpMax}
            wasDamaged={wasDamaged}
            flutuantesHeroiHp={flutuantesHeroi.filter(f => f.alvo === 'hp')}
        />

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

        {modalReivindicarAberto && reivindicarPendente && (
            <div className="absolute inset-0 z-[90] bg-black/80 flex items-center justify-center p-4">
                <PanelFrame borderWidth={10} className="w-full max-w-sm">
                    <div className="bg-gray-900 pt-6">
                        <ConfirmeEmail
                            email={reivindicarPendente}
                            aoReenviar={() => reivindicar()}
                            reenviando={reivindicarEnviando}
                            reenviado={reivindicarReenviado}
                            erroAoReenviar={reivindicarErro !== null}
                        />
                        <button
                            type="button"
                            onClick={fecharModalReivindicar}
                            className="w-full border-t-2 border-gray-700 text-gray-400 hover:text-white py-3 text-sm"
                        >
                            Continuar jogando
                        </button>
                    </div>
                </PanelFrame>
            </div>
        )}

        {modalReivindicarAberto && !reivindicarPendente && (
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

        {/* BYOK (Etapa 15) — a cota compartilhada do servidor acabou por
            hoje. Abre direto nas Opções em vez de duplicar o campo de
            chave aqui: um único lugar pra colar/remover a chave. */}
        {modalTetoAberto && (
            <div className="absolute inset-0 z-[90] bg-black/80 flex items-center justify-center p-4">
                <PanelFrame borderWidth={10} className="w-full max-w-sm">
                    <div className="bg-gray-900 p-6">
                        <h2 className="font-rpg text-lg text-rpg-gold mb-1">Cota do servidor esgotada</h2>
                        <p className="text-xs text-gray-400 leading-relaxed mb-4">
                            Todo mundo divide a mesma cota gratuita de IA, e ela já foi usada por hoje. Pra
                            continuar jogando sem esperar amanhã, cole sua própria chave gratuita do Google
                            AI Studio nas Opções — leva menos de um minuto.
                        </p>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setModalTetoAberto(false)}
                                className="flex-1 border-2 border-gray-700 text-gray-400 hover:text-white py-2 text-sm"
                            >
                                Volto amanhã
                            </button>
                            <PixelButton
                                variant="dourado"
                                onClick={() => { setModalTetoAberto(false); setConfigAberta(true); }}
                                className="flex-1 py-2 text-sm"
                            >
                                Configurar chave
                            </PixelButton>
                        </div>
                    </div>
                </PanelFrame>
            </div>
        )}

        {/* BYOK (Etapa 15) — a CHAVE PRÓPRIA do jogador (não a do servidor)
            falhou no meio de um turno. Diferente do modal acima: aqui a
            saída é temporária (só este turno) e explícita — nunca cai pra
            chave do servidor sem o jogador escolher. */}
        {modalEmergenciaAberto && (
            <div className="absolute inset-0 z-[90] bg-black/80 flex items-center justify-center p-4">
                <PanelFrame borderWidth={10} className="w-full max-w-sm">
                    <div className="bg-gray-900 p-6">
                        <h2 className="font-rpg text-lg text-rpg-gold mb-1">Sua chave falhou</h2>
                        <p className="text-xs text-gray-400 leading-relaxed mb-4">{mensagemEmergencia}</p>
                        <p className="text-xs text-gray-400 leading-relaxed mb-4">
                            Quer tentar essa ação de novo usando a cota do servidor, só por enquanto?
                        </p>
                        <div className="flex gap-2">
                            <button
                                onClick={() => setModalEmergenciaAberto(false)}
                                className="flex-1 border-2 border-gray-700 text-gray-400 hover:text-white py-2 text-sm"
                            >
                                Cancelar
                            </button>
                            <PixelButton variant="dourado" onClick={tentarComChaveDoServidor} className="flex-1 py-2 text-sm">
                                Usar chave do servidor
                            </PixelButton>
                        </div>
                    </div>
                </PanelFrame>
            </div>
        )}

        {/* HUD Inimigos — ordem de iniciativa real (Etapa 7, Fase 1): a
            posição vem de `ordemIniciativa` (índices em `enemies`, -1 é o
            herói), calculada uma vez por `combat.iniciar_combate`. Clicar
            num inimigo sugere o alvo na próxima ação — quem decide o alvo
            de verdade continua sendo o texto interpretado pelo modelo
            (ADR-0006), isto só evita digitar o nome à mão.

            Rodada de conserto — antes era `absolute top-0 z-30`, empilhado
            por cima da faixa de vitais (mesmo pai `relative`) e cobrindo o
            botão de abrir a ficha inteiro: em combate, com a ficha
            fechada, não sobrava gesto nenhum pra reabri-la. Agora é uma
            faixa normal no fluxo, abaixo dos vitais — não cobre nada. */}
        {combatActive && enemies.length > 0 && !gameOver && (
            <div className="shrink-0 w-full bg-gradient-to-b from-red-950/90 to-black/40 border-b-2 border-red-900/40 px-2 py-2 flex items-center gap-3 animate-fade-in shadow-lg overflow-x-auto">
                <span className="shrink-0 text-red-500 font-rpg text-xs animate-pulse flex items-center gap-1"><PixelIcon name="espada" size={14}/> COMBATE</span>
                {enemies.map((en, i) => {
                    const posicao = ordemIniciativa.indexOf(i);
                    const suaVez = posicao !== -1 && ordemIniciativa[turnoAtual] === i;
                    const morto = en.hp <= 0;
                    // Item 10 da rodada de polish pós-remaster — o `title=`
                    // nativo (rodada de conserto, Parte 2, item I) virava
                    // uma caixa branca padrão do navegador, fora do tema;
                    // troca por PixelTooltip quando há `comportamento` pra
                    // mostrar, sem perder o botão nu quando não há.
                    const cardBotao = (
                        <button
                            type="button"
                            onClick={() => !morto && setInput(`Eu ataco ${en.nome}`)}
                            disabled={morto}
                            aria-label={morto ? `${en.nome} (derrotado)` : `Atacar ${en.nome}`}
                            className={`relative min-w-[100px] bg-black/80 p-2 border-2 backdrop-blur-sm text-left transition-colors
                                focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold
                                ${morto ? 'border-gray-800 opacity-40 cursor-default' : 'border-red-900/50 hover:border-rpg-gold cursor-pointer'}
                                ${suaVez && !morto ? 'ring-1 ring-rpg-gold' : ''}`}
                        >
                            <FloatingCombatText
                                itens={danosFlutuantes.filter(f => f.idx === i).map(f => ({ id: f.id, texto: `-${f.valor}`, cor: 'text-red-400' }))}
                            />
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
                    return en.comportamento ? (
                        <PixelTooltip key={i} content={en.comportamento}>{cardBotao}</PixelTooltip>
                    ) : (
                        <div key={i}>{cardBotao}</div>
                    );
                })}
            </div>
        )}

        {/* Fase 1 (revisão de gameplay) — testes de morte visíveis: o herói
            caído a 0 PV está a três falhas de perder o personagem, e essa
            informação existia no backend (CombatState.sucessos_morte/
            falhas_morte) desde a Etapa 7 sem nunca chegar à tela.
            Rodada de conserto — mesma mudança do HUD de combate acima: saiu
            do `absolute` (que dependia da altura do HUD pra não sobrepor
            nada) para o fluxo normal. */}
        {hpAtual <= 0 && !gameOver && (
            <div className="shrink-0 w-full flex justify-center py-1 animate-fade-in" role="status" aria-live="assertive">
                <div className="bg-black/85 border-2 border-red-900/60 px-3 py-2 flex flex-col items-center gap-1 backdrop-blur-sm">
                    <span className="text-[10px] uppercase tracking-widest text-red-400">Teste de morte</span>
                    <div className="flex gap-3">
                        <div className="flex gap-1" aria-label={`${sucessosMorte} de 3 sucessos`}>
                            {[0, 1, 2].map(i => (
                                <PixelIcon key={i} name="escudo" size={14}
                                    className={i < sucessosMorte ? 'opacity-100' : 'opacity-20'} />
                            ))}
                        </div>
                        <div className="flex gap-1" aria-label={`${falhasMorte} de 3 falhas`}>
                            {[0, 1, 2].map(i => (
                                <PixelIcon key={i} name="caveira" size={14}
                                    className={i < falhasMorte ? 'opacity-100' : 'opacity-20'} />
                            ))}
                        </div>
                    </div>
                </div>
            </div>
        )}

        {/* `aria-live="polite"` avisa leitor de tela sobre narração/rolagens
            chegando — a ressalva honesta (Lição 08, Etapa 7) é que o
            streaming token a token pode soar picotado num leitor de tela
            real, já que cada pedacinho de texto é uma mudança no live
            region; mitigar isso de verdade (debounce por frase) ficou
            para depois. */}
        <div className="flex-1 overflow-y-auto p-4 md:p-8 space-y-6 custom-scrollbar scroll-smooth" role="log" aria-live="polite" aria-atomic="false">
            {/* Rodada de conserto — este espaçador compensava a altura do
                HUD de combate quando ele era `absolute` e cobria o topo do
                log; agora que o HUD está no fluxo normal, ele só abriria
                um buraco vazio. */}
            {messages.map((msg, idx) => {
                if (msg.kind === 'rolagem') {
                    // Etapa 10 (A-7): cura/morte de inimigo usam o card de
                    // status; o resto (ataque, teste, dano, morte do herói)
                    // continua no RollCard de sempre.
                    if (msg.dados.tipo === 'cura' || msg.dados.tipo === 'morte_inimigo' || msg.dados.tipo === 'morte_aliado') {
                        return <StatusCard key={msg.id} dados={msg.dados} />;
                    }
                    return <RollCard key={msg.id} dados={msg.dados as DadosRolagem} />;
                }

                const isUser = msg.role === 'user';
                const isSystem = msg.role === 'system';

                if (isSystem) {
                    return (
                        <div key={msg.id} className="flex justify-center my-2 animate-fade-in">
                            <div className="bg-yellow-900/20 border border-yellow-700/30 text-yellow-500 px-4 py-2 text-xs font-mono flex items-center gap-2">
                                <PixelIcon name="dado" size={12}/> {msg.content}
                            </div>
                        </div>
                    );
                }

                // Fase 1 do remaster UX (PLANO_REMASTER_UX.md) — a narração
                // deixa de ser bolha de chat (avatar + balão lado a lado,
                // cara de app de mensagem) e vira parágrafo dentro de uma
                // moldura de pergaminho (PanelFrame, 9-slice já usado na
                // sidebar/modais); a fala do jogador vira só uma linha de
                // "ação" alinhada à direita, como o comando digitado, sem
                // balão próprio — a narração do Mestre é a protagonista
                // visual da tela, não uma troca de mensagens equivalente.
                if (isUser) {
                    return (
                        <div key={msg.id} className="flex justify-end animate-fade-in">
                            <div className="max-w-[80%] md:max-w-[70%] text-right border-r-2 border-rpg-gold/30 pr-3">
                                <span className="block font-pixel-title text-[8px] tracking-widest text-rpg-gold/70 mb-1">VOCÊ</span>
                                <p className="whitespace-pre-wrap break-words font-rpg text-sm md:text-base italic text-gray-300 leading-relaxed">
                                    {msg.content}
                                </p>
                            </div>
                        </div>
                    );
                }

                return (
                    <div key={msg.id} className="animate-fade-in">
                        {/* Item 8 da rodada de polish pós-remaster — fundo
                            escuro/marrom mais presente que o `bg-gray-900/50`
                            genérico de antes (reaproveita os tokens
                            `rpg-dark`/`rpg-leather` já existentes, em vez de
                            inventar cor nova), pra separar a caixa do Mestre
                            do fundo geral da página. */}
                        <PanelFrame
                            borderWidth={10}
                            className={`relative max-w-[820px] mx-auto p-4 md:p-6 ${msg.isError ? 'bg-amber-950/20' : 'bg-[#1a140d]/85'} backdrop-blur-sm`}
                        >
                            <span className={`absolute -top-3 left-3 px-2 py-0.5 font-pixel-title text-[8px] tracking-widest ${msg.isError ? 'bg-amber-800 text-amber-100' : 'bg-rpg-leather text-rpg-gold'}`}>
                                {msg.isError ? 'AVISO' : 'MESTRE'}
                            </span>
                            {/* Item 8 — `leading-relaxed` (1.625) virou
                                `leading-loose` (2): a fonte pixelada (VT323)
                                lê melhor com mais respiro entre linhas.
                                Item 9 — `renderizarNarrativa` troca texto
                                puro por nós React, pra `**negrito**`
                                (`limparMarkdownLeve` não apaga mais, ver
                                lib/utils.tsx) virar destaque dourado com
                                glow em vez de sumir. */}
                            <p className={`whitespace-pre-wrap break-words font-rpg text-base md:text-lg leading-loose ${msg.isError ? 'text-amber-200 italic' : 'text-gray-300'}`}>
                                {msg.isError ? msg.content : renderizarNarrativa(msg.content)}
                            </p>
                            {!msg.isError && msg.turnoIndex !== undefined && (
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
                                    // Item 5 da rodada de polish pós-remaster — área de clique
                                    // maior (`p-1`→`p-2.5`) e feedback tátil (`active:scale-95`).
                                    // `PixelIcon` é um `<img>` de PNG com cor própria, então
                                    // `text-emerald-500`/`text-red-500` no botão nunca recolorem
                                    // o ícone (achado ao ler PixelIcon.tsx) — a "cor viva
                                    // permanente + brilho" vira o FUNDO do botão (chip), não o
                                    // ícone em si.
                                    <div className="flex gap-2 mt-2 -mb-1">
                                        <button
                                            type="button"
                                            onClick={() => enviarFeedback(idx, msg.turnoIndex!, 1)}
                                            disabled={msg.feedback !== undefined}
                                            aria-label="Gostei desta narração"
                                            className={`p-2.5 border-2 transition-all active:scale-95 ${
                                                msg.feedback === 1
                                                    ? 'border-emerald-500 bg-emerald-600/90 shadow-[0_0_8px_rgba(16,185,129,0.7)]'
                                                    : 'border-transparent text-gray-600 hover:text-emerald-500 hover:border-gray-700 disabled:hover:text-gray-600 disabled:hover:border-transparent'
                                            }`}
                                        ><PixelIcon name="polegar-cima" size={16}/></button>
                                        <button
                                            type="button"
                                            onClick={() => { if (msg.feedback === undefined) setComentarioAbertoIdx(idx); }}
                                            disabled={msg.feedback !== undefined}
                                            aria-label="Não gostei desta narração"
                                            className={`p-2.5 border-2 transition-all active:scale-95 ${
                                                msg.feedback === -1
                                                    ? 'border-red-500 bg-red-600/90 shadow-[0_0_8px_rgba(239,68,68,0.7)]'
                                                    : 'border-transparent text-gray-600 hover:text-red-500 hover:border-gray-700 disabled:hover:text-gray-600 disabled:hover:border-transparent'
                                            }`}
                                        ><PixelIcon name="polegar-baixo" size={16}/></button>
                                    </div>
                                )
                            )}
                        </PanelFrame>
                    </div>
                );
            })}

            {loading && <div className="text-center py-4 text-xs text-gray-600 animate-pulse italic">O mestre está narrando...</div>}
            <div ref={messagesEndRef} className="h-4" />
        </div>

        {/* INPUT AREA */}
        {/* Rodada de conserto — `z-40` empatava com o backdrop da gaveta
            mobile (mesmo z-index, e este vem depois no DOM), então a caixa
            de texto ficava acesa e clicável por cima do fundo escurecido
            enquanto a ficha estava aberta. `z-10` fica abaixo do backdrop
            (`z-40`) e da gaveta (`z-50`). */}
        <div className="p-4 border-t border-gray-800 bg-gray-900 z-10 relative">
            {/* Fase 1 (revisão de gameplay) — sugestões extraídas da tag
                [OPCOES]: preenchem a caixa, nunca enviam sozinhas. A caixa
                de texto livre continua sendo o caminho principal — isto é
                um atalho pra quem não sabe o que digitar, não uma troca
                dela por um menu (mesmo espírito do clique no inimigo). */}
            {opcoes.length > 0 && !loading && !gameOver && (
                <div className="max-w-4xl mx-auto flex flex-wrap gap-2 mb-2 animate-fade-in">
                    {opcoes.map((op, i) => (
                        <PixelActionCard
                            key={i}
                            onClick={() => setInput(op)}
                            className="text-xs md:text-sm px-3 py-2"
                        >
                            {op}
                        </PixelActionCard>
                    ))}
                </div>
            )}
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
