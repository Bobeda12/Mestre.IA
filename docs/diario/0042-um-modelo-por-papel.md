# Um modelo de IA para cada tipo de trabalho

**Período:** 05/10/2026 · continuação do diário 0041

## O que aconteceu

O diário anterior terminou com uma descoberta incômoda: o plano gratuito do Gemini dá ao
modelo que o jogo usava (`gemini-3.5-flash`) só **20 chamadas por dia e 5 por minuto**. Cada
ação do jogador custa em média 2,7 chamadas, porque o Mestre primeiro chama ferramentas
(rolar dado, mover, registrar cena) e só depois narra. Na prática o servidor inteiro
aguentava uns 7 turnos por dia.

Olhando a tabela de limites da conta, dois modelos menores, os "Flash Lite", têm **500
chamadas por dia e 15 por minuto** cada. A capacidade estava lá; o jogo só não a usava.

## A ideia

Nem toda chamada de IA do jogo precisa do mesmo modelo. Dá para separar em três tipos de
trabalho, que no código viraram três "papéis":

| Papel | O que é | Quem faz |
|---|---|---|
| **volume** | O que acontece a toda hora: cada turno, a correção de narrativa, o Oráculo da criação | 3.5 Flash Lite (500/dia) |
| **destaque** | O que acontece pouco e é lido com atenção: prólogo, cena de morte, epitáfio, fim de capítulo, crônica | Os Flash (20/dia cada, vários em fila) |
| **fundo** | O que roda escondido: o resumo da memória, a cada 8 turnos | 3.1 Flash Lite |

Cada papel tem uma lista de modelos em ordem. Se o primeiro falha ou está sem cota, o
servidor tenta o seguinte. Isso já existia (é a "cadeia de fallback"); a novidade é haver
uma lista por papel em vez de uma para tudo.

## Medir antes de trocar

Trocar o modelo que narra todo turno é arriscado, então rodei antes a suíte de avaliação do
projeto (12 situações de jogo com resultado esperado) em cada Flash Lite.

- **3.5 Flash Lite:** terminou as 12, chamou todas as ferramentas de forma válida, não
  quebrou o estado do jogo em nenhuma, resistiu a "esqueça que você é um mestre" e rolou o
  dado quando o jogador mandou pular. Defeitos: usa negrito (`**Lobo**`), que aparece cru na
  tela, e numa situação narrou um soco sem resolver o golpe.
- **3.1 Flash Lite:** falhou em 3 das 12 por sobrecarga, deixou 2 turnos sem narração e
  **obedeceu** a "esqueça que você é um mestre", respondendo como um assistente genérico.

Por isso o 3.1 ficou só com o resumo da memória (se ele falhar, o resumo antigo continua
valendo) e no fim da fila dos turnos.

## O que mudou no código

- `settings.cadeia_llm` virou três listas: `cadeia_volume`, `cadeia_destaque`, `cadeia_fundo`.
  Cada uma pode ser trocada por variável de ambiente, sem mexer no código.
- Cada lugar que chama a IA passou a dizer qual é o seu papel.
- Toda chamada atendida escreve uma linha no log com o papel e o modelo. Antes não dava para
  saber, olhando o log, quantas chamadas um turno fez nem qual modelo respondeu.
- O prólogo ganhou uma segunda chance quando a IA devolve um texto malformado: o Flash Lite
  errou o formato numa chamada e acertou na seguinte, com o mesmo pedido.

## Quando um modelo falha

Os Flash mais novos falhavam tanto que parecia defeito nosso. Sondei cada um com o menor
pedido possível ("responda só: ok"), três vezes:

| Modelo | Resultado |
|---|---|
| 3.8 Flash | 3 erros de sobrecarga em 3 |
| 3.7 Flash | 1 erro; as outras duas levaram 13 s cada |
| 3.6 Flash | 3 respostas, em 2 a 4 s |
| 3 Flash (preview) | 1 erro; uma resposta levou **293 segundos** |
| 2.5 Flash | 3 respostas, em menos de 1 s |

Não é defeito nosso. O fórum oficial do Google tem relatos iguais na última semana de
setembro, inclusive de contas pagas; a resposta da equipe é "serviço temporariamente
sobrecarregado". Dois detalhes desses relatos mudaram o código:

- **Insistir pode custar caro.** Há quem relate que cada erro de sobrecarga desconta da cota
  diária. O Google não confirmou. Na dúvida, o servidor parou de repetir no mesmo modelo:
  um modelo que falha fica de fora por alguns minutos e a fila segue para o próximo.
- **Esperar sem limite trava o jogador.** O servidor esperava até 10 minutos por uma
  resposta. Agora cada chamada tem prazo (25 s no turno, 50 s no prólogo); passou disso, o
  modelo é posto de lado e o próximo é tentado.
- **A fila inteira também precisa de prazo.** No primeiro teste ao vivo depois dessa mudança,
  um prólogo levou 201 segundos: seis modelos falharam um atrás do outro e só o sétimo
  respondeu. Cada espera estava dentro do limite; a soma não. Agora a fila tem um prazo total
  (45 s no turno, 90 s no prólogo). Acabou, o jogo usa a saída de emergência que já tinha: o
  texto de reserva no prólogo, ou o turno resolvido só pelas regras, sem narração.

Se todos os modelos da fila estiverem de lado ao mesmo tempo por sobrecarga, o servidor
tenta mesmo assim, porque um deles pode já ter voltado. Se estiverem de lado por cota
esgotada, não tenta: a resposta seria o mesmo erro.

A ordem da fila de destaque foi refeita com essas medições: 3.5 Flash, 3.6 Flash e logo o
3.5 Flash Lite, que é o único com prólogo bom comprovado e cota para repetir. O 2.5 Flash,
tão rápido na sondagem, decepcionou no prólogo de verdade: em 5 tentativas, 1 resultado
aproveitável, 2 descartados por virem com a cena malformada e 2 estouros de prazo. Ficou
depois. Pedido mínimo e pedido real são testes diferentes.

Também testei pedir aos modelos que "pensem menos" antes de responder (um parâmetro chamado
`reasoning_effort`). Não ajudou: o Flash Lite já não pensa por padrão, e nos Flash a demora
vem da fila do Google, não do raciocínio. O ajuste ficou disponível na configuração, desligado.

## O servidor passou a contar

Faltava uma peça: o servidor só descobria que um modelo tinha chegado ao limite quando o
Google respondia "cota esgotada". Isso gasta uma chamada e alguns segundos do jogador, toda
vez.

Agora ele conta as próprias chamadas, por modelo: quantas no último minuto e quantas no dia.
Os limites de cada modelo ficam na configuração (os mesmos da tabela do painel). Quando um
modelo chega ao limite, a fila simplesmente começa pelo seguinte.

Três cuidados:

- **Conta a tentativa, não só o acerto.** Se o erro de sobrecarga realmente desconta da cota,
  contar só os acertos deixaria o servidor otimista demais.
- **O dia vira na hora do Google**, meia-noite na costa oeste dos EUA (4h ou 5h de Brasília).
- **A contagem é uma estimativa.** Ela zera quando o servidor reinicia e não sabe de chamadas
  feitas por outro programa com a mesma chave (meus testes no computador, por exemplo). Então
  ela só muda a ordem da fila. Se pela contagem todos os modelos estiverem no limite, o
  servidor tenta mesmo assim e deixa o Google dar a palavra final.

Teste ao vivo, com o limite do Flash Lite baixado de propósito para 3 por minuto: as três
primeiras chamadas saíram por ele e a quarta foi direto para o modelo seguinte, sem bater no
erro. A linha de log de cada chamada agora mostra a contagem, por exemplo
`uso=3/15min 120/500dia`.

## Depois

Teste ao vivo, só com Gemini, como em produção: um prólogo saiu pelo `gemini-3.5-flash`
(papel destaque) e três turnos seguidos saíram pelo `gemini-3.5-flash-lite` (papel volume),
10 chamadas em 14 segundos, sem nenhum erro de cota.

Capacidade estimada: cerca de 185 turnos por dia e 5 por minuto.

## O que ficou de fora

- **A contagem de cota não sobrevive a um reinício do servidor.** Guardá-la no banco
  resolveria, ao custo de uma gravação a cada chamada. Ficou para se a estimativa se
  mostrar ruim na prática.
- **Quem traz a própria chave** continua preso ao modelo de 20 por dia.
- **O teto de turnos por jogador** (20 por dia) não foi recalibrado com os números novos.
- A sondagem dos Flash é de um dia só. Qual modelo está disputado muda com o dia e a hora.
- Os Flash, quando assumem um turno com ferramentas, levam 10 a 20 s por chamada. Como
  reserva servem; como modelo principal do turno seriam lentos demais.
- Não comparei o Flash Lite com o Flash nas mesmas 12 situações, porque 20 chamadas por dia
  não cobrem a suíte.

## Como testar

`pytest` no backend: 694 testes. Os novos cobrem: cada papel usa a sua lista; a ordem padrão
das listas; a segunda chance do prólogo; o resumo usa o papel de fundo; erro de sobrecarga e
prazo estourado põem o modelo de lado sem repetir; cota do dia afasta por mais tempo que a
do minuto; fila inteira de lado; prazo por papel e prazo da fila; e o contador (limite por
minuto, limite por dia, virada do dia, tentativa que falhou também conta). Para ver ao vivo,
basta jogar com o servidor local e procurar no log as linhas `ia papel=`.

A decisão, as alternativas e os sinais de que ela estaria errada estão no
[ADR-0038](../adr/0038-um-modelo-por-papel.md).
