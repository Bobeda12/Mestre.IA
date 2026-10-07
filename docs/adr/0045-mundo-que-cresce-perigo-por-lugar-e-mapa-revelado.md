# ADR-0045 — Mundo que cresce: perigo por lugar e mapa revelado por capítulo

**Data:** 07/10/2026
**Status:** Aceito
**Etapa:** Plano "Texto livre confiável e progressão" (Fase 3)
**Supersede:** —

---

## Contexto

O catálogo tinha 7 lugares fixos. O narrador podia mandar o herói a qualquer um a qualquer
momento e o perigo dos monstros dependia só do nível do herói, nunca de onde ele estava.
O mundo não mudava com o que o jogador fazia, e os "lugares" não apareciam na tela.

O plano previa "gate suave" (regiões que abrem por nível). Com a decisão do jogador de
**liberdade com consequência** (ADR-0044), trancar viagem seria o contrário: o jogo diria
"você não pode ir lá".

## Decisão

**1. Viajar continua livre. O que escala é o perigo.** Cada lugar do catálogo ganhou `nivel`
(0 = seguro). `nivel_do_local(local, nivel_heroi)` devolve `max(nível do herói, nível do
lugar)`, com teto no nível máximo. O combate iniciado ali usa essa faixa de monstros, então
quem chega ao Vulcão (nível 8) com um herói de nível 1 enfrenta o que o Vulcão tem. O
resultado de `mover` traz `perigo_nivel` e um aviso "⚠️ Lugar perigoso" quando passa do nível
do herói, para o narrador anunciar o risco antes de a luta chegar.

**2. O catálogo passou de 7 para 14 lugares**, até o nível 9 (Cidade de Altaluz como segundo
polo seguro, minas, ruínas, torre, montanhas, vulcão e uma cidadela). O conteúdo é texto
meu, pensado como ponto de partida para você reescrever.

**3. O mapa é revelado, não trancado.** `WorldState.locais_conhecidos` guarda os lugares do
catálogo que o herói ouviu falar. Ao fechar um capítulo (resultado diferente de abandono),
`revelar_locais` revela até 2 lugares ainda desconhecidos, na ordem de dificuldade, até 3
níveis acima do herói. Sem sorteio. O prompt do narrador ganhou `[LUGARES CONHECIDOS]`.
Conhecer ajuda o narrador a oferecer; o jogador ainda pode citar qualquer lugar do catálogo.

**4. A aba Jornada lista os lugares conhecidos**, com o nível de perigo e onde o herói está.

## Consequências

- O XP de abate já era alto demais (relatório 0006); lutar em lugar acima do nível agora
  rende ainda mais. A Fase 4 refaz a curva de XP e precisa levar isso em conta.
- O prompt cresceu ~40 caracteres (15479, teto 16000). Com muitos lugares conhecidos a linha
  `[LUGARES CONHECIDOS]` cresce; vale vigiar.
- Saves antigos: `locais_conhecidos` começa vazio e os lugares já visitados continuam
  contando (vêm de `mundo.cenas`), sem migração.
- Lugares inventados pelo narrador (`locais_descobertos`) continuam sem `nivel`: usam o
  nível do herói, como antes.
- **Não feito:** o perigo ainda não muda o encontro de viagem (o d20 de emboscada é igual em
  todo lugar), e não há mapa gráfico clicável (decisão: texto livre é o principal).

## Alternativas descartadas

- **Trancar regiões por nível ou capítulo.** Contradiz a liberdade; o jogador ficaria
  esbarrando em "você não pode".
- **Esconder do narrador os lugares ainda desconhecidos.** Ele já os conhece pelo catálogo;
  esconder só quebraria a mensagem de erro de `mover` e não impediria nada.
