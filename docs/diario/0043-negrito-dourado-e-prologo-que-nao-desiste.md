# O dourado que sumia e o prólogo que desistia fácil

**Período:** 05/10/2026 · continuação dos diários 0041 e 0042

## 1. O destaque dourado

### O que acontecia

O jogo tem um efeito de "repare nisto": quando o Mestre escreve um trecho entre dois
asteriscos (`**anel de sinete**`), a tela o desenha em dourado. Só que o destaque aparecia
enquanto o texto ia chegando e **sumia** quando o turno terminava. Ao recarregar a página,
também não voltava.

A causa era uma decisão antiga do próprio servidor: antes de gravar o turno, ele apagava todo
tipo de marcação, inclusive o negrito. O raciocínio da época era que marcação guardada no
histórico "ensina" a IA a marcar cada vez mais. Para piorar, as instruções da IA se
contradiziam: um trecho permitia negrito em descobertas, outro (a "bíblia" do Mestre)
proibia qualquer marcação.

### O que mudou

- O servidor **mantém o negrito** e continua apagando o resto (itálico, títulos, listas).
- Para não virar árvore de Natal, vale um teto: **no máximo 3 destaques por narração**. O
  quarto em diante vira texto comum. É a mesma ideia do resto do projeto: a IA propõe, o
  servidor decide.
- A bíblia agora diz a mesma coisa que o resto: negrito só em uma ou duas coisas que o herói
  acaba de descobrir, e explica o porquê (a tela mostra em dourado; usado em tudo, não
  destaca nada).
- O que **não** é tela do jogador fica sem asteriscos: a checagem de coerência, a memória de
  longo prazo, os botões de opção, o epitáfio, o fim de capítulo e a crônica.
- A tela do prólogo também passou a desenhar o dourado.

Uma correção ao que escrevi no diário anterior: lá eu disse que o negrito "aparece cru na
tela". Não aparecia. Vi os asteriscos numa saída de teste que não passa pelo servidor do
jogo e concluí errado.

## 2. O prólogo que desistia fácil

### Medindo antes

Gerei 10 prólogos seguidos no Flash Lite, com cinco fichas diferentes. Nove saíram bons e
amarrados à ficha. O que falhou tinha um defeito curioso, que apareceu 4 vezes nos 18 prólogos seguintes em que guardei a resposta crua:
uma resposta de 3.500 caracteres inteira certa, exceto por uma linha,

    name_missao: "O Rastro do Corvo",

onde deveria estar `"nome_missao"`. Uma chave sem aspas e com o nome trocado. O servidor
jogava a resposta toda fora e mostrava o texto de reserva.

Olhando o caminho inteiro, havia vários pontos assim, em que um deslize pequeno custava o
prólogo inteiro: um título faltando, uma descrição comprida demais, um campo vazio, a cena
registrada com um nome ligeiramente diferente do lugar.

### O que mudou

- **Ler com tolerância.** Chave sem aspas, vírgula sobrando, resposta embrulhada em bloco de
  código: o servidor conserta e lê. O `name_missao` é aproveitado como o título que era.
- **Consertar em vez de descartar.** Só duas coisas são indispensáveis: o lugar e o texto. O
  resto tem padrão. Texto longo demais é cortado no limite; campo vazio é ignorado; cena com
  outro nome assume o nome do lugar; gente ou conflito a mais é cortado, ficando primeiro
  quem está na cena inicial.
- **Tentar de novo dizendo o que estava errado.** Se mesmo assim a resposta não serve, o
  pedido é refeito com o motivo ("o campo tal veio vazio"). Até 3 tentativas.
- **Com relógio.** As tentativas dividem um prazo só, de 80 segundos. Passou disso, texto de
  reserva. O número fica abaixo de 100 de propósito: é por volta daí que serviços de
  hospedagem costumam cortar uma requisição, e isso vira erro na tela.
- **Botões que combinam com a cena.** Quando as três opções vinham inválidas, o servidor
  usava as do texto de reserva: "Examinar Registro de entregas" numa cena sem registro
  nenhum. Agora monta as opções a partir da cena que a própria IA criou.
- **Menos porto e chuva.** Dos 10 primeiros prólogos, 7 se passavam em porto ou estalagem,
  quase todos com chuva. O pedido agora chama isso de lugar-comum e sorteia três pontos de
  partida diferentes por campanha (mina, moinho, posto de fronteira, feira de estrada…).

### A ordem dos modelos mudou de novo

No diário 0042 o prólogo abria pelos modelos maiores (Flash) e o Flash Lite ficava de
reserva. As medições de hoje não sustentam isso:

- Flash Lite: 13 de 13 prólogos aproveitados depois das mudanças (9 de 10 antes), em 4 a 21 segundos.
- Flash, quando respondeu: 28 a 47 segundos. E em duas baterias seguidas (2.5 e 3.6), nenhum
  de 7: só sobrecarga, estouro de tempo e cota.

Com 80 segundos de prazo, dois Flash pendurados gastavam tudo antes de o Lite ser tentado.
Então os dois Lite passaram para a frente e os Flash ficam com o tempo que sobrar. Os Lite
também ganharam um tempo limite próprio, de 22 segundos: um modelo que normalmente responde
em 6 não merece 50 de espera.

Isso tem um custo: o prólogo deixa de ir primeiro para o modelo teoricamente melhor. Lendo
os textos lado a lado não vi diferença que justifique 30 segundos a mais e o risco de não
vir nada. Se o Google estabilizar os Flash, é uma linha de configuração para inverter.

## Depois

Dez prólogos no Flash Lite com o código novo: 10 de 10, média de 6 segundos (dois deles
salvos pela segunda tentativa). Três com a fila completa e sementes sorteadas: 6, 4 e 6
segundos, em uma oficina de carroças, uma mina de sal e outra mina de sal.

Entre uma medição e outra houve cerca de dez minutos em que o Google não respondeu em modelo
nenhum, nem no Lite. Nesse intervalo o prólogo levou os 80 segundos e caiu no texto de
reserva, que é o comportamento esperado: nenhuma mudança aqui faz a IA responder quando o
provedor está fora.

## O que ficou de fora

- **O conserto da "cena com outro nome" não foi visto ao vivo.** Era o defeito do 2.5 Flash;
  quando fui conferir, ele não respondeu nenhuma vez. Está coberto por teste automático.
- **Variedade com amostra pequena.** Duas minas de sal em três prólogos sugere que o sorteio
  de lugares ajuda mas não resolve sozinho.
- **Quando cai no texto de reserva, o jogador não tem como pedir outro prólogo.** Um botão
  "tentar de novo" na tela de abertura resolveria os dias ruins do provedor.

## Como testar

`pytest` no backend: 710 testes. Os novos cobrem: negrito sobrevive, o teto de 3, itálico
some sem tocar o negrito, opções e guardrail sem asteriscos; e, no prólogo, JSON com chave
sem aspas, campo nulo e texto longo, mundo acima do teto, cena com outro nome, opções
montadas da cena, nova tentativa com o motivo e parada pelo prazo. No front, `vitest` (80
testes) e `tsc` passam.
