# ADR-0039 — Trilha do capítulo: a IA escolhe e redige o passo, o servidor confere pelo estado do jogo

**Data:** 06/10/2026
**Status:** Aceito
**Etapa:** Plano "Trilha do capítulo + Combate v2" (Fase 2)
**Supersede:** — (revisa o ADR-0035: o capítulo continua fechando pelo servidor, mas a exigência de 8 turnos vira 3 passos cumpridos)

---

## Contexto

O jogador não tinha como saber o que fazer agora nem se tinha avançado.

- O objetivo (`QuestLog`) era um texto sem ciclo de vida: não tinha passos nem estado
  "cumprido". `concluir_objetivo` dava 50 XP quando a IA decidia e não mudava nada na tela.
- O capítulo (`Arco`) tinha fechamento conferido pelo servidor (ADR-0035), mas entre abrir
  e fechar não havia nada. A exigência de "8 turnos de jogo" media tempo, não o que o
  jogador fez; e clicar em qualquer botão de painel contava como turno.
- `abrir_arco` e `encerrar_arco` só entravam na lista de ferramentas do narrador se o
  jogador escrevesse "arco", "missão", "objetivo" ou "capítulo".

A tese do projeto (ADR-0006) é que a IA propõe e o servidor decide. A progressão da
história era o último pedaço em que a IA decidia sozinha quando algo estava "cumprido".

## Decisão

Cada capítulo tem uma **trilha de passos em sequência** (`Arco.passos`, em
`domain/living_world.py`; regras em `services/capitulo.py`).

1. **Todo passo carrega uma condição que o servidor sabe ler do estado do jogo**
   (`CondicaoPasso`). Nove tipos: chegar a um local, falar com uma pessoa, ganhar a
   cooperação de alguém, investigar um objeto, recolher um objeto, intervir no conflito,
   enfrentar o chefe, registrar um fato novo, fechar o capítulo.
2. **O servidor confere depois de cada ferramenta bem-sucedida** (`conferir_passo`, no fim
   de `ToolExecutor.executar`). Cumprido: grava uma frase de evidência ("Você ouviu Íria."),
   dá 50 XP fixos e pede o próximo passo. Não confere durante combate.
3. **Só o passo atual existe.** O seguinte nasce quando o atual fecha. O servidor monta até
   8 candidatos verificáveis e ainda falsos (`candidatos_passo`); a IA devolve
   `{"candidato": <índice>, "texto": "<frase>"}`. Ela escolhe e redige; não cria condição.
4. **A IA nunca trava a trilha.** Sem provedor, com erro, com índice inválido, texto fora
   de 8–140 caracteres ou contendo o nome do chefe, o servidor usa o primeiro candidato com
   o próprio texto de molde. Não há segunda tentativa.
5. **Passo que ficou impossível é pulado** (a pessoa foi embora, o conflito fechou por
   outro caminho) e outro nasce. Pular não dá XP.
6. **O capítulo fecha com 3 passos cumpridos**, 2 fatos registrados e o conflito central
   fechado ou o chefe vencido. Quando isso vale, o passo atual vira "Feche este capítulo".
7. **`abrir_arco` e `encerrar_arco` aparecem para o narrador pelo estado** (não há capítulo
   e existe conflito ativo; ou o capítulo pode fechar). `concluir_objetivo` sai da lista do
   narrador: o XP de progresso é o dos passos.

A chamada de IA usa o papel "fundo" (ADR-0038), com prazo de 8 segundos, e acontece no fim
do request em que o passo fechou, ao lado da geração do desfecho do capítulo.

## Alternativas consideradas

- **A IA marca o passo como cumprido, o servidor só limita abuso.** Mais flexível para
  histórias fora do comum. Rejeitada: repete o problema de `concluir_objetivo`, em que a IA
  esquece de marcar ou marca cedo, e o jogador vê um passo "feito" que não fez.
- **Roteiro fixo de 3–4 passos ao abrir o capítulo.** Mais previsível e fácil de testar.
  Rejeitada pelo dono do produto: o jogo precisa reagir ao que o jogador faz, e um roteiro
  escrito no começo não sabe quem ele poupou ou o que quebrou.
- **A IA inventa a condição do passo em texto livre e o servidor tenta interpretar.**
  Rejeitada: o servidor acabaria aceitando condições que não sabe conferir.
- **Eventos ("o jogador conversou") em vez de estado ("a pessoa foi ouvida").** A primeira
  versão do desenho usava ganchos em cada ferramenta. Trocada por leitura de estado: um
  campo novo (`PessoaMundo.ouvida`) e um contador por passo (`Passo.base`) bastaram, e a
  conferência ficou num lugar só.

## Consequências

- **Melhor:** a progressão do capítulo entra na tese. O teste de ponta a ponta mostra o
  caminho inteiro sem IA: clique, passo cumprido, próximo passo, recarga.
- **Melhor:** o jogador que resolve tudo conversando ganha XP por passo, sem depender de a
  IA lembrar de recompensar.
- **Pior:** só existem passos dos nove tipos. Uma história que avance por um caminho que
  nenhum tipo cobre cai no passo de reserva ("Descubra algo novo sobre a situação"), que
  fecha com qualquer fato novo registrado. É uma trilha menos rica que a história.
- **Pior:** uma chamada de IA a mais a cada passo fechado, dentro do request (medido ao
  vivo: 1,0 a 3,4 s). Com a IA lenta, o clique que fecha um passo pode esperar até 8 s.
- **Compatibilidade:** `versao_mundo` vai a 2. Capítulo aberto antes da trilha recebe
  passos creditados pelos turnos já jogados (1 a cada 3, até 3), para ninguém recomeçar do
  zero. `Arco.marcos_no_inicio` e o XP de `concluir_objetivo` em saves antigos não mudam.
- **Diverge do plano aprovado:** o plano listava também "vencer um combate" e "conflito
  fechado" como tipos de passo. Ficaram de fora: o primeiro não tem alvo que o servidor
  conheça antes de a luta existir, e o segundo já é a condição de fechar o capítulo.

## Como saber que erramos

- A maioria dos passos de uma campanha real termina "pulado" ou cai no passo de reserva:
  os nove tipos não descrevem o que os jogadores fazem.
- A taxa de passos com `origem = "servidor"` em produção fica alta: a IA está falhando em
  devolver um índice válido, e o texto de molde é o que o jogador vê.
- Capítulos deixam de fechar (o risco já anotado no ADR-0035, agora com mais uma condição).

## Referências

- `Backend/app/services/capitulo.py`, `Backend/tests/test_capitulo.py`
- Diário 0047; ADR-0006, ADR-0035, ADR-0038
