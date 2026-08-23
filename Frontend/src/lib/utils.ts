import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Sprite local por classe/raça/monstro (CharacterCreation.tsx e
// GameChat.tsx) — usado na tela de criação (escolher raça/classe) e como
// retrato de fallback quando o personagem não tem `imagem` gerada por IA
// persistida (ver B-3, `Personagem.imagem`). Etapa 11 (B-1): pixel art
// real (CC0, ver docs/CREDITOS.md), não mais foto — por isso `.png`, não
// `.jpg` (pixel art com perda de JPEG borra os contornos).
// `\p{Diacritic}` (Unicode property escape) tira os acentos depois do NFD,
// sem precisar embutir a faixa de marcas de combinação no código-fonte.
export function getLocalImage(type: 'classes' | 'races' | 'monstros', name: string) {
  const semAcento = name.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')
  return `/assets/${type}/${semAcento.replace(/\s+/g, '-')}.png`
}

// Etapa 10 (A-7) — limpeza leve enquanto o texto ainda está chegando aos
// pedaços (GameChat.tsx). O servidor (services/guardrail.limpar_formatacao)
// já limpa o texto completo antes de persistir; isto é só para a tela não
// piscar um `**` cru por meio segundo antes do fechamento chegar. Passa
// sempre sobre o texto ACUMULADO, nunca sobre o pedaço isolado — um `**`
// pode chegar partido entre dois frames SSE.
export function limparMarkdownLeve(texto: string) {
  return texto.replace(/\*{1,3}([^*\n]+?)\*{1,3}/g, '$1').replace(/`([^`\n]+?)`/g, '$1')
}
