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
  intencao?: string;
  comportamento?: string;
  efeitos?: Record<string, number>;
}

export interface AcaoDireta {
  acao: 'atacar' | 'defender' | 'esquivar' | 'investir' | 'esconder_se' | 'fugir' | 'usar_habilidade' | 'interagir' | 'descansar' | 'resistir';
  alvo?: string;
  habilidade?: string;
  interacao?: string;
}

/** The name remains the exact server target; only the visual uses an archetype. */
export function spriteInimigo(inimigo: InimigoVisual): string {
  const nome = `${inimigo.arquetipo ?? ''} ${inimigo.nome}`.toLowerCase();
  const sprite = ['bugbear', 'esqueleto', 'kobold', 'goblin', 'lobo'].find(tipo => nome.includes(tipo));
  return sprite ? `/assets/monstros/${sprite}.png` : '/assets/icons/caveira.png';
}

export function alvoValido(selecionado: string | null, inimigos: InimigoVisual[]): string | undefined {
  return inimigos.find(inimigo => inimigo.nome === selecionado && inimigo.hp > 0)?.nome
    ?? inimigos.find(inimigo => inimigo.hp > 0)?.nome;
}
