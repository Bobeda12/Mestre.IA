# Quatro consertos de UX na ficha do jogador

**Período:** 02/09/2026 · uma sessão com o Claude Code

## O que aconteceu

Depois do remaster visual (Fase 1), quatro coisas pequenas ficaram incômodas de usar de
verdade, mesmo com a interface mais bonita. Nenhuma delas é uma etapa nova do jogo — são
ajustes de uso, então este diário é só um resumo simples, sem ADR técnico.

## Os quatro ajustes

- **A aba "Regras" saiu da ficha.** A faixa de abas do lado (Status, Itens, Missão,
  Relações, Bestiário, Regras) estava apertada demais, principalmente no celular. As
  regras do jogo (níveis, dificuldade dos testes, ações de combate) agora abrem num
  painel de tela cheia, através de um botão "Manual do Jogo" (ícone de dado) que fica no
  topo, do lado do botão de configurações.

- **A dica de cada atributo (Força, Destreza etc.) não fica mais escondida atrás dos
  botões de aba.** Antes, passar o mouse num atributo às vezes abria a explicação por
  baixo da faixa de abas, ilegível. Além de corrigir isso, agora também dá pra *clicar*
  no atributo (não só passar o mouse) para ver a explicação num quadro fixo logo abaixo
  — importante pra quem joga no celular, onde não existe "passar o mouse".

- **Clicar num item da mochila não manda mais ele pro chat sem querer.** Antes, um único
  clique no item ao mesmo tempo abria os detalhes dele E escrevia `[Nome do Item]` na
  caixa de ação — fácil de mandar sem querer. Agora clicar só abre os detalhes; um botão
  separado, "💬 Citar no chat", é que escreve o item na caixa.

- **Os botões de sugestão de ação ficaram com mais cara de jogo.** Aqueles botões que
  aparecem quando o narrador sugere ações (ex: "Avançar em direção ao guardião") ganharam
  um acabamento de madeira/metal entalhado e uma setinha do lado do texto, que reage
  quando o mouse passa por cima — mais parecido com um menu de RPG clássico.

## Como testei

Criei um personagem de teste (fluxo "Jogar agora", sem precisar de conta) e joguei um
turno de verdade contra o modelo de IA, no navegador: abri o Manual do Jogo, cliquei e
passei o mouse nos atributos, abri um item da mochila e usei o botão de citar, e vi as
sugestões de ação com o novo visual aparecendo depois da resposta do narrador. Também
rodei o typecheck (`tsc -b`) e o lint (`eslint`) do frontend, os dois limpos.

## Próximo passo

Nenhum pendente desta rodada — os quatro pontos relatados foram resolvidos. As pendências
gerais do projeto continuam as mesmas de antes (Google OAuth em produção, gaveta mobile da
Etapa 7, calibração do juiz da Etapa 6).
