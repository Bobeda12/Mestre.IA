# Fase 0 do plano "jogo completo": o Mundo Vivo entra, os Atos saem, e o turno aprende a caber

**Período:** 08/09/2026 · uma sessão longa com o Claude Code

## O que aconteceu

A sessão anterior tinha deixado uma feature grande sem commit: o **Mundo Vivo**. É a
peça que faz o que o narrador inventa virar coisa de verdade no jogo: cenas com objetos
que têm propriedades (uma porta *trancada*, uma estante *móvel*, um óleo *inflamável*),
pessoas com objetivo, medo, limite, necessidade e segredo, e conflitos com relógio que
avançam sozinhos enquanto o herói decide o que fazer. Vieram junto 8 ferramentas novas
para o narrador, um painel no chat e 13 testes.

Esta rodada fez três coisas: **fechou** esse trabalho (commits separados, código legado
apagado, decisão registrada), **poliu** quatro pontas soltas, e — a parte que ninguém
tinha previsto — **descobriu ao vivo por que o jogo tinha parado de responder**, e
consertou.

## O que saiu do jogo, e por quê (ADR-0032)

Até aqui toda campanha nascia de uma de 8 aberturas escritas à mão e carregava um
"esqueleto de Atos" (3 a 5 capítulos gerados no prólogo). Na prática o modelo quase nunca
avançava de Ato, as aberturas se repetiam depois de três heróis, e o que o narrador
inventava não ficava registrado em lugar nenhum. O Mundo Vivo resolve o terceiro problema
e torna os outros dois desnecessários: agora toda campanha nasce de uma **origem
determinística** (uma cena, dois NPCs com interesses opostos, um conflito com prazo e uma
estrada por onde dá para ir embora sem prometer nada) e o mundo cresce pelo que o narrador
registra. A pressão de tempo continua existindo, só que vem dos conflitos, com
consequência concreta (uma passagem bloqueada, alguém que foi embora), não de uma frase
genérica no prompt.

Saves antigos continuam abrindo: as chaves velhas ficam inertes, e um personagem criado
antes do Mundo Vivo ganha a cena do local atual na primeira vez que carrega.

## Os polimentos

- **O botão clicado aparece no chat com o texto do botão** ("Atacar Goblin"), não com o
  id da ação.
- **NPCs têm raça e retrato da raça** no painel (antes todos usavam a imagem de humano).
- **Dano ambiental fere inimigo em combate** de novo — empurrar o goblin no fogo funciona,
  e conta como a ação do turno (decisão do autor; antes um guard proibia).
- **O cenário tático não some** quando o local tem cena registrada — o WIP trocava as
  interações de terreno por um painel genérico em todo combate novo, sem querer.
- **Uma saída registrada só restringe o destino que ela nomeia.** Antes a cena inicial
  prendia o herói: só dava para ir aonde uma saída apontava.

## O achado ao vivo: o turno não cabia

Testando de verdade contra os provedores (a regra do projeto: teste com cliente falso não
pega "o modelo não chamou a ferramenta"), o primeiro turno de chat voltava vazio ou com
"o mestre perdeu o fio da meada", e o log mostrava o Groq recusando toda chamada. Três
causas, uma atrás da outra:

1. **Teto de tokens por minuto.** A chave gratuita do Groq aceita 8.000 tokens *por
   minuto* no modelo principal. Uma chamada de turno pesava ~10.000: as 30 ferramentas
   (o Mundo Vivo trouxe 8) mais o prompt. Nenhum turno cabia; tudo caía no Gemini, que
   por sua vez estourava o próprio limite no laço de até 6 passos. Conserto: o narrador
   recebe **só as ferramentas do estado atual** (em combate não vê `mover`, fora de
   combate não vê `atacar`; `escolher_especializacao` nunca — é decisão do jogador, pela
   interface), os schemas do Mundo Vivo perdem campos que o servidor preenche sozinho e
   restrições que só o Pydantic usa, as seções de técnicas e cenário tático só entram em
   combate, e o bloco do mundo vai sem campos vazios. Medido com a chamada real: ~7.600
   tokens, cabe.
2. **Uma chave a mais na mensagem.** A mensagem do prólogo era gravada no histórico com
   um campo extra (`opcoes`, para o frontend) e ia inteira ao modelo. O Gemini ignora;
   o Groq responde 400. Como o Groq é o primeiro da cadeia, *todo* turno de herói novo
   caía no fallback. Agora só `role` e `content` chegam ao modelo.
3. **A segunda chamada.** Um turno com ferramenta são duas chamadas: a que decide a
   ferramenta e a que narra. A primeira passou a funcionar; a segunda, no mesmo minuto,
   morre no teto — e o Gemini passou o dia inteiro respondendo 429. Antes disso, o turno
   inteiro era descartado: o dado já tinha decidido e o jogador via "erro" com o mundo
   intacto. Agora, se pelo menos uma ferramenta rodou, o turno **persiste** com uma
   linha fixa ("O mestre engole as palavras por um instante. O mundo, não:") e os
   eventos do juiz. É a tese do projeto virando comportamento: o juiz não precisa do
   narrador para funcionar. Resposta vazia do modelo também virou falha, não narrativa.

De quebra: o modelo recadastrou um NPC da origem com outro id e ele apareceu duas vezes
no painel — nome igual no mesmo local agora é a mesma pessoa. E o laço do agente passou
a logar cada ferramenta chamada, e o fallback loga o corpo do erro do provedor; o próximo
teste ao vivo não vai precisar de reprodução offline para saber o que aconteceu.

## Como testei

- Suíte do backend: 478 testes verdes; ruff e mypy limpos; typecheck do frontend limpo.
- Ao vivo, contra o backend local com as chaves do `.env`, em três rodadas de 3 turnos com
  65 s de pausa entre eles (para o teto por minuto zerar): a origem emergente nasce sem
  Atos, com NPCs de raça sorteada e saída livre; clicar um botão grava o texto humano no
  histórico; `mover` a partir da origem chega à Vila de Phandalin; o modelo escolhe a
  ferramenta certa nos três turnos (`rolar_teste`, `mover`, `iniciar_combate`); quando o
  provedor responde, a prosa vem inteira; quando não, o turno persiste com os eventos.
  Um save com o mundo zerado no banco ganha a cena do local ao recarregar.
- No navegador (fim da sessão): criação de personagem completa até o jogo, painel do mundo
  com retratos por raça, clique em "Examinar" virando fala do jogador no chat.

## Segunda rodada de cortes (mesma sessão)

O provedor conta os tokens dele, não os meus: o primeiro corte deixou o turno em ~9.300 pela
conta do Groq (o log passou a mostrar o corpo do erro: "Requested 9346"). Segunda rodada,
sem tirar regra nenhuma: descrições de ferramenta 40% mais curtas, os dois blocos de
instrução do prompt reescritos mais densos, instruções de combate só em combate, três
mensagens de histórico em vez de quatro, uma seção situacional da bíblia em vez de duas,
textos longos do mundo truncados no prompt (o save guarda tudo) e três memórias por turno.
Resultado medido pela conta do Groq: o pior turno passou de ~9.300 para dentro do teto de
8.000. Confirmação no navegador, que voltou a renderizar no fim da sessão: o painel "Ao seu
redor" mostra os dois NPCs com retratos de raças diferentes e os objetos da cena; clicar
"Examinar" num objeto grava no chat "VOCÊ — Examinar: Bilhete sem assinatura" e, em seguida,
a resposta do juiz.

## O que ficou registrado para depois

- Com chaves gratuitas, um turno com ferramenta raramente ganha prosa do Groq no mesmo
  minuto; a experiência boa depende do Gemini responder. Se o autor quiser o jogo fluido
  com os amigos, o caminho é a chave própria do jogador (BYOK, já existe) ou um plano
  pago — não é código.
- `WorldState.relogios` ficou sem uso; sai na Fase 4 se nenhum relógio novo aparecer.
- Cenários táticos e cenas do Mundo Vivo são dois sistemas de "lugar" que coexistem.

- O mundo inicial proposto pelo modelo às vezes vem magro (uma banca e ninguém). O validador
  passou a exigir pelo menos uma pessoa e uma saída; sem isso, cai na origem determinística.

## Próximo passo

Fase 1 do plano: economia e itens (catálogo com tags, equipar, loot por banda, mercador).
Toda ferramenta nova entra no conjunto certo de `tools_para` e o total de tokens é medido
antes e depois — o teto do provedor não perdoa.
