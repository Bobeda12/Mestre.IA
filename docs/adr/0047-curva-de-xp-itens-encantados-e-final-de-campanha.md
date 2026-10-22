# ADR-0047 — Curva de XP, itens encantados e final de campanha

**Data:** 07/10/2026
**Status:** Aceito
**Etapa:** Plano "Texto livre confiável e progressão" (Fase 4)
**Supersede:** revisa a curva do ADR-0026 (limiares) e o XP fixo do ADR-0035/0039

---

## Contexto

O relatório [0006](../relatorios/0006-progressao-campanha.md) mediu o que o jogador sentia:
do nível 4 em diante um único encontro subia de nível (um Troll valia 400 XP e faltavam 230),
o XP de passo da trilha (50) e de arco ficava irrisório, o ouro entrava sem lugar para sair
e o loot era o mesmo do catálogo que se compra.

## Decisão

**1. Curva refeita.** `XP_POR_NIVEL` passa a 0, 150, 425, 1000, 2400, 4800, 8500, 14500, 26500,
45000. Cada nível custa de 3 a 7 encontros típicos da faixa do herói (o XP médio do encontro vem
de `data/monsters.json`).

**2. XP proporcional ao nível.** `rules_engine.xp_do_nivel(nivel, fracao)` devolve uma fração do
que falta para o próximo nível. Passo de trilha vale 1/8, pista investigada 1/20, conflito
resolvido por acordo 1/4, objetivo de cena 1/6 e fim de arco 2/5 (metade se for "consequência").
O XP de abate continua o da ficha do monstro.

**3. Itens encantados.** `weapons.json` ganha o grupo `Mágicas` (10 armas, +1 a +3, com raridade),
`items.json` ganha 5 armaduras e escudos encantados (CA maior). O campo `bonus` da arma soma no
acerto e no dano e aparece como "Arma encantada" no card de ataque. `loot.json` ganha a tabela
`raros` por banda (8% a 18% nas bandas 3 a 8, 60% no chefe comum, 100% no chefe de elite) e nas
recompensas de arco de nível 3, 5 e 8.

**4. O ouro vira compra de verdade.** Os encantados têm preço de 120 a 5000 e entram no catálogo,
então um comerciante pode vendê-los (e o servidor já valida o nome). Não foi criada uma ferramenta
nova de estalagem ou treino: o prompt de entrada está rente ao teto do provedor.

**5. Final de campanha.** Ao fechar um arco por vitória contra um chefe da banda `Chefe_Elite` com
o herói no nível 8 ou mais, `WorldState.campanha_concluida` vira verdadeiro, ganha um marco e um
evento, e o prompt do narrador recebe uma linha "pós-jogo". O mundo segue; novos arcos continuam
possíveis.

## Consequências

- Saves existentes mantêm o nível e o XP. O ritmo para o próximo nível fica mais lento (um herói
  no nível 5 com 650 XP precisa de 4800 para o 6). Não há demotamento.
- O teto de 20 turnos por dia por conta passa a pesar mais: chegar ao nível 10 pede ~47 encontros.
- Fichas e testes que usavam 100 XP para o nível 2 foram atualizados para ler a tabela.
- Os encantados com nome composto ("Espada Longa +2, Lâmina da Aurora") são nomes de catálogo
  longos; servem de ponto de partida para o autor reescrever.
- **Não feito:** sumidouro dedicado (estalagem paga, treino, conserto) e arte própria para os
  encantados; "arcos encadeados com consequência persistente" ficou só nos marcos e nos lugares
  revelados (ADR-0045).

## Alternativas descartadas

- **Escalar o XP do abate pela diferença de nível.** Mais fiel ao D&D, mas esconde a curva em duas
  tabelas; mexer nos limiares é a mudança mais simples de explicar e de medir.
- **Uma ferramenta nova de estalagem.** Custaria tokens no prompt sem alterar o essencial: o ouro
  precisava de algo que valesse a pena comprar, e agora existe.
