# Trilha e Combate v2, Fase 4: o motor de turnos novo, ainda ao lado do antigo

**Período:** 06/10/2026 · continuação do diário 0048

## O que esta fase é (e o que não é)

O combate que o jogador joga hoje **não mudou**. Esta fase construiu o motor novo num
arquivo separado (`Backend/app/services/turnos.py`) e o testou sozinho. Ligá-lo aos botões
é a Fase 5. Fazer em dois passos deixa a suíte antiga inteira passando enquanto o novo
nasce, e a troca vira um passo só, fácil de conferir.

## O problema do motor antigo

- Um clique resolvia a ação do herói e, em seguida, **todos** os inimigos. O herói sempre
  agia primeiro; a iniciativa era rolada e ignorada.
- Não havia distância: um mago apanhava em corpo a corpo desde o primeiro turno.
- O jeito de cada monstro lutar era adivinhado por palavras num texto livre da ficha
  ("recua", "brutal", "sozinho"). Daí vinham três defeitos: brutos atacando rodada sim,
  rodada não; kobold fugindo na primeira rodada; chefe se rendendo.
- Nenhum inimigo fazia nada além de bater. O herói nunca ficava envenenado nem caído.

## O que o motor novo faz

**Fila de turnos.** Herói, cada inimigo e cada aliado rolam iniciativa (um d20 mais
Destreza) e agem nessa ordem. Quem é mais rápido que o herói age antes dele.

**Distância.** Cada inimigo está "perto" ou "longe" do herói. Todos começam longe, menos
em emboscada.

- Inimigo de corpo a corpo avança e ataca na mesma vez.
- Atirador fica longe. Se o herói cola nele, atira com desvantagem (rola dois dados e fica
  com o pior).
- Recuar tira o herói do corpo a corpo, mas cada inimigo perto ganha um ataque de graça,
  uma vez por rodada. É o "ataque de oportunidade".

**Tática na ficha.** Cada monstro tem agora, em `data/monsters.json`, campos próprios:

| Campo | O que diz |
|---|---|
| `tatica` | agressivo, covarde, matilha, atirador, bruto, regenera ou implacável |
| `alcance` | corpo, distância ou ambos |
| `foge_abaixo` | a fração de vida abaixo da qual foge (0 = nunca) |
| `fortes` | em quais resistências ele é bom |
| `habilidade` | um efeito especial, quando tem |

O texto livre continua na ficha só como descrição. Os três defeitos saem pela raiz: o
bruto ataca toda vez e alterna um golpe pesado (+3 de dano) **avisado na vez anterior**; o
kobold só foge ferido; chefe nunca foge.

**Resistência e condições.** Onze monstros ganharam habilidade. Quando ela pega, o herói
rola um teste de resistência (d20 mais o atributo) contra uma dificuldade. Se falha:

| Monstro | Efeito |
|---|---|
| Aranha Gigante | envenenado: 2 de dano por turno |
| Lobo | caído: inimigos perto atacam com vantagem |
| Múmia, Vampiro | amedrontado |
| Carniçal | contido |
| Espectro | enfraquecido |
| Elemental de Fogo | em chamas: 2 de dano por turno |
| Dragões | sopro: 4d6 ou 6d6, metade se resistir |
| Lich | raio necrótico: 4d6, metade se resistir |

Sopro e raio têm recarga de 3 vezes e **uma vez de aviso** antes do primeiro uso: a
intenção do dragão aparece como "sopro" e o jogador pode se preparar.

**Aliados.** Agem sozinhos na própria vez, no inimigo mais ferido. Se o herói marcou um
alvo, batem nele, com vantagem no primeiro golpe.

**Partidas antigas.** Uma luta em andamento salva no formato antigo é convertida ao
carregar: todos ficam "perto" (a luta já estava engajada) e a vez é do herói.

## Decisões que simplificam

- **Atirador não foge do corpo a corpo.** O plano dizia "atira com desvantagem ou recua".
  Ficou só a desvantagem: é previsível e já recompensa o jogador que fecha a distância.
- **Aliado não tem distância.** Só o herói e os inimigos têm.
- **Resistência de monstro sem ficha de atributos.** Ela acompanha o bônus de ataque dele,
  com +3 no que a ficha diz ser o forte.
- **A resistência do herói é só o atributo**, sem bônus de classe. Isso entra com a
  identidade das classes, na Fase 8.

Os números (3 de regeneração, +3 no golpe pesado, as dificuldades de 11 a 16) são um
primeiro chute. Quem acerta é o simulador, na Fase 8.

## O que falta para o jogador sentir isso

Nada disto chega à tela ainda. Faltam: ligar aos botões e ao servidor (Fase 5), a narração
por rodada e o Improvisar (Fase 6), a fila e as etiquetas na tela (Fase 7) e as classes e o
balanceamento (Fase 8).

O efeito de cada condição **sobre as ações do herói** (envenenado ataca com desvantagem,
amedrontado não avança, contido não se move) também é da Fase 5, que é onde as ações do
herói passam para o motor novo. Nesta fase as condições já entram, duram e cobram dano.

## Como foi verificado

65 testes em `Backend/tests/test_combate_v2.py`, com dados fixos para cada resultado ser
exato: ordem da fila, empate, inimigo rápido agindo antes, distância e desvantagem, ataque
de oportunidade uma vez por rodada, bruto avisando o golpe pesado, fuga, matilha,
regeneração, atordoamento custando exatamente uma vez, veneno, sopro com aviso e recarga,
aliados e comando, conversão de luta antiga. Um teste percorre os 28 monstros conferindo a
ficha tática.

Suíte inteira do backend: 848 testes passando, com o motor antigo intacto.

Não foi jogado, porque ainda não está ligado ao jogo.
