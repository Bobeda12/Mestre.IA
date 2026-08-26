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
// Ícone pequeno: sprite do Dungeon Crawl (CC0, 32×32) — personagem completo,
// silhueta própria, cada opção distinta da outra num quadrado de 48px.
export function getLocalImage(type: 'classes' | 'races' | 'monstros', name: string) {
  return `/assets/${type}/${_arquivo(name)}.png`
}

// Painel grande: retrato gerado por IA e pixelizado pra 48×48 (ADR-0025).
//
// Os dois conjuntos existem porque cada um ganha num tamanho. O sprite do
// Dungeon Crawl é feito pra ser lido a 32px: ampliado num painel de ~400px
// ele continua correto, mas é uma figura pequena e simples ocupando muito
// espaço. O retrato tem densidade pra sustentar esse tamanho — e é ilegível
// reduzido a 48px, onde várias classes acabam parecidas entre si. Cada um
// onde funciona, em vez de um só servindo mal aos dois.
export function getRetrato(type: 'classes' | 'races', name: string) {
  return `/assets/retratos/${type}/${_arquivo(name)}.png`
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

// Fase 1 da revisão de gameplay — o narrador sempre termina com
// `[OPCOES]: ...` (narrator.montar_contexto); o servidor a remove antes de
// persistir (guardrail.extrair_opcoes), mas o texto cru ainda passa pelos
// frames `token` ao vivo. Mesma lógica de "limpeza leve" do markdown: corta
// a exibição no primeiro sinal da tag e nunca mais volta a mostrar depois
// dele — a tag é sempre a última coisa que o modelo escreve, por instrução
// do prompt, então isto nunca esconde narrativa de verdade.
//
// O prompt pede "[OPCOES]" sem acento, mas ao vivo o modelo "corrige" pra
// "[OPÇÕES]" (grafia correta em português) — achado testando contra a
// Groq de verdade, não em teste automatizado. `/\[OP.{0,2}ES/i` casa as
// duas grafias (e variações de acento) sem enumerar cada uma; mesmo regex
// usado no servidor (guardrail.extrair_opcoes).
const _PADRAO_OPCOES = /\[OP.{0,2}ES/i

export function esconderTagOpcoes(texto: string) {
  // Rodada de conserto — antes disto, o corte valia pro texto INTEIRO: se
  // "[OP" aparecesse em qualquer ponto (mesmo no meio de uma frase, por
  // acidente), tudo o que vinha depois sumia da tela pra sempre, mesmo
  // narração de verdade. A tag só é válida como ÚLTIMA linha (é assim que
  // o prompt pede) — procurar só ali evita apagar narração por engano.
  const inicioUltimaLinha = texto.lastIndexOf('\n') + 1
  const ultimaLinha = texto.slice(inicioUltimaLinha)
  const m = _PADRAO_OPCOES.exec(ultimaLinha)
  return m ? texto.slice(0, inicioUltimaLinha + m.index).trimEnd() : texto
}
