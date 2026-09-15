# Um objetivo só, não três

**Período:** 15/09/2026 · achado de uso, mesma sessão da auditoria pré-lançamento

## O que aconteceu

Ao jogar, ficou claro que a palavra "objetivo" tinha virado três coisas diferentes ao
mesmo tempo, sem nenhuma explicar a relação com as outras:

1. Na aba Jornada da ficha, um bloco "Missão atual" (o que o Mestre decidia) e, mais
   embaixo, um bloco "Meu objetivo" (o que o jogador escrevia), quase sempre mostrando o
   mesmo texto — mas nem sempre, e nada dizia por quê.
2. Por baixo dos dois, o Mestre (a IA) tinha duas ferramentas escrevendo no mesmo lugar:
   `atualizar_missao` (pensada pra quando um NPC dá uma tarefa) e `definir_objetivo`
   (pensada pra quando o jogador decide sozinho). A única diferença entre elas era uma
   frase de instrução no prompt — nada no código impedia o modelo de usar a errada, e um
   uso errado significava o Mestre sobrescrevendo, sem avisar, o objetivo que o jogador
   tinha acabado de escolher.

## O que mudou

- A ficha mostra um bloco só, "Seu objetivo agora", com o texto atual e o campo pra
  redefinir — sem duas fontes de verdade competindo pela mesma informação.
- No motor, sobrou uma ferramenta (`definir_objetivo`), com um campo `origem`
  (`jogador` ou `npc`) pra registrar quem decidiu, em vez de duas ferramentas
  escrevendo por caminhos diferentes no mesmo QuestLog. `atualizar_missao` não existe
  mais.
- O objetivo de vida do personagem (definido na criação, aparece na ficha e no prólogo)
  e o objetivo de uma cena de combate (o `[OBJETIVO]` que aparece durante um confronto)
  não mudaram — já tinham nomes e contextos próprios, então não faziam parte da confusão.

## Por que isso importa

Duas ferramentas de IA fazendo a mesma coisa por caminhos diferentes não é só estética:
é o tipo de ambiguidade que produz bug de comportamento (o Mestre escolhendo a ferramenta
"errada") que nenhum teste automatizado pega, porque o bug está na decisão do modelo, não
no código. Reduzir pra uma ferramenta com um campo explícito tira essa ambiguidade sem
tirar a diferença de significado que ela protegia.

## Como testar

Os 677 testes do backend e os do frontend continuam passando; a mudança de ferramenta do
Mestre ainda depende de uma sessão jogada ao vivo pra confirmar que o modelo usa `origem`
do jeito esperado — teste automatizado com sequência fixa não pega "o modelo escolheu mal
a ferramenta".
