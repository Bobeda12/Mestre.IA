# ADR-0033 — Catálogo de itens com números e itens inventados só com tags

**Data:** 08/09/2026
**Status:** Aceito
**Etapa:** Plano "jogo completo" (Fase 1 — ver `docs/diario/0027-fase-1-economia-e-itens.md`)
**Supersede:** o mapa `_EFEITOS_ITENS` de `services/tools.py` (uma única poção com efeito) e a
heurística por palavra-chave do `InventoryGrid.tsx`

---

## Contexto

Até aqui o inventário era uma lista de nomes. Só "Poção de Cura" fazia alguma coisa; ouro
só saía (`gastar_ouro`) e nunca entrava; não existia armadura, equipar, loja nem saque. O
narrador entregava qualquer item por `dar_item`, e o item existia como palavra — o
frontend adivinhava se era arma ou poção olhando o nome.

O autor decidiu (08/09/2026) que itens precisam ter peso mecânico sem tirar a liberdade
do narrador de inventar coisas.

## Decisão

**Dois mundos, uma fronteira.**

1. **Catálogo com números** (`data/items.json`, `data/weapons.json`): consumíveis com
   efeito (`cura`, `foco`, `remover_efeitos`, `dano_area`, `bonus_dano_temporario`,
   `esconder`), armaduras (`categoria` leve/média/pesada, `ca_base`, `forca_min`),
   escudos (`ca_bonus`), ferramentas com tags, armas com `preco`. Validado no boot
   (`DataManager` → `ItemCatalogo`): JSON torto derruba o servidor na subida, não no
   meio de um combate. Nomes aceitam acento e caixa diferentes (`nome_canonico`).
2. **Itens inventados** pelo narrador (`WorldState.itens_inventados`): `dar_item` fora do
   catálogo exige `descricao` e até 3 `tags` de um vocabulário fechado (Fogo, Luz, Sagrado,
   Utilidade, Cura, Foco, Veneno, Gelo, Leve, Pesada, Afiado, Arcano). O único poder de um
   item inventado é o bônus de tag em `rolar_teste`. Nunca cura, nunca dá CA, nunca vale
   mais que 1 de ouro na venda.

**Slots equipados** (`Personagem.equipamento`, migration 0016): arma, armadura, escudo.
`Personagem.defesa` passa a ter uma única fonte, `rules_engine.calcular_defesa` (sem
armadura 10+DES; leve base+DES; média base+min(DES,2); pesada base; escudo +2). O servidor
decide o slot pela ficha, valida força mínima e escudo × arma de duas mãos. A arma equipada
é a preferida no ataque, atrás só da proposta explícita do jogador.

**Ouro entra por dois canais, e só dois:** saque determinístico por banda do bestiário na
vitória (`services/loot.py`, `data/loot.json`, RNG derivado de semente + turno para não
mexer nos dados do combate) e, na Fase 4, a recompensa de arco.

**Mercador** = uma `PessoaMundo` com `mercadoria` (nomes do catálogo; o resto é
descartado no registro). Preços são do servidor: compra `preco × (1 − confiança/400)`,
venda `preco // 2`. A tool `comerciar` e o balcão do painel passam pela mesma função.

**Decisões do jogador pela interface, não pelo narrador:** equipar, guardar, usar e
comprar/vender têm botões que chamam `/game/action` sem LLM. O narrador tem as mesmas
tools para quando o jogador escreve em vez de clicar.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Só catálogo fixo | Previsível | O narrador não pode entregar o "Amuleto de Osso" que a cena pediu | Liberdade é a tese do jogo |
| Narrador escreve o efeito do item (`{"cura": "3d8"}`) | Mais variedade | Número decidido pelo LLM — exatamente o que o ADR-0006 proíbe | Um item que cura é uma regra, não uma frase |
| Equipamento em JSON dentro de `world_state` | Sem migration | `combat.escolher_arma` e a Home não recebem `world_state`; ficha é ficha | Coluna própria, mesmo padrão de `aliados` |
| Saque decidido pelo narrador por `dar_item` | Já existia | Ouro nunca entrava; o modelo esquece ou exagera | Vitória é o único evento que o servidor tem certeza que aconteceu |

## Consequências

**Ganhamos:** economia fechada (ouro entra e sai), defesa que muda com o que se veste,
consumíveis que fazem coisas diferentes, e o frontend lendo tipo/tags do servidor em vez
de adivinhar por palavra.

**Pagamos:** três tools a mais no conjunto de exploração (`equipar`, `desequipar`,
`comerciar`); `equipar` também em combate (custa a ação). Medido dentro do teto de tokens
da Fase 0. `equipamento_inicial` das classes tem nomes fora do catálogo ("Adagas (2)",
"Foco Arcano"): continuam na mochila como itens sem ficha, sem prejuízo.

**Fica em aberto:** proficiência de arma por classe continua não valendo no ataque (adiado
desde a rodada de conserto); raridade e itens mágicos com efeito passivo não existem — se
entrarem, entram no catálogo, nunca por texto.

## Como saber que erramos

- Se o modelo insistir em `dar_item` sem tags e o jogador ficar sem o item que a cena
  prometeu, o prompt precisa de um exemplo, ou o servidor precisa aceitar sem tags
  (item puramente narrativo, sem bônus).
- Se o saque por vitória deixar o herói rico cedo demais, `data/loot.json` é o único
  lugar a mexer.

## Referências

- ADR-0002, ADR-0006 — o modelo propõe, o servidor decide
- ADR-0029 — pele × ficha (o mesmo padrão, aplicado a monstros)
- Plano "jogo completo", Fase 1
