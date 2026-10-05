# Asteriscos na abertura e as opções que não chegavam

**Período:** 05/10/2026 · continuação do diário 0043

Dois defeitos achados jogando, os dois na primeira tela do jogo.

## 1. As opções do prólogo nunca apareciam

### O que acontecia

Junto com o texto de abertura, a IA escreve três sugestões de ação ligadas à cena
("Aproximar-se do ferreiro idoso para examinar o martelo"). O servidor as guardava no
histórico do herói. Mas os botões que apareciam ao começar a jogar eram sempre os mesmos
três, genéricos: "Observar os arredores", "Seguir em frente", "Verificar o inventário".

A causa: quem abre o jogo é uma rota chamada `/load_game` (ela carrega o herói do banco e
manda tudo para a tela). Essa rota não lia as sugestões guardadas; devolvia sempre as
genéricas. As sugestões do prólogo existiam no banco e não eram usadas por ninguém.

O mesmo acontecia no meio da partida: recarregar a página trocava as sugestões do último
turno pelas genéricas, porque os turnos nem guardavam as suas.

### O que mudou

- `/load_game` devolve as sugestões gravadas com a última narração. As genéricas ficam só
  para quando não há nenhuma gravada (partidas antigas, ação por clique em combate).
- Cada turno narrado agora grava as próprias sugestões no histórico, como o prólogo já fazia.

O que vai para a IA continua igual: `contexto_recente` (em `services/memory.py`) já mandava
só o papel e o texto de cada mensagem, sem as sugestões.

## 2. `**` aparecendo cru na abertura

### O que acontecia

O destaque dourado depende de um par bem formado: `**cofre de ferro**`, na mesma linha, sem
espaço colado nos asteriscos. Quando a IA escrevia qualquer coisa diferente disso, os
asteriscos ficavam na tela como vieram. Três formas de errar:

- espaço por dentro: `** cofre de ferro **`;
- um `**` que abre e nunca fecha;
- um par que atravessa a quebra de parágrafo.

Havia ainda um efeito pior no segundo caso. Para não piscar asteriscos enquanto o texto é
digitado, a tela esconde tudo depois de um `**` ainda sem par. Com um `**` que nunca fecha,
ela escondia o resto do texto para sempre.

### O que mudou

- **No servidor** (`limpar_formatacao`): o par com espaço é consertado e vira destaque; todo
  `**` que sobra sem par é apagado antes de gravar. O texto fica, os asteriscos saem.
- **Na tela** (`renderizarNarrativa`): mesmo que chegue um `**` sem par, ele não é desenhado.
  E a regra de esconder passou a valer só para a última linha, que é onde o texto ainda está
  chegando; uma sobra numa linha já encerrada não esconde mais nada.
- Durante a digitação do prólogo, que avança de dois em dois caracteres, metade de um `**`
  podia aparecer por um instante como `*`. Um asterisco sozinho no fim também fica escondido.

Não consegui reproduzir o texto exato que apareceu no jogo: o banco local não tem esse herói
e os prólogos guardados das medições tinham todos pares corretos. A correção cobre as
formas de erro possíveis em vez de um caso observado.

## Como testar

`pytest` no backend: 714 testes. Os novos: par com espaço consertado, asteriscos sem par
apagados, e `/load_game` devolvendo as sugestões do prólogo, as do último turno e as
genéricas quando não há nenhuma. No front, `vitest`: 83 testes, com os casos de
`renderizarNarrativa` (par vira destaque, abertura pendente escondida, sobra nunca aparece
nem esconde texto).

No navegador, com o jogo local: um herói criado pela IA, abertura observada durante os oito
segundos de digitação (nenhum asterisco em 210 amostras), depois com marcação quebrada
posta à mão no banco (nenhum asterisco, texto inteiro). Ao clicar em COMEÇAR, os três
botões eram as sugestões do prólogo.
