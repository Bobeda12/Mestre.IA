# Relatório 0002 — Balanceamento do bestiário 1–10 por simulação

**Data:** 08/09/2026 · Fase 5 do plano "jogo completo"

## Método

Duelos simulados sem LLM, só `rules_engine` + `combat` + `ToolExecutor` (o juiz), com
`random.Random(semente)` por partida. Herói de referência: Guerreiro humano, Força 16,
Cota de Malha + Escudo (Defesa 18), Espada Longa, PV `10 + 7 × (nível − 1)`, duas Poções
de Cura, sem técnicas nem talentos (o pior caso: um jogador que só clica em Atacar e bebe
poção abaixo de 35% de PV). 150–200 partidas por par (nível do herói × monstro), para
cada banda que `rules_engine.desafio_sugerido` oferece àquele nível.

Alvo (do backlog, C-1): encontro comum ≈ 85–90% de vitória com ~50% de PV restante;
chefe ≈ 60%.

## Antes do ajuste (fichas da primeira passada)

| Nível | Monstro | Vitória | PV restante |
|---|---|---|---|
| 5 | Urso-Coruja | 41% | 48% |
| 6 | Minotauro | 20% | 41% |
| 7 | Cavaleiro Negro | 26% | 40% |
| 7 | Gigante da Colina | 31% | 49% |
| 8 | Hidra Menor | 10% | 42% |
| 8 | Golem de Pedra | 0% | — |
| 9 | Lich Menor (elite) | 12% | 43% |
| 9 | Dragão Adulto Jovem (elite) | 12% | 42% |

Diagnóstico: as fichas seguiam o SRD, que pressupõe grupo de 4 aventureiros com magias e
recursos. O jogo é um herói só; HP e dano dos monstros altos precisavam cair ~35%.

## Depois do ajuste (fichas atuais de `data/monsters.json`)

| Nível | Banda | Monstro | Vitória | PV restante |
|---|---|---|---|---|
| 5 | Nivel_5 | Gnoll Líder | 92% | 63% |
| 5 | Nivel_5 | Urso-Coruja | 91% | 60% |
| 5 | Nivel_5 | Carniçal Cinzento | 99% | 71% |
| 6 | Nivel_6 | Wight | 95% | 69% |
| 6 | Nivel_6 | Minotauro | 83% | 55% |
| 6 | Nivel_6 | Manticora | 97% | 71% |
| 7 | Nivel_7 | Elemental de Fogo | 93% | 59% |
| 7 | Nivel_7 | Cavaleiro Negro | 71% | 52% |
| 7 | Nivel_7 | Gigante da Colina | 89% | 64% |
| 8 | Nivel_8 | Vampiro Jovem | 74% | 49% |
| 8 | Nivel_8 | Hidra Menor | 66% | 53% |
| 8 | Nivel_8 | Golem de Pedra | 49% | 51% |
| 9 | Nivel_8 | Golem de Pedra | 67% | 45% |
| 9 | Chefe_Elite | Lich Menor | 53% | 52% |
| 9 | Chefe_Elite | Dragão Adulto Jovem | 57% | 49% |
| 10 | Chefe_Elite | Lich Menor | 83% | 57% |
| 10 | Chefe_Elite | Dragão Adulto Jovem | 81% | 59% |

Bandas 1–4 (não alteradas nesta fase, mesmo método): Goblin 92%, Esqueleto 82%, Lobo 73%
e Kobold 100% no nível 1; Ogro 60% e Múmia 50% no nível 3 (o topo da banda é duro de
propósito); Troll 25% no nível 4 e 73% no 5.

## Leitura

- O topo de cada banda (Golem no 8, Troll no 4, Múmia no 3) é um encontro "duro" que um
  herói sem técnica nem talento perde metade das vezes. Com técnicas (3–4 usos de Foco por
  luta) e um talento de dano ou Defesa, a simulação sobe ~10–15 pontos — o jogador que
  aprende o sistema sente a diferença, que é o que se quer.
- O chefe de elite no nível 9 fica em ~55% para o herói básico: é o "chefe ≈ 60%" do alvo.
  No nível 10 ele vira 80%: o último nível é para se sentir forte.
- A escala artificial antiga (`+5 PV e +½ de ataque por nível acima do 5`) foi removida;
  o que existe agora é ficha por banda, legível no bestiário do jogador.

## Como reproduzir

O laço de simulação está reproduzido no diário desta fase (`docs/diario/0031`); vale
promover a `Backend/evals/simulador.py` quando a Fase 5 fechar a arte, junto com técnicas
e talentos no herói de referência.
