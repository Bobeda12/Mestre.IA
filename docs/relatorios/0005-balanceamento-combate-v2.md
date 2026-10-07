# Relatório 0005 — Balanceamento do Combate v2

**Data:** 07/10/2026 · Fase 8 do plano "Trilha do capítulo + Combate v2"

## O que foi medido

As mesmas lutas do relatório 0004, agora no combate novo (fila de turnos, distância,
ação bônus, resistências, Foco que acaba) e com as classes já diferenciadas.

Método: `Backend/evals/simulador.py`, 150 duelos por combinação de classe, nível (1 a 10) e
monstro, sem IA, pelo mesmo caminho de um clique do jogador. O herói chega descansado, com
o equipamento inicial e duas poções.

```bash
uv run python -m evals.simulador --n 150 --classes todas --bot tatico
uv run python -m evals.simulador --n 150 --classes todas --bot basico
```

Dois jogadores simulados:

- **básico:** só ataca e bebe poção com pouca vida.
- **tático:** usa a ação bônus da classe, a técnica mais forte que o Foco paga, cura só
  quando ferido, e recua quando a classe recua sem levar golpe.

## Encontros comuns

Vitória média contra os monstros das bandas do nível, por classe.

| Classe | Antes (rel. 0004), tático | Agora, tático | Agora, básico | Rodadas (tático) |
|---|---|---|---|---|
| Bárbaro | 88% | 98% | 78% | 2,4 |
| Bruxo | 79% | 96% | 59% | 2,0 |
| Guerreiro | 95% | 96% | 85% | 2,7 |
| Patrulheiro | 96% | 92% | 66% | 2,8 |
| Bardo | 62% | 91% | 53% | 3,0 |
| Paladino | 94% | 91% | 86% | 4,6 |
| Monge | 88% | 90% | 60% | 2,6 |
| Clérigo | 77% | 85% | 58% | 4,2 |
| Feiticeiro | 53% | 85% | 46% | 3,1 |
| Ladino | 72% | 85% | 64% | 3,4 |
| Druida | 76% | 84% | 56% | 4,4 |
| Mago | 70% | 83% | 47% | 3,8 |

A distância entre a melhor e a pior classe, com o jogador tático, caiu de 43 pontos (53% a
96%) para 15 (83% a 98%).

Por nível (tático, média dos encontros comuns):

| Classe | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9 | 10 |
|---|---|---|---|---|---|---|---|---|---|---|
| Bárbaro | 100 | 98 | 97 | 95 | 98 | 99 | 99 | 98 | 98 | 99 |
| Bruxo | 93 | 93 | 97 | 98 | 97 | 99 | 97 | 93 | 94 | 97 |
| Guerreiro | 99 | 98 | 92 | 88 | 97 | 99 | 96 | 97 | 96 | 99 |
| Patrulheiro | 98 | 98 | 92 | 86 | 92 | 99 | 88 | 86 | 85 | 93 |
| Bardo | 94 | 92 | 88 | 81 | 92 | 98 | 91 | 85 | 89 | 95 |
| Paladino | 96 | 95 | 83 | 79 | 90 | 97 | 94 | 90 | 92 | 97 |
| Monge | 97 | 96 | 79 | 79 | 90 | 97 | 88 | 89 | 90 | 96 |
| Clérigo | 95 | 94 | 87 | 77 | 86 | 98 | 81 | 70 | 66 | 84 |
| Feiticeiro | 86 | 92 | 80 | 71 | 82 | 94 | 89 | 78 | 82 | 92 |
| Ladino | 93 | 94 | 77 | 74 | 85 | 94 | 85 | 77 | 79 | 91 |
| Druida | 95 | 93 | 86 | 77 | 82 | 98 | 78 | 68 | 67 | 84 |
| Mago | 82 | 90 | 81 | 66 | 74 | 93 | 84 | 77 | 82 | 92 |

## Contra a meta do plano

| Meta | Resultado |
|---|---|
| Nenhuma classe fora de 75–97% (tático, comum) | **Não cumprida por inteiro.** Na média por classe, só o Bárbaro passa (98%). Por nível, ficam abaixo de 75%: Mago no 4 e no 5, Feiticeiro e Ladino no 4, Clérigo e Druida no 8 e no 9. |
| 3 a 6 rodadas por luta | **Cumprida no limite.** Média geral de 3,4; cinco classes ficam abaixo de 3 (Bruxo 2,0; Bárbaro 2,4). As lutas estão curtas. |
| Diferença de 10 a 15 pontos entre os dois jogadores | **Passou do alvo.** De 5 (Paladino) a 39 (Feiticeiro) pontos. Conjurador que só ataca perde muito. |
| Morte na rodada 1 em até 2% | **Cumprida na média** (1,4% nos encontros comuns). O pior encontro isolado chega a 37%. |
| Chefe por volta de 60% | **Depende do nível**, ver abaixo. |

O nível 4 é um vale para quase todas as classes: é quando entra a banda do Troll e do
Espectro, e o herói ainda não tem o dado extra de dano do nível 5.

## Chefes

O chefe do capítulo é sorteado por degrau de nível, e a ficha de três deles foi ajustada.
Vitória do jogador tático, 120 duelos:

| Chefe | Nível | Guerreiro | Bárbaro | Patrulheiro | Clérigo | Ladino | Mago | Feiticeiro |
|---|---|---|---|---|---|---|---|---|
| Bugbear | 1 | 70% | 54% | 56% | 24% | 13% | 42% | 32% |
| Bugbear | 2 | 88% | 76% | 82% | 69% | 55% | 57% | 61% |
| Dragão Jovem | 5 | 68% | 84% | 91% | 56% | 42% | 17% | 14% |
| Dragão Jovem | 6 | 83% | 98% | 95% | 76% | 51% | 35% | 38% |
| Lich Menor | 8 | 93% | 93% | 98% | 62% | 55% | 21% | 33% |
| Lich Menor | 9 | 98% | 99% | 98% | 66% | 62% | 39% | 52% |
| Dragão Adulto Jovem | 8 | 52% | 67% | 77% | 23% | 13% | 17% | 18% |
| Dragão Adulto Jovem | 9 | 70% | 83% | 82% | 38% | 31% | 26% | 33% |
| Dragão Adulto Jovem | 10 | 85% | 98% | 97% | 78% | 59% | 44% | 52% |

Leitura: o chefe é difícil no primeiro nível do degrau e fica vencível um ou dois níveis
depois. Como o capítulo leva vários passos até o confronto, o herói costuma chegar acima
do nível em que o chefe foi sorteado, mas isso não foi medido.

**Os dragões são o ponto fraco de Mago e Feiticeiro.** O sopro pega de qualquer distância
e eles têm pouca vida; recuar, que é a defesa deles, não protege do sopro. O Ladino sofre
contra todo chefe porque chefe não fica "abalado" tão fácil, e o ataque furtivo depende
disso.

## O que foi mudado para chegar aqui

**Regras:**

- Inimigo que atravessa a cena para atacar o faz com desvantagem naquela vez.
- O Foco não volta cheio a cada luta. Atacar não devolve Foco; defender devolve 1.
- A cura das técnicas soma o nível do herói.
- Efeito de controle de técnica (atordoar, enfraquecer, queimar, abrir a guarda) pede
  teste de resistência do alvo.

**Conjuradores** (eram os mais fracos, por pouca vida e pouca Defesa):

- 2 de Foco máximo a mais.
- Ataque básico mais forte: 1d10 para Mago, Feiticeiro e Bruxo; 1d8 para Clérigo, Druida e
  Bardo. Antes era 1d6 para todos.
- Defesa extra que cresce com o nível para Mago, Feiticeiro e Bruxo (+2 no nível 1, +5 no
  nível 9) e, menor, para Bardo e Druida.
- Mago e Feiticeiro recuam sem levar golpe de oportunidade.

**Chefes:**

| Chefe | Mudança |
|---|---|
| Bugbear | 27 → 24 de vida; sorteado do nível 1 ao 4 |
| Dragão Jovem | 78 → 60 de vida; ataque 2d10+4 → 2d8+3; sopro 4d6 → 3d6; sorteado do 5 ao 7 |
| Dragão Adulto Jovem | ataque 3d10+4 → 2d10+4; sopro 6d6 (CD 16) → 4d6 (CD 15); a partir do 8 |
| Lich Menor | sem mudança; a partir do 8 |

## Dois erros do jogador simulado, não do jogo

Durante a medição, duas quedas grandes eram do simulador:

- Ele usava a técnica de cura no começo da luta, com a vida cheia, e ficava sem Foco.
- Ele nunca usava magia de área contra um inimigo só, e as técnicas mais fortes de Mago e
  Feiticeiro são de área.

Corrigidos os dois, Mago e Feiticeiro subiram cerca de 10 pontos sem mexer em regra
nenhuma. Vale lembrar ao ler qualquer número daqui: o simulador mede **um jeito de jogar**.

## Limites

- Só duelos de um contra um. Grupos de inimigos e lutas com aliado não foram medidos.
- O herói não tem talentos nem itens além do inicial, e chega descansado em toda luta. O
  efeito do Foco que acaba ao longo de várias lutas seguidas não foi medido.
- O improviso não é usado pelos jogadores simulados.
