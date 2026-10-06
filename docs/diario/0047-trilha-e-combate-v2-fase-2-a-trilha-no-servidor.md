# Trilha e Combate v2, Fase 2: a trilha do capítulo no servidor

**Período:** 06/10/2026 · continuação do diário 0046 · decisão no ADR-0039

## O problema

O jogo tinha um "objetivo" e um "capítulo", mas nada entre o começo e o fim de um capítulo.
O jogador não via o que fazer agora nem se tinha avançado. E quem decidia que algo estava
"cumprido" era a IA, quando lembrava.

## O que mudou

Cada capítulo agora tem uma **trilha**: uma sequência de passos, um de cada vez.

### Quem faz o quê

- **O servidor monta as opções.** Olhando o estado do jogo (quem está na cena, o que ainda
  não foi investigado, como anda o conflito), ele lista até 8 próximos passos possíveis.
  Cada um tem uma condição que ele sabe conferir.
- **A IA escolhe uma e escreve a frase.** Ela recebe a lista numerada e o que o jogador
  acabou de fazer, e devolve o número e um texto curto.
- **O servidor confere.** Depois de cada ação do jogador, ele olha se a condição do passo
  atual virou verdade. Se sim: marca como feito, anota a prova ("Você ouviu Íria."), dá
  50 XP e pede o próximo passo.

A IA não consegue marcar um passo como feito nem inventar uma condição. Se ela falhar
(sem cota, resposta torta, número fora da lista), o servidor usa a primeira opção com o
próprio texto. A trilha nunca fica parada esperando a IA.

### Os tipos de passo

Chegar a um lugar, falar com alguém, ganhar a cooperação de alguém, investigar um objeto,
recolher um objeto, intervir no conflito, enfrentar o chefe, descobrir um fato novo e, por
último, fechar o capítulo.

### Fechar o capítulo

Antes, o capítulo exigia 8 turnos de jogo. Isso media tempo, e até clicar em "equipar"
contava. Agora exige 3 passos cumpridos, além do que já exigia (2 fatos registrados e o
conflito resolvido ou o chefe vencido). Quando tudo vale, o passo atual vira "Feche este
capítulo quando estiver pronto".

### Outras mudanças

- O narrador passou a receber as ferramentas de abrir e fechar capítulo quando elas cabem,
  e não só quando o jogador escreve a palavra "arco" ou "missão".
- `concluir_objetivo` saiu da lista do narrador. O XP de progresso vem dos passos.
- O narrador recebe o passo atual no contexto, com a instrução de não dizer que foi
  cumprido e não obrigar o jogador a segui-lo.
- Partidas antigas: um capítulo já em andamento recebe passos "creditados" pelos turnos
  jogados, para ninguém voltar ao zero.

## Mudança em relação ao plano

O plano previa avisos espalhados pelo código ("o jogador conversou", "o jogador venceu").
Ficou mais simples conferir o estado direto: bastou um campo novo dizendo se a pessoa já
foi ouvida. Também ficaram de fora dois tipos de passo previstos ("vencer um combate" e
"conflito fechado"); o motivo está no ADR-0039.

## Como foi verificado

**Testes.** 26 em `Backend/tests/test_capitulo.py`, escritos antes do código. Cobrem cada
tipo de passo, a migração de partida antiga, as quatro formas de a IA responder errado e o
caminho inteiro pela API sem IA (carregar, clicar em conversar, ver o passo feito e o
próximo já na resposta, recarregar). Suíte toda: 783 testes passando.

**Ao vivo, com a IA real.** Três mundos gerados com sementes diferentes; em cada um, o
herói conversa com a pessoa do primeiro passo e a IA escolhe o seguinte.

| Mundo | A IA escolheu | Texto | Tempo |
|---|---|---|---|
| A disputa por sementes | falar com Tália | "Fale com Tália para buscar pistas sobre o paradeiro de sua irmã antes de decidir sobre o depósito." | 3,4 s |
| O destino da propriedade | falar com Dara | "Fale com Dara para descobrir se ela sabe algo sobre o paradeiro de sua irmã antes que Nilo venda a propriedade." | 2,1 s |
| A decisão de interditar | ganhar a cooperação de Ravi | "Conquiste a cooperação de Ravi para garantir que a interdição da câmara não bloqueie sua busca." | 1,0 s |

Três de três vieram com número válido e texto dentro do tamanho. A IA ligou o passo ao
objetivo do herói ("encontrar minha irmã") sem que isso fosse pedido passo a passo.

Na primeira rodada, um dos textos veio como "você decide procurar por Dara", decidindo
pelo jogador. O pedido passou a exigir o imperativo ("Fale", "Procure") e a proibir dizer
o que o jogador sente ou pensa; os textos da tabela são da segunda rodada.

**O que não foi verificado.** Uma partida inteira jogada no navegador, do começo ao fim de
um capítulo. A tela da trilha só existe na Fase 3; o teste no navegador fica para lá. Três
mundos é uma amostra pequena: mostra que o formato funciona, não mede quantas vezes a IA
erra em mil.
