# Uma abertura feita para o seu personagem

**Período:** 05/10/2026 · achado de uso

## O que aconteceu

O prólogo é o primeiro texto que o jogador lê: aquele que deveria usar o passado e o
objetivo que ele acabou de escrever. Jogando, ele era a parte mais esquisita do jogo. Não
dava para entender direito quem estava onde, apareciam pessoas chamadas pelo nome como se o
herói já as conhecesse, e a cena servia para qualquer personagem.

Para medir em vez de achar, gerei o prólogo ao vivo para uma mesma personagem de teste
(Kaela, que procura o irmão levado por homens com um brasão de corvo, e guarda um botão
arrancado do casaco de um deles). Antes da mudança saiu isto, num parágrafo só:

> Um barulho inesperado corta o murmúrio: o velho faroleiro exibe um mapa rasgado […] A voz
> de Mira se eleva, pedindo silêncio, enquanto o estranho de capa negra observa a cena…

Quem é Mira? Onde estamos? Por que eu estou aqui? O texto não diz.

## As três causas

Todas estavam no prompt (a instrução que o servidor manda para a IA), em
`Backend/app/services/narrator.py`:

1. **O "exemplo de formato" era uma cena pronta.** Para mostrar à IA como montar a resposta,
   o prompt mandava a abertura de reserva inteira: um mercado, duas pessoas com nome, uma
   disputa por suprimentos. Modelos de linguagem tendem a imitar o exemplo que recebem (isso
   se chama ancoragem), então a cena nascia parecida com o exemplo, não com a ficha.
2. **O prompt mandava esconder a ficha.** Havia uma frase pedindo para não citar o objetivo
   nem a história, só "absorver como pano de fundo". A intenção era evitar um texto que
   repetisse a ficha feito papagaio; o efeito foi a IA quase não usar a ficha.
3. **A ordem começava pelo meio.** O texto era pedido como "acontecimento, tensão,
   oportunidades": já abria numa cena em andamento, sem apresentar o herói nem o lugar.

## O que mudou

- O exemplo virou um **esqueleto vazio**: só os nomes dos campos e, entre `< >`, o que vai
  em cada um. Não há mais cena para copiar.
- A ficha do jogador é declarada como **matéria-prima**: o lugar tem de ser onde alguém com
  aquele objetivo estaria, e uma pessoa e um objeto da cena precisam se ligar a um detalhe
  que o jogador escreveu. O teste que o prompt dá à IA: se a abertura servir para outro
  personagem trocando só o nome, está errada.
- O texto tem **ordem fixa em três parágrafos curtos**: quem você é e por que está na
  estrada; a chegada a um lugar onde você nunca esteve; o que acontece na sua frente agora.
- **Clareza**: ninguém aparece pelo nome sem apresentação (primeiro "uma mulher de avental",
  o nome só se alguém disser em voz alta), frases curtas, no máximo duas pessoas em destaque.
- O **texto de reserva** (o que aparece quando a IA falha) seguia um molde que quebrava a
  gramática: "sua busca por Encontrar meu irmão Teo trouxe você até este lugar". Agora segue
  a mesma ordem, cita o objetivo entre aspas e apresenta as duas pessoas antes de elas falarem.
- Duas coisas que a IA copiava do exemplo antigo passaram a ser preenchidas pelo servidor: o
  chefe do capítulo (tem de ser um do catálogo) e o objetivo registrado no mundo.
- Quando a resposta da IA é descartada por estar malformada, o motivo agora aparece no log.
  Antes o descarte era mudo.

## Depois

A mesma Kaela, com o modelo que roda em produção (Gemini):

> Três anos se passaram desde que homens com o brasão do corvo levaram seu irmão Teo do
> orfanato. Você ainda guarda o botão de metal que arrancou de um deles […]
>
> A Taverna do Cais de Silt é um antro escuro que cheira a peixe podre e cerveja barata […]
>
> Junto à lareira enfumaçada, um homem de casaco pesado esbraveja com um jovem mensageiro
> […] você nota que os botões de latão do agressor trazem o maldito desenho de um corvo…

Um ferreiro de templo atrás de um martelo roubado recebeu um entreposto de montanha e um
caixote com a marca do templo dele. Uma ficha mínima (eremita, objetivo "Ficar rica", sem
história) recebeu uma taverna onde um devedor tenta pagar a conta com um mapa lacrado.

## Por que a IA falhava tanto: dois tetos diferentes

Em 6 tentativas de prólogo no Gemini, 3 voltaram erro e o jogador teria visto o texto de
reserva. A suspeita era o limite por minuto. Capturando o erro de verdade, apareceram duas
coisas, e nenhuma é o limite por minuto:

1. **Sobrecarga do lado do Google (erro 503).** A resposta é "este modelo está com alta
   demanda, tente mais tarde". Não depende de quanto o jogo usou; passa sozinho em segundos.
   Às vezes o erro chega na hora, às vezes demora 30 segundos para chegar.
2. **Cota diária (erro 429).** O plano gratuito do Gemini dá **20 chamadas por dia** para o
   `gemini-3.5-flash`. Um turno de jogo faz várias chamadas, então a conta do servidor inteira
   sustenta poucos turnos por dia. Depois disso, tudo falha até a cota voltar, horas depois.

O código tratava os dois do mesmo jeito: "caia para o próximo modelo da lista". Isso funciona
com vários provedores, mas produção tem um só, então não havia próximo.

O que mudou:

- Para a sobrecarga, o prólogo agora **percorre a lista de modelos uma segunda vez** depois
  de 3 segundos (`rodadas=2` em `llm_client.chamar_com_fallback`). Só repete quando o erro
  foi sobrecarga ou demora; cota esgotada não se resolve esperando, então não insiste. O
  turno de jogo continua com uma rodada só, para não fazer o jogador esperar o dobro.
- Esses erros passageiros agora **aparecem no log** com o tipo e a mensagem do provedor.
  Antes eram mudos, e por isso não dava para saber qual dos dois tetos tinha batido.

O que **não** mudou: a cota diária. Nenhum código de repetição resolve 20 chamadas por dia.
As saídas são de configuração (mais modelos do Gemini na lista, cada um com cota própria;
plano pago; outro provedor de reserva) e ficaram como decisão em aberto.

## O que ficou de fora

- A segunda rodada não foi testada ao vivo: os testes desta sessão esgotaram a cota diária
  da chave local antes. Está coberta por teste automático com cliente falso.
- Localmente, o primeiro modelo da Groq recusa a resposta (`json_validate_failed`) e o
  prólogo sai pelo segundo. Também já era assim.
- Não conferi a tela de prólogo no navegador; o front não mudou e o texto tem o mesmo
  tamanho de antes (três parágrafos).

## Como testar

`pytest` no backend: 682 testes passando, cinco novos. Eles travam o que dá para travar sem
IA: o prompt contém a ficha e não contém a cena de reserva; chefe e objetivo vêm do servidor;
o texto de reserva começa pelo herói e apresenta as pessoas. Se a abertura ficou boa, só
gerando ao vivo e lendo. Teste automático não mede isso.
