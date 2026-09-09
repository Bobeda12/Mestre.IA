# Fase 5 do plano "jogo completo": bestiário 5–10 e o chefe do arco

**Período:** 08/09/2026 · mesma sessão das Fases 0 a 4

## O que aconteceu

O bestiário terminava no nível 4, e do 5 em diante o jogo fingia: repetia os dois chefes e
somava PV e ataque por nível para os monstros não ficarem ridículos. Esta fase dá fichas de
verdade aos níveis 5 a 10 e liga o chefe ao arco (Fase 4): cada capítulo tem um vilão com
ficha reservada, que o narrador só nomeia e apresenta quando o confronto chega.

## O que o jogador sente

- **Monstros novos do nível 5 ao 10**, três por banda: Gnoll Líder, Urso-Coruja, Carniçal
  Cinzento, Wight, Minotauro, Manticora, Elemental de Fogo, Cavaleiro Negro, Gigante da
  Colina, Vampiro Jovem, Hidra Menor, Golem de Pedra; e dois chefes de elite, Lich Menor e
  Dragão Adulto Jovem. Cada um com comportamento próprio, que o card de inimigo já mostra.
- **O chefe do capítulo é sorteado quando o arco abre** (pela semente da aventura, não
  pelo narrador). O prompt avisa o narrador que existe um chefe reservado; quando a cena
  chega ao confronto, ele chama `iniciar_combate` com `chefe=true`, dá um nome à criatura
  ("O Carrasco de Vharn") e o servidor usa a ficha reservada, fora do orçamento de
  encontro. Vencer marca o arco como fechável por vitória.
- **Balanceado por simulação, não por achismo.** 150–200 duelos por par nível × monstro
  com um herói básico (só Atacar e poção). A primeira passada, tirada do SRD, era dura
  demais para um herói sozinho (Golem de Pedra: 0% de vitória no nível 8); depois do ajuste,
  encontros comuns ficam entre 83% e 99% com metade a dois terços da vida, o topo de cada
  banda em ~50–70%, e o chefe de elite em ~55% no nível 9. Tabela completa em
  [`docs/relatorios/0002-balanceamento.md`](../relatorios/0002-balanceamento.md).

## O que mudou por baixo

- `rules_engine.BANDA_POR_NIVEL` cobre 1–10 com bandas dedicadas; a escala artificial de
  `combat.iniciar_combate` saiu. `data/loot.json` ganhou saque para as bandas novas.
- `combat.iniciar_combate(chefe_reservado=...)` cria o chefe com a pele proposta e depois
  monta o resto do encontro como sempre; `CombatState.chefe_do_arco` liga a vitória a
  `marcar_chefe_enfrentado`.
- `regras.chefes_para_nivel`: fichas de "Chefe" até o nível 5, "Chefe_Elite" depois.
- Frontend: `spriteInimigo` passou a mapear por slug do arquétipo; adicionar arte é só
  colocar o PNG em `assets/monstros/` e o slug em `SPRITES_MONSTROS`.

## Como testei

- 7 testes em `tests/test_bestiario.py` (bandas 1–10 sem lacuna e sem "Chefe" na banda;
  toda ficha parseável com saque; sem escala artificial; chefe reservado fora do orçamento
  com a pele; origem e `abrir_arco` sorteiam chefe; `iniciar_combate(chefe=true)` usa a ficha
  e a vitória fecha o arco, sem repetir; saque das bandas altas). Suíte: 544 verdes; ruff,
  mypy e typecheck limpos.
- Simulação (relatório 0002).
- Ao vivo com o narrador: não nesta sessão — a cota diária do Groq acabou na Fase 4. O
  fluxo "narrador nomeia o chefe e chama `iniciar_combate` com `chefe=true`" fica para o
  próximo dia com cota, junto com `abrir_arco` e `comerciar` pelo texto.

## O que ficou registrado para depois

- ~~Sprites dos monstros~~ — feito na mesma sessão, com a decisão do autor: baixei o pacote
  Dungeon Crawl 32×32 (CC0, já creditado) e extraí um tile por arquétipo (28 de 28 com
  arte; `docs/CREDITOS.md` lista tile por monstro). Mantidos em 32×32 como os retratos de
  raça; o palco escala para 80 px. Confirmado no navegador: um combate com "Vharn, o
  Devorador" (pele sobre a ficha do Dragão Jovem) e um Golem de Pedra mostra os dois
  sprites novos, legíveis, com o dragão verde e o golem cinza no lugar da caveira.
- O laço da simulação merece virar `Backend/evals/simulador.py`, com técnicas e talentos no
  herói de referência.
