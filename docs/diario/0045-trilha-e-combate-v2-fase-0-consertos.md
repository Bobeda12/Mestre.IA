# Trilha e Combate v2, Fase 0: consertos antes do redesenho

**Período:** 06/10/2026 · primeira fase do plano "Trilha do capítulo + Combate v2"

## De onde isto vem

A parte de objetivo e a de combate não estavam prontas para lançar. Antes de mexer em
código, o plano foi fechado em conversa. As decisões:

- **Jornada:** a aba vira uma "trilha do capítulo": o objetivo de agora, o capítulo com
  passos em sequência e, embaixo, o que ficou para trás. Quem marca um passo como cumprido
  é o servidor; a IA só escreve o texto. Os outros painéis (projetos, lugares,
  organizações) saem da tela e continuam funcionando por trás.
- **Combate:** sem mapa, mas com distância (cada inimigo está "perto" ou "longe"),
  iniciativa de verdade com a fila na tela, ação + ação bônus + movimento, testes de
  resistência, condições no herói e recursos que acabam. Os botões resolvem a jogada sem
  IA; uma chamada curta de IA narra cada rodada. O texto livre em combate vira o botão
  "Improvisar".
- **Entrega:** tudo junto no fim, na branch `feat/trilha-e-combate-v2`, em dez fases.

Esta é a Fase 0: consertar o que estava errado sem redesenhar nada. Serve de chão firme
para as próximas, que vão trocar o motor.

## O que estava errado e o que mudou

### 1. Matar o chefe com um ataque comum não fechava o capítulo

Cada capítulo reserva um chefe. Vencê-lo é uma das formas de encerrar o capítulo. Mas o
aviso "o chefe foi enfrentado" só era dado num dos cinco caminhos de vitória (o das
técnicas). Derrubar o chefe com Atacar, Investir, com o golpe de um aliado ou com o
terreno encerrava a luta e o capítulo continuava aberto, esperando um chefe que já tinha
caído.

Agora existe um único ponto de vitória, `_fechar_vitoria` (em `services/tools.py`), e os
cinco caminhos passam por ele.

O teste antigo não pegava o defeito porque chamava direto a função que funcionava. O novo
derruba o chefe pelos quatro caminhos que falhavam.

### 2. Chefe se rendia com 30% de vida

O comportamento dos monstros é lido de um texto livre na ficha. Os dois dragões e o Lich
têm "recua quando abaixo de 30% de HP" nesse texto, e "recuar" tira o inimigo da luta. O
chefe do capítulo saía de cena com um terço da vida e a luta contava como vencida.

Chefe agora não recua. Monstro comum continua recuando.

### 3. Inimigo que fugia rendia XP inteiro

A soma de XP contava todos os inimigos da luta, inclusive os que tinham recuado. Agora só
conta quem caiu, o mesmo critério que o bestiário já usava para contar abates.

### 4. O contador de fatos do capítulo podia travar

Para encerrar, o capítulo exige dois fatos registrados desde que abriu. A conta era
"tamanho da lista de marcos agora, menos o tamanho quando o capítulo abriu". Só que essa
lista guarda apenas os últimos 60 itens (e um trecho do código cortava em 40). Numa
campanha longa, a lista para de crescer, a conta dá zero ou negativo, e o capítulo nunca
mais fecha.

Cada capítulo agora tem o próprio contador (`fatos_registrados`), que sobe a cada fato e
não depende do tamanho da lista. Capítulos de partidas antigas, que não têm o contador,
seguem pela conta antiga até o primeiro fato novo. O corte em 40 virou 60, igual ao resto.

### 5. O nome do chefe ia para o navegador

O servidor mandava, junto com o estado do capítulo, o nome do chefe reservado. A tela não
mostrava, mas estava lá para quem abrisse as ferramentas do navegador. O campo saiu do que
vai para o cliente; o narrador continua recebendo.

### 6. Três acertos menores

- **Alvo que já recuou:** o clique em "Atacar" aceitava um inimigo que tinha saído da
  luta e trocava de alvo em silêncio. Agora recusa.
- **Aviso de chefe para o narrador:** comparava o nome inventado pela IA ("Vharn, o
  Devorador") com a lista de chefes, e nunca batia. Passou a comparar a ficha por trás do
  nome.
- **Painel de regras:** descrevia Esquivar como "remove a vantagem do inimigo". O motor
  faz outra coisa: os inimigos atacam com desvantagem. O texto foi corrigido.

## O que ficou para as próximas fases

Três defeitos dependem do motor novo e não foram tocados: monstros "brutos" (orc, ogro,
dragões) atacam rodada sim, rodada não; o kobold sozinho foge na primeira rodada; e mandar
só o aliado atacar não provoca reação dos inimigos. Os três somem quando a tática do
monstro deixar de ser lida do texto livre e a iniciativa passar a valer (Fases 4 e 5).

## Como foi verificado

- 11 testes novos em `Backend/tests/test_conserto_combate.py`, escritos antes dos
  consertos e vistos falhar.
- Suíte inteira do backend: 728 testes passando. `mypy` sem erros.
- `ruff` acusava 4 linhas longas em `tests/test_game_actions.py`, que já estavam na
  `main` e derrubariam o lint do CI. Foram quebradas.

Nada disto foi jogado ao vivo ainda; são regras do servidor, cobertas por teste. O teste
ao vivo entra na Fase 2, quando a trilha do capítulo existir.
