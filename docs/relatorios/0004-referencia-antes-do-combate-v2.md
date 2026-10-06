# Relatório 0004 — Referência de balanceamento antes do Combate v2

**Data:** 06/10/2026 · Fase 1 do plano "Trilha do capítulo + Combate v2"

## Para que serve

O combate vai mudar bastante (iniciativa de verdade, distância, recursos que acabam).
Este relatório mede como ele está **hoje**, já com os consertos da Fase 0, para que cada
mudança futura possa ser comparada com um número e não com uma impressão.

## Método

`Backend/evals/simulador.py`: duelos sem IA e sem banco, pelo mesmo caminho que um clique
do jogador percorre (`ToolExecutor.executar`). 150 duelos por combinação de classe, nível
(1 a 10) e encontro. Encontros: cada monstro das bandas sugeridas ao nível, sozinho, mais
os chefes que um capítulo aberto naquele nível pode sortear.

Herói de referência: atributo principal da classe em 16, Constituição e Destreza 12, o
resto 10; equipamento inicial da classe vestido pela mesma função da criação de
personagem; duas Poções de Cura. Clérigo e Paladino recebem a Força que a armadura inicial
exige (13 e 15), como faria quem joga com eles.

Dois jogadores simulados:

- **básico:** só ataca e bebe poção abaixo de 35% de vida.
- **tático:** além disso, usa a técnica mais forte que o Foco paga, área só contra grupo,
  e o reforço próprio uma vez por luta.

Reproduzir:

```bash
uv run python -m evals.simulador --n 150 --classes todas --bot basico
uv run python -m evals.simulador --n 150 --classes todas --bot tatico
```

## Resultado por classe

"Comum" = monstros das bandas do nível. "Chefe" = chefes do capítulo e de elite, em todos
os níveis em que podem aparecer. "Pior encontro" = a menor taxa de vitória entre os comuns.

### Jogador básico

| Classe | Vitória (comum) | Pior encontro | PV restante | Turnos | Vitória (chefe) |
|---|---|---|---|---|---|
| Paladino | 86% | 33% | 71% | 5,7 | 35% |
| Guerreiro | 84% | 28% | 68% | 5,0 | 32% |
| Patrulheiro | 78% | 19% | 65% | 4,9 | 25% |
| Bárbaro | 73% | 12% | 59% | 4,4 | 21% |
| Clérigo | 65% | 4% | 63% | 5,0 | 17% |
| Ladino | 57% | 2% | 60% | 4,5 | 13% |
| Monge | 53% | 1% | 57% | 4,7 | 12% |
| Druida | 52% | 3% | 57% | 4,6 | 11% |
| Bruxo | 48% | 1% | 54% | 4,5 | 10% |
| Bardo | 47% | 0% | 53% | 4,5 | 10% |
| Feiticeiro | 33% | 0% | 53% | 3,8 | 6% |
| Mago | 32% | 0% | 54% | 3,8 | 6% |

### Jogador tático

| Classe | Vitória (comum) | Pior encontro | PV restante | Turnos | Foco gasto | Vitória (chefe) |
|---|---|---|---|---|---|---|
| Patrulheiro | 96% | 75% | 82% | 3,8 | 4,2 | 53% |
| Guerreiro | 95% | 68% | 78% | 3,8 | 4,3 | 54% |
| Paladino | 94% | 71% | 79% | 5,4 | 5,5 | 50% |
| Bárbaro | 88% | 38% | 64% | 3,5 | 4,0 | 32% |
| Monge | 88% | 47% | 74% | 4,0 | 4,3 | 35% |
| Bruxo | 79% | 24% | 68% | 3,6 | 3,9 | 23% |
| Clérigo | 77% | 29% | 68% | 5,2 | 4,3 | 26% |
| Druida | 76% | 12% | 61% | 5,2 | 4,2 | 21% |
| Ladino | 72% | 25% | 62% | 4,6 | 4,2 | 21% |
| Mago | 70% | 18% | 69% | 4,1 | 4,1 | 18% |
| Bardo | 62% | 5% | 54% | 5,3 | 4,2 | 17% |
| Feiticeiro | 53% | 1% | 61% | 3,2 | 3,5 | 14% |

## O que os números dizem

1. **As classes estão muito desiguais.** Com o jogador tático, a vitória em encontro comum
   vai de 53% (Feiticeiro) a 96% (Patrulheiro). A meta do plano é nenhuma classe fora de
   75–97%. Seis das doze estão abaixo ou no limite.
2. **A diferença é a armadura inicial, mais que as técnicas.** Guerreiro e Paladino
   começam com Defesa 18; Mago e Feiticeiro com 11 e 7 de vida. Como hoje não existe
   distância, o conjurador apanha em corpo a corpo desde o primeiro turno. A distância
   (perto/longe) da Fase 4 deve mudar isso; a Fase 8 confere.
3. **O relatório 0002 contava com o chefe se rendendo.** Ele registrava 53–57% de vitória
   contra o chefe de elite no nível 9. Aquela medição incluía o defeito consertado na
   Fase 0 (o chefe saía da luta com 30% de vida e contava como vencido). Sem a rendição, o
   Guerreiro básico vence o chefe de elite em 30–39% das vezes no nível 9, e o tático em
   65–75%. Conferido rodando o mesmo simulador com a rendição religada: volta a 52–62%.
4. **O Dragão Jovem é impossível para níveis baixos.** Um capítulo aberto até o nível 5
   sorteia o chefe entre Bugbear e Dragão Jovem. Contra o Dragão Jovem, o Guerreiro tático
   vence 1% das vezes no nível 1, 12% no 3 e 53% no 5. O Bugbear, na mesma faixa, vai de
   61% a 100%. A escolha do chefe precisa olhar o nível com mais cuidado (Fase 8).
5. **As lutas são curtas.** De 3 a 6 turnos em média, dentro da meta de 3 a 6 rodadas.

## Limites desta medição

- Só duelos de um contra um. Grupos de inimigos e aliados não foram medidos.
- O herói não tem talentos nem itens além do inicial.
- Os monstros "brutos" ainda atacam rodada sim, rodada não (defeito que sai na Fase 5).
  Quando sair, orc, ogro, gigante e dragões vão bater o dobro de vezes, e estes números
  vão cair. Por isso esta tabela é ponto de partida, não meta.
