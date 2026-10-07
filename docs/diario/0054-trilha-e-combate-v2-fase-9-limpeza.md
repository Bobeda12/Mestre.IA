# Trilha e Combate v2, Fase 9: limpeza e o que faltava

**Período:** 07/10/2026 · continuação do diário 0053 · última fase do plano

## O que esta fase fez

As fases anteriores construíram o novo ao lado do antigo. Esta tirou o antigo, fechou as
portas que ficaram abertas e resolveu as pendências anotadas pelo caminho.

### 1. O motor de combate antigo saiu

Desde a Fase 5, o motor antigo só rodava em estados montados à mão pelos testes. Agora:

- Toda luta é do motor de turnos. Um estado antigo é convertido na entrada.
- Saíram do código: a "reação dos inimigos colada na ação", a rodada de inimigos de uma
  vez só, e a tática lida por palavra-chave do texto livre da ficha.
- Saíram os testes que exercitavam essas funções: quatro classes de teste inteiras e mais
  quatro testes avulsos. Outros 12, que descreviam o
  comportamento "tudo num clique" pelo executor, foram trocados por 5 equivalentes no
  motor novo (investir, esconder-se, dano do cenário, óleo de lâmina, card do ataque).

**Um erro meu no meio disso.** O filtro que apagava testes do motor antigo procurava, entre
outros nomes, `turno_atual`. Esse também é o nome de um parâmetro da busca de memória, e o
filtro apagou testes de busca e de memória que não tinham nada a ver. Percebi pela lista de
arquivos alterados, restaurei os três arquivos e conferi os outros removidos um a um. Um
teste de intenção contra inimigo, que só tinha sido pego por usar um dublê da função
antiga, voltou sem o dublê.

### 2. O narrador saiu do combate

- **O chat fica fechado durante a luta.** As duas rotas de chat respondem "você está em
  combate" (código 409). A tela já não mandava chat em combate desde a Fase 7; isto fecha a
  porta para quem chamar a rota direto.
- **O narrador não recebe mais ações de combate.** As nove (atacar, investir, esquivar,
  defender, esconder-se, fugir, usar técnica, interagir, comandar aliado) saíram da lista de
  ferramentas dele. Continuam existindo para o clique.
- **O prompt perdeu o ramo de combate ativo.** As seções de combate, técnicas da classe e
  cenário interativo só eram montadas com luta em curso, e agora nunca são.
- **`concluir_objetivo` foi removida.** Já não era oferecida ao narrador desde a Fase 2.

### 3. Cenários de avaliação de combate

Oito dos dez cenários esperavam o narrador chamando "atacar", "usar item" ou "consultar
regra" no meio da luta. Esse caminho não existe mais. Foram reescritos para a fronteira
que sobrou para o narrador:

- abrir a luta na hora certa (jogador ataca primeiro, nome inventado, emboscada, criatura
  acima do nível);
- **não** aceitar uma vitória declarada pelo jogador;
- **não** abrir luta numa conversa só tensa;
- o que acontece logo antes da luta (poção, pergunta de regra).

**Não rodei a avaliação com a IA.** O arquivo carrega e passa na validação de formato, mas
a nota de cada cenário novo não foi medida, e a linha de base antiga (`baseline.json`) não
vale mais para esta categoria.

### 4. Revisão do save separada do tempo de jogo

Cada clique compara um número com o servidor antes de gravar, para um clique repetido
nunca valer duas vezes. Esse número era o próprio "turno do mundo". Com várias jogadas por
turno (mover, ação bônus, ação), o relógio do mundo andava três vezes mais rápido em
combate, e qualquer clique de painel também o adiantava.

Agora são dois números: `revisao` (sobe a cada clique) e `turno` (tempo de jogo, que só
anda quando o herói fecha um turno em combate ou faz algo que consome ação fora dele).

### 5. A tela recebe só o que desenha

A resposta de cada turno trazia projetos, organizações, remessas, conflitos e mais uma
dezena de campos que a tela deixou de usar na Fase 3. Agora vai só a cena do local, as
pessoas, as oportunidades e os aprendizados. Os tipos do frontend e 27 linhas de estilo
sem uso também saíram.

### 6. O teste de ponta a ponta voltou a passar

`e2e/jogar-um-turno.spec.ts` estava quebrado desde antes da "uma tela só" (ADR-0036). Dois
motivos:

- **Um defeito de verdade.** Entrar como convidado criava a conta, mas a tela voltava para
  a entrada. A tela de entrada pedia para reler a sessão e navegava em seguida; só que ela
  mesma não observava a sessão, então o pedido não buscava nada, e a página protegida via
  "não logado". Era o defeito que eu tinha anotado na Fase 3 sem investigar. Corrigido em
  `lib/auth.ts`.
- **O assistente de criação mudou** de 5 para 6 passos. Em vez de refazer o teste clique a
  clique (e quebrá-lo de novo na próxima mudança), o personagem é criado pela API dentro do
  teste. O que o teste protege é o caminho até o primeiro turno.

Há um segundo teste novo: a aba Jornada de um herói recém-criado mostra o objetivo, o
capítulo 1, o passo atual e o "???".

### 7. Pendências pequenas

- **Aviso de "crie uma conta"** não aparece mais durante a luta (cobria os botões de
  combate no celular).
- **Bíblia do mestre.** O trecho de combate mandava "você pede o dado" e citava "Ação
  Ardilosa" e "Escudo Arcano", que o jogo não tem. Reescrito: quem rola é o servidor, e os
  inimigos lutam como a ficha diz.
- **Painel de regras** ganhou o turno em três partes, aproximar e recuar, ação bônus,
  improvisar e Foco.
- **Documentos:** README e plano mestre dizem que o combate deixou de ser só "teatro da
  mente"; os cinco documentos dos sistemas que perderam painel avisam isso no topo.

## Verificação

**Automática.** Backend: 917 testes, `ruff` e `mypy` limpos. Frontend: 84 testes e tipos
sem erro. Ponta a ponta: 2 testes passando, com navegador, servidor e IA reais na criação.

**No navegador, com o código final:**

| O que | Resultado |
|---|---|
| Luta contra dois inimigos (Orc e Aranha Gigante), herói de nível 3 | A aranha, mais rápida, agiu antes: avançou, acertou e envenenou. Fila "Aranha Gigante › Lia › Orc", "envenenado · 3" sob o herói, PERTO e LONGE certos |
| Aba Poderes | Traço "Veterano" e "Ação bônus · 1 Foco" no Golpe tático |
| Herói caído | Botão Resistir; três falhas; tela de fim de jornada |
| Chefe do capítulo (Bugbear com o nome "O Algoz das Cinzas"), Bárbaro de nível 4 | Fúria como bônus mais ataque; aviso "GOLPE PESADO" no chefe; vitória na segunda rodada; prosa narrou a queda |
| Depois do chefe | Foco em 0/4 (não voltou cheio); o capítulo deixou de pedir "conflito aberto"; revisão 5 e turno 3; nome do chefe fora da resposta |

**O que essa passada mostrou e não é bom:** o Bárbaro de nível 4 derrubou o chefe em duas
rodadas sem levar dano. É o que o relatório 0005 já dizia (lutas curtas, Bárbaro forte),
visto na tela.

## O que continua em aberto

- **Um capítulo inteiro jogado no navegador**, do primeiro passo ao encerramento. Só o
  primeiro passo e o nascimento do segundo foram vistos (Fase 3), e a vitória sobre o chefe
  (agora). O encerramento pela tela está coberto só por teste automático.
- **A avaliação com IA dos cenários novos de combate** e a nova linha de base.
- **Balanceamento:** lutas curtas, chefes duros no primeiro nível de cada degrau, Bárbaro e
  Bruxo acima da meta, conjurador que só ataca perdendo metade das lutas. Detalhe no
  relatório 0005 e no ADR-0042.
- **"Encerrar turno" em quase todo turno** para as dez classes com ação bônus.
- **Lutas com vários inimigos são raras** nos níveis altos: o orçamento de XP do encontro
  quase nunca comporta dois monstros da banda. Não mexi.
- **No celular**, o selo do palco ainda cobre a etiqueta dos personagens da esquerda, e o
  palco recolhido não mostra distância.
- **Julgamento de improviso sem IA** continua pobre.
- **O teste de ponta a ponta cria contas de convidado e heróis no banco local** a cada
  execução, como o antigo já fazia.
