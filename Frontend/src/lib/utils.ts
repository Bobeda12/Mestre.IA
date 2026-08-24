import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Sprite local por classe/raça/monstro (CharacterCreation.tsx e
// GameChat.tsx) — usado na tela de criação (escolher raça/classe) e como
// retrato de fallback quando o personagem não tem `imagem` gerada por IA
// persistida (ver B-3, `Personagem.imagem`). É pixel art CC0 (ver
// docs/CREDITOS.md), por isso `.png` e não `.jpg`: perda de JPEG borra os
// contornos de 1px.
//
// UMA função só, de propósito. Houve uma fase com dois conjuntos de arte
// (sprite pequeno numa função, retrato grande noutra) porque nenhuma das
// fontes de então servia aos dois tamanhos. Os sprites de 32×32 do Dungeon
// Crawl (ADR-0025) resolvem os dois, então o segundo caminho foi removido em
// vez de ficar mantendo duas pastas em sincronia.
export function getLocalImage(type: 'classes' | 'races' | 'monstros', name: string) {
  return `/assets/${type}/${_arquivo(name)}.png`
}

// `\p{Diacritic}` (Unicode property escape) tira os acentos depois do NFD,
// sem precisar embutir a faixa de marcas de combinação no código-fonte.
function _arquivo(name: string) {
  return name.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '').replace(/\s+/g, '-')
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
