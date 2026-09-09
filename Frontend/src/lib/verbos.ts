import type { AcaoDireta, EntidadeMundo, PessoaMundo } from './gameplay';
import type { PixelIconName } from '../components/PixelIcon';

// Fase 6 (ADR-0036) — o vocabulário de verbos do Mundo Vivo sai de
// LivingWorld.tsx para um módulo puro: o palco seleciona, o dock lista os
// verbos, e o servidor (`living_world.agir_no_mundo`) continua sendo quem
// valida. Os rótulos são os que o jogador lê nos botões.
export const ACOES: Record<string, string> = {
  examinar: 'Examinar', investigar: 'Investigar', mover: 'Mover', bloquear: 'Bloquear com um objeto',
  desbloquear: 'Remover o bloqueio', abrir: 'Abrir', destrancar: 'Destrancar', quebrar: 'Quebrar',
  acender: 'Acender', apagar: 'Apagar', atravessar: 'Seguir por aqui', ocultar: 'Esconder-se aqui',
  conversar: 'Conversar', negociar: 'Negociar', ajudar: 'Oferecer ajuda', intimidar: 'Intimidar',
  distrair: 'Distrair', acalmar: 'Acalmar',
  pegar: 'Recolher',
};

/** Verbos sociais que exigem uma proposta em texto (o dock usa o próprio campo de ação). */
export const SOCIAIS = ['negociar', 'ajudar', 'intimidar', 'distrair', 'acalmar'];

/** Verbos que aceitam um `meio` (objeto móvel ou item do inventário). `bloquear` exige. */
export const ACEITAM_MEIO = ['bloquear', 'quebrar', 'acender', 'mover', 'destrancar', 'distrair'];

export function verbosPara(alvo: PessoaMundo | EntidadeMundo | undefined): string[] {
  if (!alvo) return [];
  if ('disposicao' in alvo) return ['examinar', 'conversar', ...SOCIAIS];
  const e = alvo;
  return [
    'examinar', 'investigar',
    ...(e.tipo === 'saida' ? ['atravessar', 'bloquear'] : []),
    ...(e.estado === 'bloqueado' ? ['desbloquear'] : []),
    ...(e.propriedades.includes('trancado') ? ['destrancar'] : ['abrir']),
    ...(e.propriedades.includes('movel') ? ['mover'] : []),
    ...(e.propriedades.includes('coletavel') ? ['pegar'] : []),
    ...(e.propriedades.includes('inflamavel') ? ['acender'] : []),
    ...(e.estado === 'aceso' ? ['apagar'] : []),
    ...(e.propriedades.includes('cobertura') ? ['ocultar'] : []),
    ...(e.tipo === 'animal' ? ['acalmar'] : ['quebrar']),
  ];
}

/** Ícone de um objeto ou saída do mundo na prateleira do palco. */
export function iconeEntidade(e: EntidadeMundo): PixelIconName {
  if (e.tipo === 'saida') return 'seta';
  if (e.tipo === 'animal') return 'rosto';
  if (e.propriedades.includes('investigavel')) return 'pergaminho';
  return 'bau';
}

/** Táticas de combate (Fase 1 da revisão de gameplay), resolvidas pelo juiz sem LLM. */
export const TATICAS: { acao: AcaoDireta['acao']; nome: string; dica: string; icone: PixelIconName }[] = [
  { acao: 'esquivar', nome: 'Esquivar', dica: 'Dificulte os ataques inimigos até seu próximo turno.', icone: 'seta' },
  { acao: 'investir', nome: 'Investir', dica: 'Ataque com mais força, expondo sua defesa.', icone: 'machado' },
  { acao: 'esconder_se', nome: 'Esconder', dica: 'Teste furtividade para preparar uma emboscada.', icone: 'adaga' },
  { acao: 'fugir', nome: 'Fugir', dica: 'Tente escapar; a perseguição pode ser perigosa.', icone: 'alerta' },
];

/** Ícones das interações táticas de cenário (`encounters.painel_cena`), só em combate. */
export const ICONE_INTERACAO: Record<string, PixelIconName> = {
  cobertura: 'escudo', distrair: 'rosto', poeira: 'alerta', derrubar: 'machado', objetivo: 'pergaminho',
};
