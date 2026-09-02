# Onze ajustes de "juice" pós-remaster

**Período:** 02/09/2026 · uma sessão com o Claude Code

## O que aconteceu

Depois do remaster e das duas rodadas de conserto anteriores, veio um lote de 11 pedidos de
polish visual e de usabilidade — nada de etapa nova, então este diário fica no tom simples,
sem ADR técnico (a única decisão que chegou perto de "arquitetural" foi extrair dois pedaços
novos de tela a partir do arquivo gigante que já existia, e isso já seguia o padrão das fases
anteriores).

"Juice", pra quem não é da área de jogos: é o nome informal pro conjunto de reações
pequenas — animação, som, brilho, tremor — que fazem uma ação simples (clicar, tomar dano,
rolar um dado) *parecer* satisfatória, mesmo sem mudar a mecânica por baixo.

## Os onze ajustes

- **Vida/Experiência/Ouro do herói foram morar na ficha lateral, com um resumo fixo por
  cima.** Antes, vida/nível/defesa ficavam soltos no topo da tela central, junto com o
  chat — e o Ouro nem aparecia ali. Agora os três moram juntos na ficha, com barras, do
  lado do retrato. Achei um comentário no código explicando por que a vida tinha sido
  posta ali no topo antes: no celular, a ficha cobre a tela inteira quando aberta, então
  se a vida só existisse lá dentro, fechar a ficha pra ver o chat durante uma luta deixaria
  o jogador sem saber quanto de vida tem. Resolvido com um meio-termo: uma pilulazinha só
  de vida (coração + número) continua visível no topo, mesmo com a ficha fechada.

- **Local e clima viraram um "cabeçalho de região"** no topo da tela central — no lugar
  que a faixa de vida ocupava antes.

- **O dado agora "rola" por mais tempo (cerca de 1 segundo) e mostra números trocando
  rápido enquanto gira**, tipo caça-níquel, antes de revelar o resultado final. Antes só
  o ícone girava, sem número nenhum aparecendo.

- **O motivo de um teste (ex: "Teste de Sabedoria para perceber a emboscada") não corta
  mais em "..."** — o texto quebra linha se precisar, mas aparece inteiro.

- **Os botões de 👍/👎 embaixo de cada fala do Mestre ficaram mais fáceis de acertar com o
  dedo** (área de clique quase o dobro do tamanho) **e dão um feedback visual bem mais
  claro** — o botão ganha uma cor viva (verde ou vermelho) e um brilho que fica, em vez de
  só mudar de cor discretamente.

- **A ficha lateral ganhou mais respiro** — os botões de aba (Status, Itens, Missão...)
  estavam quase colados nos atributos logo abaixo; agora tem espaço de sobra.

- **Os botões de "ação sugerida"** (que aparecem depois de uma resposta do narrador, tipo
  atalhos pra não precisar digitar) **ganharam um "cursor" de menu clássico de RPG**: uma
  setinha que só aparece quando o mouse passa por cima, e o texto muda de cor junto.

- **A caixa de texto do Mestre ficou mais fácil de ler** — as linhas têm mais espaço entre
  si, e o fundo por dentro da moldura dourada ficou um marrom/cinza bem escuro, separado
  do resto do fundo da página (antes era quase a mesma cor).

- **O retrato do herói agora mostra marcas de ferimento conforme a vida cai** — leves com
  menos da metade da vida, mais fortes e piscando com um quarto da vida, e no último
  décimo a tela inteira também começa a piscar vermelho sem parar (só volta ao normal
  quando a vida sobe ou o jogo acaba). As marcas são um "carimbo" de mancha de sangue
  (pacote gratuito Kenney, o mesmo já usado em outras partes do jogo) pintado de vermelho
  por cima do retrato — não é uma imagem nova gerada pra cada ferimento. Também: palavras
  em **negrito** que o narrador escreve agora aparecem em dourado brilhante (tipo "loot" ou
  lugar importante), em vez de simplesmente sumirem — antes o negrito era só apagado do
  texto, nunca virava destaque nenhum.

- **O Bestiário ganhou tooltips de verdade.** Passar o mouse num monstro (na aba
  Bestiário ou num card de inimigo em combate) mostrava, antes, a caixinha branca padrão
  do navegador — agora é uma caixinha no mesmo estilo do resto do jogo. Além disso, clicar
  num monstro do Bestiário abre uma "página de livro mágico" com o nome, se já foi
  derrotado, e uma descrição — como o jogo ainda não tem uma descrição de verdade pra cada
  monstro (isso exigiria mudar o servidor, fora do escopo desta rodada), aparece um texto
  de espera ("as lendas sobre esta criatura ainda estão sendo escritas...") só até esse
  dado existir de verdade.

- **Um "Guia do Aventureiro" novo**, pra quem nunca jogou RPG de mesa — um botão "?" do
  lado do botão de Configurações abre um resumo curto de "o que é isso", "como jogar" e
  "por que jogar". É diferente do "Manual do Jogo" que já existia: aquele é uma referência
  de números (nível, dificuldade, ações de combate); este é a explicação do conceito, pra
  quem está perdido antes mesmo de entender as regras.

## Como testei

Continuei uma sessão de jogo de verdade (personagem "TesteUX") no navegador, com o
frontend e o backend rodando local: vi a ficha nova com HP/XP/Ouro juntos, testei a
pilulazinha de HP no celular (viewport mobile) com a ficha fechada durante um combate,
mandei uma ação de ataque de verdade e vi o card de rolagem, testei os botões de 👍
(virou verde com brilho, confirmado também lendo a classe CSS aplicada), abri o Bestiário
e cliquei num monstro (o card de "livro mágico" abriu com o texto de espera), e abri o
Guia do Aventureiro (as três seções apareceram certinho, com visual de pergaminho
diferente do Manual do Jogo). O sistema de IA do servidor local ficou instável durante o
teste (fila de modelos configurados falhando), então não consegui ver a narração completa
de um turno em texto — mas os cards de rolagem, o HUD e os modais, que não dependem da IA
terminar de responder, foram todos confirmados ao vivo. A técnica de tingir a marca de
ferimento de vermelho foi confirmada à parte, numa página de teste isolada. Rodei também o
typecheck (`tsc --noEmit`) e o lint (`eslint`) do frontend nos arquivos tocados — os dois
limpos (só restaram dois avisos de `any` e um de dependência de `useEffect` que já
existiam antes desta rodada, sem relação com o trabalho feito aqui).

## Próximo passo

Nenhum pendente desta rodada específica. Fora do escopo dela, ficou registrado que o
Bestiário só mostra descrição de verdade quando o servidor passar a expor um campo de
lore/descrição por monstro — hoje ele só sabe nome, ataque e "comportamento" tático, e só
durante o combate. As pendências gerais do projeto continuam as mesmas de antes (Google
OAuth em produção, gaveta mobile da Etapa 7, calibração do juiz da Etapa 6).
