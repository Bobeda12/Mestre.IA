# Trilha e Combate v2, Fase 3: a aba Jornada nova

**Período:** 06/10/2026 · continuação do diário 0047

## O problema

A aba Jornada tinha 17 blocos e cerca de 8 formulários numa coluna estreita. O objetivo do
jogador era o sexto bloco, abaixo de projetos, lugares, abastecimento e organizações. No
celular, onde a ficha é uma gaveta, era preciso rolar bastante para achar o que fazer.

## O que mudou

A aba agora tem três partes, nesta ordem:

1. **Seu objetivo agora.** O texto do objetivo e um link discreto, "Mudar de rumo", que
   abre um campo só quando o jogador quer trocar.
2. **Capítulo N · título.** A premissa em até três linhas e a trilha:
   - ✔ passo cumprido, com a prova logo abaixo ("Você ouviu Bram.");
   - ▶ o passo de agora, destacado;
   - ○ ??? um único passo oculto, para lembrar que a história continua;
   - – passo deixado para trás (riscado), quando o alvo sumiu.
   O botão "Encerrar capítulo" só aparece quando o servidor diz que pode. "Abandonar" é um
   link pequeno e pede confirmação.
3. **O que ficou para trás.** Os fatos marcantes, do mais recente ao mais antigo, e os
   capítulos encerrados.

O arquivo `AbaJornada.tsx` caiu de 266 para cerca de 140 linhas. A aba recebia 11
propriedades e agora recebe 5.

### O que saiu da tela

Projetos, lugares transformados, abastecimento, organizações, o formulário de intervir em
conflito, segredos do lugar, ecos, aprendizados, descobertas, marcas e momentos. Os
componentes `ProjetosJornada.tsx` e `LugaresDaJornada.tsx` foram apagados com seus testes.

Esses sistemas **continuam funcionando no servidor** e a IA continua usando-os na
narração. O que mudou é que o jogador mexe neles conversando com o mestre, não por
formulário.

Também saiu a linha "Para fechar: faltam 3 passos da trilha; faltam 1 fatos registrados;
o conflito central ainda está aberto…". Eu a tinha mantido na primeira versão e, vendo na
tela, ela era uma lista de regras do servidor no meio de uma aba que quer ser simples. O
passo atual já diz o que fazer.

## O que ficou pendente

- **O servidor ainda manda os dados dos painéis escondidos.** A resposta de cada turno
  continua trazendo projetos, organizações etc., que a tela não usa mais. Cortar isso
  encolhe a resposta, mas mexe em outras telas (o palco e a aba Relações leem parte desses
  dados). Fica para a limpeza final (Fase 9).
- **Aprendizados não têm mais botão.** "Desenvolver este aprendizado" era um botão desta
  aba. A ação ainda existe no servidor, sem tela. Se fizer falta, o lugar natural é a aba
  Poderes.
- **Ao entrar como convidado, a tela de entrada não muda sozinha.** Vi isso testando: a
  conta de convidado é criada, mas a página continua em `/entrar` até eu navegar para a
  inicial. Não investiguei; pode ser só do ambiente local. Anotado para conferir.

## Como foi verificado

**Testes.** 10 em `AbaJornada.test.tsx`, reescritos antes do componente: ordem dos passos,
um só passo oculto, botão de encerrar só com permissão do servidor, confirmação ao
abandonar, mudar de rumo, lista do passado, travas em combate. Frontend: tipos sem erro e
todos os testes passando.

**No navegador, com o jogo de verdade** (servidor e IA reais, conta de convidado local):

1. Personagem novo, com mundo gerado pela IA. A aba mostrou "Capítulo 1 · A Pista do
   Norte" e o passo "Fale com Bram.", criado pelo servidor sem IA.
2. Conversa com Bram, pelo mesmo endereço que o botão usa. Resposta em 4,9 s, já com:
   - "✔ Passo cumprido: Fale com Bram." e 50 XP;
   - o passo seguinte, escrito pela IA: "Persuada Bram a revelar o que ele sabe sobre o
     destino da sua irmã após ouvi-lo."
3. Página recarregada: a trilha estava igual, com ✔, ▶ e ???.
4. Conferido em tela larga (1280 px) e em tela de celular (375 px), sem rolagem lateral.

**O que não foi verificado.** Um capítulo inteiro, do primeiro passo ao encerramento,
jogado no navegador; só o primeiro passo e o nascimento do segundo. O clique nos botões
"Encerrar capítulo" e "Abandonar" foi testado só nos testes automáticos.
