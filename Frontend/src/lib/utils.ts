import { clsx, type ClassValue } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Retrato local por classe/raça (CharacterCreation.tsx e GameChat.tsx) —
// desde a Etapa 8 é o único retrato que sobrevive a um F5 ou a "continuar":
// o retrato gerado por IA na criação nunca foi persistido no servidor
// (`Personagem` não tem coluna de imagem), só vivia no `localStorage`
// junto com o resto do save — que morreu como fonte de verdade nesta etapa.
// `\p{Diacritic}` (Unicode property escape) tira os acentos depois do NFD,
// sem precisar embutir a faixa de marcas de combinação no código-fonte.
export function getLocalImage(type: 'classes' | 'races', name: string) {
  const semAcento = name.toLowerCase().normalize('NFD').replace(/\p{Diacritic}/gu, '')
  return `/assets/${type}/${semAcento.replace(/\s+/g, '-')}.jpg`
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
