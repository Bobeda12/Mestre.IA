import type { ReactNode } from "react"
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
// piscar um crase cru por meio segundo antes do fechamento chegar. Passa
// sempre sobre o texto ACUMULADO, nunca sobre o pedaço isolado — uma crase
// pode chegar partida entre dois frames SSE.
//
// Item 9 da rodada de polish pós-remaster: `**negrito**` deixou de ser
// APAGADO aqui — agora sobrevive em `msg.content` de propósito, pra
// `renderizarNarrativa` (abaixo) transformar em destaque dourado na hora de
// desenhar a bolha do Mestre, em vez de virar texto plano.
export function limparMarkdownLeve(texto: string) {
  return texto.replace(/`([^`\n]+?)`/g, '$1')
}

// Item 9 da rodada de polish pós-remaster — "loot visual": em vez de um
// parser de markdown completo (fora de escopo — desde o ajuste no prompt do
// narrador, `Backend/app/services/narrator.py`, o modelo só tem permissão
// de usar `**negrito**`, nunca itálico/listas/links/etc.), isto faz um
// split manual em segmentos e devolve nós React prontos — texto puro e
// `<strong>` dourado com glow pros trechos em negrito. De propósito NÃO usa
// `dangerouslySetInnerHTML`: a narração vem do LLM, e um nó React por
// segmento evita qualquer risco de HTML injetado, sem precisar de
// sanitização à parte.
const _PADRAO_NEGRITO = /(\*\*[^*\n]+?\*\*)/g

// Enquanto o texto ainda está chegando aos pedaços (token a token, ver
// `acrescentarTexto` em GameChat.tsx), um `**` de abertura pode chegar
// vários frames SSE antes do de fechamento — sem isto, o jogador veria os
// dois asteriscos crus piscando na tela por uma fração de segundo antes do
// negrito "fechar" e virar dourado. Mesmo truque de "esconder a cauda
// incompleta" que `esconderTagOpcoes` já usa pra tag `[OPCOES]`: com um
// número ÍMPAR de `**` no texto acumulado, o último é uma abertura ainda
// sem par — corta a exibição bem antes dele até o par chegar.
function ocultarNegritoIncompleto(texto: string): string {
  const total = (texto.match(/\*\*/g) || []).length
  if (total % 2 === 0) return texto
  return texto.slice(0, texto.lastIndexOf('**'))
}

export function renderizarNarrativa(texto: string): ReactNode[] {
  const partes = ocultarNegritoIncompleto(texto).split(_PADRAO_NEGRITO)
  return partes.map((parte, i) => {
    const m = /^\*\*([^*\n]+?)\*\*$/.exec(parte)
    if (!m) return parte
    return (
      <strong key={i} className="text-rpg-gold text-glow font-bold">
        {m[1]}
      </strong>
    )
  })
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
