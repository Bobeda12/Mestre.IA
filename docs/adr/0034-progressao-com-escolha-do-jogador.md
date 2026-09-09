# ADR-0034 — Progressão com escolha do jogador, números do servidor

**Data:** 08/09/2026
**Status:** Aceito
**Etapa:** Plano "jogo completo" (Fase 3 — ver `docs/diario/0029-fase-3-level-up-com-escolha.md`)
**Supersede:** nada — estende ADR-0026 (curva de XP própria) e a especialização dos marcos 3/7 do Mundo Vivo

---

## Contexto

Subir de nível era automático e invisível: PV, técnica nova em 3 e 7, Foco em 4 e 8. O
jogador não decidia nada. A única escolha de progressão (especialização explorador /
diplomata / combatente nos níveis 3 e 7) estava escondida num `<details>` do painel do
mundo e também exposta como ferramenta do narrador — o modelo podia escolher pelo
jogador. O autor pediu "level-up com escolha" (08/09/2026).

## Decisão

1. **Cada nível novo deixa uma escolha pendente** (`WorldState.niveis_pendentes`), feita
   pelo jogador num modal: nos níveis 2, 4, 5, 6, 8, 9 e 10, +1 num atributo (teto 20) ou
   um **talento**; nos níveis 3 e 7, a especialização. Subir continua automático (PV,
   técnicas, Foco); só a escolha espera.
2. **Talentos são números em canais que o motor já tem**, nunca regra em texto
   (`services/talents.py`): dano (soma em `CombatState.bonus_especializacao`), Defesa
   (`bonus_extra` de `calcular_defesa`, recalculada ao escolher e ao equipar), PV por nível
   (retroativo), vantagem num atributo em `rolar_teste`, desconto no mercador. Catálogo
   pequeno: 7 comuns e 1 por classe, alguns com nível mínimo.
3. **A escolha nunca é ferramenta do narrador.** `escolher_nivel` só existe na rota
   `/game/action`; `escolher_especializacao` saiu das ferramentas na Fase 0. O narrador
   recebe `[PROGRESSÃO]` com os talentos e a instrução de lembrar a pendência sem decidir.
4. **Sem migration:** pendências e talentos vivem no `world_state` (JSON), como o resto do
   Mundo Vivo. Saves antigos têm lista vazia — nada muda até o próximo nível.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Talentos descritos em texto e interpretados pelo narrador | Variedade infinita | O efeito viraria opinião do modelo (ADR-0006) e o RollCard mentiria | Um talento que "dá vantagem" é regra, não frase |
| Escolha obrigatória antes de continuar jogando | Ninguém esquece | Trava o jogo no meio de uma cena; em combate é impossível | "Decidir depois" esconde o modal até a próxima subida; a pendência fica na ficha |
| Árvore de talentos por classe (3 níveis, pré-requisitos) | Mais profundo | Mais 100 linhas de dados para balancear e uma tela nova; o simulador ainda não roda | Catálogo plano primeiro; a árvore cabe depois no mesmo formato |

## Consequências

**Ganhamos:** a subida de nível vira um momento com decisão; talentos mudam números que o
jogador vê na hora (Defesa no HUD, dano no card).

**Pagamos:** uma linha `[PROGRESSÃO]` no prompt quando há talento ou pendência; a vitrine
pública do painel do mundo não aplica o desconto de talento (a compra real, por
`comerciar`, aplica).

**Fica em aberto:** balanceamento dos talentos por simulação (Fase 5 traz o bestiário
alto; rodar o harness com e sem talentos).

## Como saber que erramos

- Se os jogadores escolherem sempre o mesmo talento, os outros não valem o número que têm.
- Se o narrador "conceder" talentos em texto, o prompt precisa dizer mais claramente que
  progressão é da ficha, não da cena.

## Referências

- ADR-0026 — curva de XP própria; ADR-0027 — companheiros; ADR-0033 — catálogo de itens
- Plano "jogo completo", Fase 3
