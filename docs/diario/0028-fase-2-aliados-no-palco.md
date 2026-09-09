# Fase 2 do plano "jogo completo": aliados no palco

**Período:** 08/09/2026 · mesma sessão das Fases 0 e 1

## O que aconteceu

Companheiros recrutados já existiam por baixo desde a revisão de gameplay (ADR-0027): o
narrador podia recrutar um NPC, ele tinha PV, atacava por ferramenta e o dano persistia
entre turnos. Nada disso aparecia na tela — o backend mandava a lista de aliados em todo
frame e o frontend a ignorava. Esta fase é curta e é só isso: o companheiro passa a ser
visto e comandado.

## O que o jogador sente

- **O companheiro está no palco**, entre o herói e os inimigos, com retrato da raça, barra
  de vida azul e uma tag que diz o estado: PRONTO, JÁ AGIU ou CAÍDO (ALIADO fora de
  combate).
- **Ele ataca por botão.** Escolha um inimigo, clique em ATACAR no card do aliado e o juiz
  resolve na hora, sem narrador. Depois disso o botão trava até a próxima rodada — e a
  rodada só vira quando o herói faz a ação dele, como sempre foi.
- O narrador continua podendo fazer o mesmo por texto ("Ana, ataca o goblin"), e sabe no
  prompt quem já agiu nesta rodada.

## O bug que precisava ser fechado antes

A contagem de "esse aliado já agiu" morava num conjunto criado a cada request. Pelo chat
isso funcionava (um turno = um request), mas pelo botão cada clique é um request novo, e o
aliado atacaria sem limite. A contagem mudou para o estado do combate
(`CombatState.aliados_agiram`) e é zerada quando a rodada termina. Sem migration: é JSON.

## Como testei

- Testes: um aliado não ataca duas vezes na mesma rodada mesmo em executores diferentes; a
  rodada libera; raça inválida vira Humano; rota com aliado morto ou inexistente responde
  400. Suíte inteira verde, ruff, mypy e typecheck do frontend limpos.
- Ao vivo pela API (combate montado no banco, a cota dos provedores já tinha acabado):
  Ana ataca pelo `/game/action`, segunda tentativa na mesma rodada recusada, o ataque do
  herói fecha a rodada e ela volta a ficar PRONTA.
- No navegador: Ana no palco com retrato de elfa, clique em Goblin e depois em ATACAR,
  rolagem "d20(12)+4=16 vs CA 10 → ACERTO! 4 de dano", goblin 26/30, tag JÁ AGIU e botão
  desabilitado.

## O que ficou registrado para depois

- Recrutar continua sendo decisão do narrador (`recrutar_aliado`); o jogador não tem
  botão para isso — faz sentido, é a cena que decide quem se junta.
- O aliado não usa item nem técnica, só ataca. Se um dia importar, é a mesma fatia de
  trabalho que deu ao herói as técnicas.

## Próximo passo

Fase 3: level-up com escolha (modal ao subir de nível, talentos por classe, especialização
dos marcos 3 e 7 na mesma tela; `escolher_especializacao` já saiu das ferramentas do
narrador na Fase 0).
