export interface Habilidade {
  id: string;
  nome: string;
  descricao: string;
  nivel: number;
  custo: number;
  alvo: 'inimigo' | 'todos' | 'heroi';
  disponivel: boolean;
}

export interface Progressao {
  nivel_maximo: number;
  estilo: string;
  recurso: { nome: string; atual: number; maximo: number };
  habilidades: Habilidade[];
  niveis: { nivel: number; xp: number; descricao: string }[];
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
  acao: 'atacar' | 'defender' | 'esquivar' | 'investir' | 'esconder_se' | 'fugir' | 'usar_habilidade' | 'interagir' | 'descansar' | 'resistir' | 'agir_no_mundo' | 'intervir_conflito' | 'definir_objetivo' | 'escolher_especializacao' | 'equipar' | 'desequipar' | 'comerciar' | 'usar_item';
  alvo?: string;
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
export interface MundoPersistente {
  local: string; descricao: string; entidades: EntidadeMundo[]; pessoas: PessoaMundo[];
  conflitos: {id: string; nome: string; sinal: string; progresso: number; etapas: number;
    estado: string; desfecho: string; minutos_restantes: number; intervencoes: number}[];
  conhecimento: {texto: string; natureza: string; fonte: string; turno: number}[];
  objetivos: string[]; especializacoes: Record<string, string>;
  aptidao: {nome: string; acoes: string[]; bonus: number}; minutos: number;
}

/** The name remains the exact server target; only the visual uses an archetype. */
export function spriteInimigo(inimigo: InimigoVisual): string {
  const nome = `${inimigo.arquetipo ?? ''} ${inimigo.nome}`.toLowerCase();
  const sprite = ['bugbear', 'esqueleto', 'kobold', 'goblin', 'lobo'].find(tipo => nome.includes(tipo));
  return sprite ? `/assets/monstros/${sprite}.png` : '/assets/icons/caveira.png';
}

export function alvoValido(selecionado: string | null, inimigos: InimigoVisual[]): string | undefined {
  return inimigos.find(inimigo => inimigo.nome === selecionado && inimigo.hp > 0 && !inimigo.afastado)?.nome
    ?? inimigos.find(inimigo => inimigo.hp > 0 && !inimigo.afastado)?.nome;
}
