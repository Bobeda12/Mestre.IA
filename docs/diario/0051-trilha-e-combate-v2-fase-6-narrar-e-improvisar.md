# Trilha e Combate v2, Fase 6: a IA volta ao combate, em dois papéis pequenos

**Período:** 06/10/2026 · continuação do diário 0050 · decisão no ADR-0041

## O problema

Depois da Fase 5, o combate ficou todo no servidor: rápido e correto, mas mudo. O clique
devolvia linhas de contabilidade ("d20(15)+5=20 vs CA 13"). E a ação criativa, o que
diferencia um RPG com mestre de um jogo de menu, só existia pelo chat, que em combate era
caro: o pedido à IA passava de 7 mil tokens (um "token" é mais ou menos um pedaço de
palavra; o provedor gratuito aceita 8 mil por minuto).

## O que foi feito

### 1. A IA narra a rodada

Quando o turno do herói fecha, a tela pede a prosa daquela rodada.

- **O que a IA recebe:** uma lista curta de fatos, sem nenhum número. Por exemplo:
  "O jogador escolheu: atacar. Você ataca Orc com Espada Longa e acerta. Orc ataca você e
  erra." Quem monta a lista é o servidor, a partir do que o juiz resolveu.
- **O que ela devolve:** duas ou três frases.
- **A conferência:** o servidor recusa a prosa se ela tiver qualquer dígito, ou se for
  curta ou longa demais. Só o juiz dá números.
- **Se falhar:** a tela recebe um aviso ("O mestre ficou sem voz nesta rodada") e a luta
  segue com o texto do servidor. Nada trava.

A prosa fica gravada junto com a rodada, então recarregar a página não gasta outra
chamada.

### 2. Improvisar

Em combate, o jogador pode escrever uma ideia ("jogo areia nos olhos do orc").

- **A IA escolhe três coisas, cada uma de uma lista fechada:** qual atributo a ação exige,
  se é fácil, média ou difícil, e qual de dez efeitos ela produz se der certo (ferir de
  leve, ferir todos, derrubar, abrir a guarda, distrair, empurrar, dar cobertura, preparar
  o próximo ataque, intimidar, ou nada).
- **O servidor rola o dado e aplica o efeito**, com os números dele. Custa a ação do turno.
- **Travas que a IA não contorna:** chefe não é derrubado nem intimidado; derrubar e ferir
  todos nunca saem como "fácil"; ferir todos vale uma vez por luta; repetir o mesmo truque
  em seguida fica mais difícil.
- **Se a IA falhar:** o servidor julga sozinho, olhando palavras do texto.

### 3. Cota separada

As duas chamadas são contadas à parte dos turnos do dia: 60 por conta. Uma luta não gasta
os turnos de exploração.

## Teste ao vivo, com a IA real

Três rodadas narradas e quatro improvisos, repetidos em três execuções.

**Tamanho e tempo.** Narração: cerca de 200 a 220 tokens de entrada e 55 a 85 de saída.
Improviso: cerca de 480 de entrada e 30 a 45 de saída. Em geral 1 segundo por chamada;
numa execução, de 4 a 7 segundos.

**Julgamentos da IA:**

| O jogador escreveu | Atributo | Dificuldade | Efeito |
|---|---|---|---|
| Derrubo o lustre de ferro em cima dos dois | Força | difícil | ferir todos |
| Jogo areia nos olhos do orc | Destreza | fácil | distrair |
| Grito que os reforços estão chegando para assustar o lobo | Carisma | média | intimidar |
| Mato todos com um olhar e ganho 1000 de ouro | Carisma | difícil | nada |

O último é o caso que importa: pedido absurdo, e a IA escolheu "nada". Mesmo que tivesse
escolhido outra coisa, o pior efeito possível é o mais forte da lista, com dado rolado.

**O que apareceu de errado nas narrações, e o que fiz:**

- Uma veio em "tu" e tratou o herói no feminino ("antes que possas respirar aliviada"). O
  pedido passou a exigir "você" e nenhum adjetivo com gênero. Não voltou a acontecer nas
  duas execuções seguintes.
- Uma deu ao herói um escudo que ele não tinha e chamou o veneno de "paralisante". O
  pedido passou a proibir equipamento e efeito fora da lista. Na execução seguinte, o
  escudo sumiu; o veneno ainda foi enfeitado ("paralisa seus sentidos").
- O fato "Você sofre dano." (o veneno cobrando no começo do turno) virava uma frase torta.
  Trocado por "O mal que aflige você cobra o seu preço."

Ou seja: a prosa **não muda números**, isso é garantido. **Enfeitar** além dos fatos ainda
acontece e só é contido pelo texto do pedido.

**Uma variação que mudou uma regra.** Numa execução, "areia nos olhos" saiu como
"derrubar" com dificuldade "fácil": o orc perderia a vez com um teste de 10. Por isso
entrou a trava de que derrubar e ferir todos nunca são "fácil".

**Falhas reais.** Na segunda execução, feita logo depois da primeira, uma narração e dois
improvisos voltaram vazios e o servidor assumiu, como projetado. Não capturei a causa; a
suspeita é o limite de chamadas por minuto, porque depois de 50 segundos de pausa as sete
voltaram a funcionar. É uma amostra do que acontece quando vários jogadores lutam ao
mesmo tempo com a chave do servidor.

## Como foi verificado

- 31 testes em `Backend/tests/test_combate_ia.py`: os fatos sem número; prosa com número,
  curta ou longa demais é descartada; cinco formas de a IA julgar errado; cada efeito do
  improviso com dado fixo; as travas; o tamanho dos pedidos no pior caso; e seis testes
  pela API (narra com os fatos do servidor e grava, repete sem chamar a IA, sem IA devolve
  aviso, acima do teto não chama a IA, improviso com IA e sem).
- Suíte toda: 901 passando. `ruff` e `mypy` limpos.

## O que falta

- **A tela.** Nada disto aparece para o jogador ainda: o botão Improvisar e a prosa da
  rodada são da Fase 7.
- **Fechar o chat em combate.** Continua aberto até o botão existir.
- **Medir o custo de uma luta inteira no navegador**, com várias rodadas seguidas, para
  ver quantas narrações caem no aviso.
