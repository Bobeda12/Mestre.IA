# Relatório 0006 — Progressão de campanha (antes da Fase 4)

**Data:** 07/10/2026 · **Como reproduzir:** `uv run python -m evals.campanha --campanhas 200 --passo-a-cada 3` (em `Backend/`).

## O que foi medido (em termos simples)

O simulador joga 200 campanhas "de mentira", sem IA, usando as mesmas peças do jogo
(o sorteio de inimigos, o saque e a curva de XP). Ele **assume que o herói sempre vence** e só
conta o que cada vitória rende: quantos encontros até subir de nível, quanto ouro e quantos itens
entram, e quantos inimigos diferentes aparecem. Um passo da trilha vale 50 XP a cada 3 encontros e
um arco fecha a cada 8 encontros.

## Resultado

| Nível | Encontros para subir | Ouro ganho no nível | Itens no nível | Inimigos distintos | Mais frequente |
|---|---|---|---|---|---|
| 1 | 2,5 | 9 | 0,6 | 4 | Lobo (26%) |
| 2 | 1,7 | 8 | 0,5 | 7 | Goblin (18%) |
| 3 | 1,3 | 12 | 0,6 | 6 | Múmia (19%) |
| 4 | 1,0 | 16 | 0,6 | 5 | Troll (23%) |
| 5 | 1,0 | 50 | 1,6 | 5 | Espectro (22%) |
| 6 | 1,0 | 47 | 1,2 | 6 | Urso-Coruja (22%) |
| 7 | 1,0 | 46 | 0,9 | 6 | Elemental de Fogo (19%) |
| 8 | 1,0 | 56 | 0,8 | 6 | Golem de Pedra (20%) |
| 9 | 1,0 | 87 | 0,9 | 5 | Dragão Adulto Jovem (24%) |
| 10 (teto, 20 enc.) | — | 1916 | 22,2 | 5 | Lich Menor (20%) |

## O que isso quer dizer

1. **A curva de XP está quebrada do nível 4 em diante.** Um só abate rende mais XP do que falta para o
   próximo nível (um Troll vale 400; o nível 4→5 pede 230). O herói chega ao nível 10 em cerca de 15
   encontros. A "história que não cresce" que você sentiu tem esta raiz: o personagem sobe rápido
   demais para o mundo acompanhar. O XP de passo de trilha (50) é irrelevante.
2. **O ouro não pesa.** Em quase todos os níveis entram menos de 60 moedas, e uma poção custa 25. No
   teto, 20 encontros rendem ~1900 moedas sem nenhum lugar para gastar.
3. **Variedade baixa.** Só 4 a 7 inimigos diferentes por nível, e um deles aparece em 20–26% dos
   encontros. Nos níveis 9 e 10 são os mesmos 5.
4. **Itens são poucos e comuns** (cerca de 1 por nível), e do mesmo catálogo que se compra.

## Limites da medição

- Não mede se o herói sobrevive (isso é do `evals/simulador.py`).
- O narrador propõe 1 inimigo por encontro no modelo; no jogo real pode propor até 3.
- Os 8 encontros por arco são uma suposição; o jogo não fixa esse número.

## Consequência para o plano

A Fase 4 ganha uma tarefa que não estava escrita: **refazer a curva de XP** (XP de abate escalado pelo
nível do herói contra o nível do monstro, e limiares maiores), antes de mexer em loot. O restante
(raridade, sumidouros de ouro, banco de arquétipos) segue como planejado.
