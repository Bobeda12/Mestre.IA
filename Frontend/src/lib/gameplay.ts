export interface Habilidade {
  id: string;
  nome: string;
  descricao: string;
  nivel: number;
  custo: number;
  alvo: 'inimigo' | 'todos' | 'heroi';
  disponivel: boolean;
}

export interface OpcaoNivel { tipo: 'atributo' | 'talento' | 'especializacao'; id: string; nome: string; descricao: string }

export interface Progressao {
  nivel_maximo: number;
  estilo: string;
  recurso: { nome: string; atual: number; maximo: number };
  habilidades: Habilidade[];
  niveis: { nivel: number; xp: number; descricao: string }[];
  /** Fase 3 (ADR-0034) — escolhas de nível que o jogador ainda não fez. */
  pendencias?: { nivel: number; opcoes: OpcaoNivel[] }[];
  talentos?: { id: string; nome: string; descricao: string }[];
  especializacoes?: Record<string, string>;
}

export interface Cena {
  tipo: string;
  nome: string;
  descricao: string;
  objetivo: string;
  progresso: number;
  meta: number;
  rodada: number;
  interacoes: { id: string; nome: string; descricao: string }[];
}

/** Fase 2 do plano "jogo completo" — companheiro no palco (roster de `Personagem.aliados`). */
export interface AliadoVisual {
  nome: string;
  classe: string;
  raca?: string;
  hp: number;
  hp_max: number;
  ja_agiu?: boolean;
}

export interface InimigoVisual {
  nome: string;
  hp: number;
  max_hp: number;
  ca: number;
  arquetipo?: string;
  afastado?: boolean;
  intencao?: string;
  comportamento?: string;
  efeitos?: Record<string, number>;
}

export interface AcaoDireta {
  acao: 'atacar' | 'defender' | 'esquivar' | 'investir' | 'esconder_se' | 'fugir' | 'usar_habilidade' | 'interagir' | 'descansar' | 'resistir' | 'agir_no_mundo' | 'intervir_conflito' | 'definir_objetivo' | 'escolher_especializacao' | 'equipar' | 'desequipar' | 'comerciar' | 'usar_item' | 'atacar_com_aliado' | 'escolher_nivel' | 'encerrar_arco';
  alvo?: string;
  nivel_escolha?: number;
  tipo_escolha?: 'atributo' | 'talento' | 'especializacao';
  opcao?: string;
  aliado?: string;
  item?: string;
  slot?: 'arma' | 'armadura' | 'escudo';
  habilidade?: string;
  interacao?: string;
  operacao?: string;
  meio?: string;
  proposta?: string;
  marco?: '3' | '7';
  escolha?: 'explorador' | 'diplomata' | 'combatente';
}

export interface EntidadeMundo {
  id: string; nome: string; descricao: string; tipo: string; propriedades: string[];
  estado: string; destino: string; descoberto: boolean; pista?: string;
}
export interface PessoaMundo {
  id: string; nome: string; descricao: string; disposicao: string; confianca: number; raca?: string;
  necessidade: string; lembrancas: string[]; promessas: string[]; depoimento?: string;
  /** Fase 1 (ADR-0033) — vitrine do mercador, com preço já calculado pelo servidor. */
  vitrine?: { item: string; preco: number }[];
}

/** Fase 1 (ADR-0033) — ficha pública de um item que o herói tem ou que está à venda. */
export interface ItemInfo {
  tipo: 'consumivel' | 'ferramenta' | 'armadura' | 'escudo' | 'arma' | 'inventado';
  tags: string[];
  descricao: string;
  preco_venda: number;
}
export interface Equipamento { arma?: string | null; armadura?: string | null; escudo?: string | null }
/** Fase 4 (ADR-0035) — o arco atual, com o que o servidor exige para encerrar. */
export interface ArcoAtual {
  ativo: boolean; id?: string; titulo?: string; premissa?: string; conflito?: string; estado_conflito?: string;
  turnos?: number; marcos?: number; resultado_esperado?: string; pode_encerrar?: boolean; motivo_bloqueio?: string;
}
export interface ArcoEncerrado { id: string; titulo: string; texto: string; resultado: string; recompensa: { xp: number; ouro: number; itens: string[] } }

export interface MundoPersistente {
  local: string; descricao: string; entidades: EntidadeMundo[]; pessoas: PessoaMundo[];
  conflitos: {id: string; nome: string; sinal: string; progresso: number; etapas: number;
    estado: string; desfecho: string; minutos_restantes: number; intervencoes: number}[];
  conhecimento: {texto: string; natureza: string; fonte: string; turno: number}[];
  objetivos: string[]; especializacoes: Record<string, string>;
  aptidao: {nome: string; acoes: string[]; bonus: number}; minutos: number;
}

/** Arquétipos do bestiário com sprite em /assets/monstros (slug sem acento). Fase 5: a lista
 *  cresce conforme a arte entra; quem não tem arte cai na caveira. */
export const SPRITES_MONSTROS = new Set([
  'aranha-gigante', 'bugbear', 'capitao-bandido', 'carnical-cinzento', 'cavaleiro-negro', 'dragao-adulto-jovem', 'dragao-jovem', 'elemental-de-fogo', 'espectro', 'esqueleto', 'gigante-da-colina', 'gnoll-lider', 'goblin', 'golem-de-pedra', 'harpia', 'hidra-menor', 'kobold', 'lich-menor', 'lobo', 'manticora', 'minotauro', 'mumia', 'ogro', 'orc', 'troll', 'urso-coruja', 'vampiro-jovem', 'wight',
]);

export function slugMonstro(nome: string): string {
  return nome.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-|-$/g, '');
}

/** The name remains the exact server target; only the visual uses an archetype. */
export function spriteInimigo(inimigo: InimigoVisual): string {
  const candidatos = [inimigo.arquetipo, inimigo.nome].filter(Boolean).map(n => slugMonstro(n as string));
  const direto = candidatos.find(s => SPRITES_MONSTROS.has(s));
  if (direto) return `/assets/monstros/${direto}.png`;
  const nome = `${inimigo.arquetipo ?? ''} ${inimigo.nome}`.toLowerCase();
  const parcial = [...SPRITES_MONSTROS].find(tipo => nome.includes(tipo));
  return parcial ? `/assets/monstros/${parcial}.png` : '/assets/icons/caveira.png';
}

export function alvoValido(selecionado: string | null, inimigos: InimigoVisual[]): string | undefined {
  return inimigos.find(inimigo => inimigo.nome === selecionado && inimigo.hp > 0 && !inimigo.afastado)?.nome
    ?? inimigos.find(inimigo => inimigo.hp > 0 && !inimigo.afastado)?.nome;
}

/** Fase 6 (ADR-0036) — a seleção única do palco: um inimigo (alvo de combate), uma pessoa ou um objeto/saída. */
export interface Selecao { tipo: 'inimigo' | 'pessoa' | 'objeto'; id: string }

/** Sentinela do backend (`domain/living_world.SAIDA_LIVRE`): saída sem destino fixo. */
export const SAIDA_LIVRE = 'Estrada livre';
