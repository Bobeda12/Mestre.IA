# ADR-0046 — Banco de arquétipos de papel, com personalidade para a IA

**Data:** 07/10/2026
**Status:** Aceito
**Etapa:** Plano "Texto livre confiável e progressão" (Fase 3.5)
**Supersede:** — (estende o ADR "pele de arquétipo", Parte 2 item J da rodada de conserto)

---

## Contexto

Quando o narrador propunha um inimigo com nome de história ("Rei Ruan"), o servidor usava
uma **pele**: a ficha era de um monstro sorteado da banda do nível e só o nome mudava. O
sorteio não tinha relação com quem o personagem era, então o "rei" podia ser um lobo.
O bestiário era todo de criaturas (Goblin, Orc, Troll); faltavam pessoas com um jeito de
lutar. E o texto de personalidade (`comportamento`) existia na ficha, mas não chegava
a nenhuma IA.

## Decisão

**1. Banco de arquétipos de papel.** 19 fichas novas em `data/monsters.json`, marcadas com
`por_papel`, `papel` (ladino, bruto, mago, guarda, assassino, nobre, comandante, clérigo),
`temperamento` (medroso, orgulhoso, fanático, astuto, sádico, honrado), uma `persona` de
duas frases e um `sprite` emprestado de uma criatura (ainda não há arte própria).
Cobrem os níveis 1 a 8; os níveis 9 e 10 usam as mesmas bandas do 8. Exemplos: o Rei
Medroso (nível 4, covarde, foge a 60% de vida) e o Rei Tirano (nível 7, tática de matilha:
luta cercado dos seus).

**2. Seleção por sentido.** `iniciar_combate` aceita `perfis` (`nome`, `papel`,
`temperamento`). O servidor (`services/arquetipos.py`) traduz sinônimos ("rei" → nobre,
"covarde" → medroso), filtra as fichas das bandas do nível e pontua: papel vale 2,
temperamento vale 1. Empate é desfeito pela semente, como todo o resto. Sem afinidade,
o sorteio da banda de sempre. O nome da história vira a pele, mas agora de uma ficha que
combina.

**3. A personalidade chega à IA do combate.** A `persona` entra no prompt da narração da
rodada ("só para o tom; não crie falas nem fatos") e o `temperamento` entra no prompt do
juiz de improviso (intimidar um medroso é mais fácil; um fanático não recua).

**4. As fichas de papel não entram no sorteio comum**: `get_monstros_por_banda` as
exclui. Um lobo não vira "Rei Medroso" por acaso. Quem pede o nome exato da ficha, no
nível certo, recebe a ficha.

## Consequências

- O `tests/test_bestiario.py` exigia um sprite com o nome da ficha; agora aceita o
  campo `sprite`. O front passou a considerar `inimigo.sprite` primeiro.
- Medição (evals/simulador, bot tático, 3 classes): as fichas ficaram na faixa dos monstros
  comuns da banda, com 3 exceções fáceis no nível exato (Saqueador Medroso, Guarda
  Corrupto e Nobre Duelista vencem em ~100%). O Rei Medroso é fácil de propósito.
- O XP dessas fichas copia o da banda; a curva de XP inteira é da Fase 4.
- A tool `iniciar_combate` ganhou o campo `perfis`; só entra no prompt quando o grupo
  de combate está ativo.
- **Não feito:** chefes de arco ainda usam a ficha reservada, sem papel/temperamento; a
  rendição e a súplica por temperamento dependem de `foge_abaixo` e da narração, sem
  regra nova no motor.

## Alternativas descartadas

- **Fichas completas geradas pela IA.** Número de combate vindo do modelo quebra o balanço.
- **Misturar os arquétipos de papel no sorteio comum.** Nomes como "Rei Medroso" apareceriam
  em qualquer luta sem contexto.
