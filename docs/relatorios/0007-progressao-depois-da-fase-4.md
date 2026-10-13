# Relatório 0007 — Progressão de campanha depois da Fase 4

**Data:** 07/10/2026 · **Reproduzir:** `uv run python -m evals.campanha --campanhas 200` (em `Backend/`) · compara com o [0006](0006-progressao-campanha.md).

## O que mudou entre os dois relatórios

- A curva de XP foi refeita (150, 425, 1000, 2400, 4800, 8500, 14500, 26500, 45000).
- XP de passo de trilha, pista, acordo, objetivo de cena e fim de arco virou fração do que falta
  para o próximo nível (1/8, 1/20, 1/4, 1/6 e 2/5), em vez de constantes.
- Itens encantados entram nos saques das bandas 3 em diante, nos chefes e nas recompensas de arco.

## Resultado

| Nível | Encontros p/ subir (antes → depois) | Ouro no nível (antes → depois) | Itens no nível (antes → depois) |
|---|---|---|---|
| 1 | 2,5 → 3,6 | 9 → 13 | 0,6 → 0,9 |
| 2 | 1,7 → 3,4 | 8 → 24 | 0,5 → 1,6 |
| 3 | 1,3 → 2,6 | 12 → 49 | 0,6 → 2,5 |
| 4 | 1,0 → 4,4 | 16 → 60 | 0,6 → 2,2 |
| 5 | 1,0 → 3,0 | 50 → 116 | 1,6 → 3,4 |
| 6 | 1,0 → 4,7 | 47 → 143 | 1,2 → 3,4 |
| 7 | 1,0 → 3,4 | 46 → 182 | 0,9 → 3,9 |
| 8 | 1,0 → 5,4 | 56 → 325 | 0,8 → 4,3 |
| 9 | 1,0 → 3,8 | 87 → 380 | 0,9 → 4,5 |

## Leitura

1. **Acabou o "um encontro, um nível".** Do nível 4 em diante o herói agora precisa de 3 a 5 encontros.
   A média simulada ficou entre 2,6 e 5,4, a faixa que a curva pretendia (3 a 7).
2. **Itens e ouro cresceram junto**, em parte porque mais encontros acontecem por nível e em parte pelos
   encantados e pelo arco. O ouro ainda é pouco perto do preço de um item encantado (150 a 5000), então
   passa a existir motivo para gastar.
3. **Os níveis 3, 5, 7 e 9 saem mais rápido (2,6 a 3,8)** porque o arco fecha a cada 8 encontros na simulação
   e paga 2/5 de um nível. É uma suposição da simulação; no jogo real o arco leva mais tempo.

## O que continua ruim

- **Variedade:** 4 a 7 inimigos distintos por nível (o banco de arquétipos de papel entra por escolha do narrador, não no
  sorteio comum, então não aparece aqui), com um inimigo em 16 a 26% dos encontros.
- **O nível 10 acumula** ~1900 de ouro em 20 encontros sem novo sumidouro além das compras.
- A simulação assume vitória e 8 encontros por arco.

## Salvaguardas

- Saves antigos mantêm o nível e o XP. Quem já estava no nível 5 com 650 XP passa a precisar de 4800 para o 6.
  Não há demotamento; só o ritmo ficou mais lento.
