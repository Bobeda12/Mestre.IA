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
