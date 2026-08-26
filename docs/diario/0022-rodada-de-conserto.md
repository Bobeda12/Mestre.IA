# Rodada de conserto — quatro bugs e "chega de goblins"

**Período:** 26/08/2026 · uma sessão com o Claude Code · **plano:**
`plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md` (reescrito nesta rodada)

## O que aconteceu

As 9 fases da revisão de gameplay (docs/diario/0013 a 0021) tinham acabado de ser
commitadas. O primeiro teste de verdade — eu jogando, com uma chave Gemini de outra
conta — achou quatro defeitos em cinco minutos: a chave "falhava" com um erro que não
fazia sentido, o combate prendia o jogador com a ficha fechada, os botões de sugestão
sumiam e a tag crua `[OPCOES]: ...` aparecia como texto na tela, e o dado nunca girava.

O padrão importa mais que os quatro bugs em si: **nove fases passaram em 411 testes e
quatro bugs apareceram em cinco minutos de jogo real.** Nenhum dos quatro é um erro de
lógica que um teste unitário pegaria — são todos costuras: CSS empilhado de um jeito que
só aparece com o navegador de verdade aberto, um frame SSE tratado diferente do outro, uma
preferência de acessibilidade do sistema operacional, e o segundo passo de um agent loop
contra um provedor (Gemini) que a suíte nunca tinha exercitado de ponta a ponta.

O feedback depois dos quatro bugs foi mais amplo: "tudo parece uma beta ainda". Investigando
por que, a resposta não foi falta de sistemas — o jogo tem 9 deles — foi que boa parte
ficou com dado pronto no backend e nenhum consumidor, ou com uma regra genérica demais
(todo herói de nível 1 vendo os mesmos 4 monstros, quase sempre em Phandalin; raça e
classe valendo só um +2 na criação).

## Os quatro bugs

- **Chave de outra pessoa "falhava" com 400**: não era a chave. A segunda chamada de um
  turno com ferramenta manda `content: null` numa mensagem de assistente — a Groq aceita,
  a camada OpenAI-compat do Gemini rejeita. `agent_loop.py` corrigido (string vazia, nunca
  `None`); as mensagens de erro do BYOK passaram a diferenciar por código HTTP em vez de
  culpar a chave por qualquer coisa. Estendi BYOK pro prólogo/epitáfio/crônica (antes só o
  turno de jogo respeitava "traga sua própria chave") e adicionei validação da chave ao
  salvar (`GET/POST /byok/validar`), em vez de só descobrir no meio de uma cena.
- **Preso no combate**: o HUD vermelho de inimigos era `position: absolute`, empilhado por
  cima do botão de abrir a ficha — com a ficha fechada em combate, não sobrava gesto
  nenhum pra reabri-la. Tirado do absoluto, virou uma faixa normal no fluxo.
- **Opções sumindo / tag vazando**: o frame `correcao` (quando o guardrail reescreve a
  narrativa) mandava o texto antes de limpar/extrair a tag — reordenado. E, como a tag é
  a última linha de um prompt gigante, o modelo às vezes esquecia — agora o servidor monta
  opções sozinho a partir do estado quando isso acontece (`guardrail.opcoes_padrao`).
- **Dado não girava**: `prefers-reduced-motion` já matava a animação via CSS, mas o
  `setTimeout` que espera a animação continuava esperando os mesmos 700ms à toa — a
  narração parecia travar sem nenhum giro pra justificar. Agora o JS também respeita a
  preferência (`lib/acessibilidade.ts`).

Confirmei os dois primeiros ao vivo no navegador (criei personagem, entrei em combate,
fechei a ficha, e vi o botão continuar acessível — a captura de tela original mostrava
exatamente o oposto). Os outros dois ficaram bem cobertos por teste automatizado; a
confirmação ao vivo da tag em `correcao` especificamente exigiria forçar uma violação do
guardrail contra o modelo de verdade, o que não tentei nesta rodada.

## O que passou a existir de verdade (Parte 2)

- **O jogo não começa mais do nada**: `/load_game` devolvia só "Conectado ao mundo. Local:
  X." — o `historico_chat` de verdade (gerado com capricho pelo narrador) nunca chegava à
  tela ao recarregar uma partida em andamento. Agora reconstrói as bolhas reais, com um
  recap "Anteriormente…" (a partir do resumo rolante, que já existia) quando a janela dos
  últimos 12 turnos corta alguma coisa.
- **Raça e classe passam a existir**: `[TRAÇOS]` entra no contexto do narrador (antes só o
  rótulo "Anão Guerreiro" chegava lá) e um traço com o motivo certo concede vantagem de
  verdade — `rules_engine.vantagem_por_traco`, acionado pelo novo parâmetro `motivo` que
  `rolar_teste` passou a aceitar. **Não** implementei a proficiência de arma por classe
  (Guerreiro vs Mago com a mesma espada) — `classes.json` mistura categorias ("Armas
  Marciais") com armas específicas ("Rapiers", "Adagas") de um jeito que não bate limpo
  com `weapons.json`, e forçar esse casamento arriscava matemática de combate errada. Fica
  registrado como próximo passo, não fingido como feito.
- **O dado diz por que está rolando**: `motivo` (o mesmo parâmetro novo de `rolar_teste`)
  chega ao `RollCard` — "Teste de Sabedoria" sozinho não dizia se era pra perceber uma
  emboscada ou resistir a medo. De brinde, o estilo de luta do bestiário (`comportamento`,
  já existia desde a Fase 0 e nunca tinha consumidor) virou um `title` no card de inimigo.
- **Chega de goblins**: o nome que o jogador vê e a ficha que o motor usa deixaram de ser
  a mesma coisa (ADR-0029). Um nome fora do catálogo não é mais descartado — vira a pele
  de um arquétipo sorteado da banda de nível certa; a mecânica nunca muda, só o rótulo. O
  mesmo vale pro local inicial do prólogo, que pode inventar um lugar novo com descrição
  em vez de ser forçado ao catálogo fixo (mesmo padrão do ADR-0028, aplicado antes ao
  `mover` do meio de jogo).
- **`GET /regras`**: uma aba na ficha gerada do motor de verdade (`rules_engine`,
  `ToolExecutor`, `data/weapons.json`) — nunca a bíblia do mestre, isso vazaria o prompt de
  sistema. Testado que os números batem com as constantes reais, não com uma cópia.
- **"O mestre está pensando"**: acabou não precisando de mudança — `loading` já ligava
  antes da chamada de rede começar, e o indicador já era visível durante uma chamada
  lenta. Investiguei antes de mexer e não havia bug aqui.

## O que achei no caminho

**Cota diária do Gemini grátis (20 req/dia) esgotada logo no início** — não consegui
confirmar ao vivo contra o Gemini de verdade que `content: ""` resolve o 400 (só contra
Groq, que não reproduz o bug). A correção segue a especificação OpenAI-compat com
confiança alta, mas fica registrado: não foi testada ao vivo contra o provedor que
originou o bug, só coberta por teste que fixa o comportamento da mensagem construída.

**`Frontend/dist/` não era o problema que parecia** — já estava em `.gitignore`, nunca
rastreado; o "obsoleto" da investigação original era só uma build local velha, sem
consequência em produção (Vercel builda do zero a cada deploy).

## Como testei

- **Backend**: 411 → 454 testes (43 novos), cobrindo cada bug de causa raiz (não só o
  sintoma) e cada item da Parte 2. `ruff`/`mypy` limpos a cada checkpoint.
- **Frontend**: 16 → 25 testes (9 novos, incluindo o primeiro arquivo de teste de
  `lib/utils.ts`, que nunca tinha um). `tsc`/`eslint` limpos (só os erros pré-existentes
  em arquivos não tocados nesta rodada, confirmados via `git diff` antes de declarar
  "limpo").
- **Ao vivo, no navegador**: criei personagem, entrei em combate, fechei a ficha durante o
  combate (bug B confirmado), recarreguei a partida em andamento (item G confirmado — as
  bolhas reais substituíram "Conectado ao mundo"), e abri a aba REGRAS nova (item K
  confirmado, incluindo achar e corrigir um 404 por servidor backend não reiniciado —
  lição repetida da Fase 4: o backend não roda com `--reload`).

## Decisões tomadas

- Escopo desta rodada, por pedido explícito do jogador: **conserto primeiro** (Parte 1),
  depois "desenvolver o que já temos" (Parte 2) — não sistema novo. C-5 (criação
  interativa) e C-6 (temperamento/dificuldade/estilo) do backlog antigo continuam fora,
  deliberadamente.
- ADR-0029 — só o item J mexe numa garantia de arquitetura (o bestiário deixa de ser um
  catálogo fechado de *nomes* sem deixar de ser um catálogo fechado de *números*). Os
  outros oito itens (A-I, K) são conserto ou extensão dentro de decisões já tomadas — sem
  ADR novo.
- Proficiência de arma por classe (parte do item H) ficou de fora — ver "O que achei no
  caminho" e a nota em `docs/backlog-pos-lancamento.md`.

## Números

- 454 testes de backend, 25 de frontend, todos verdes.
- `ruff`, `mypy`, `tsc --noEmit`, `eslint` limpos.
- Um ADR novo (0029), esta entrada de diário, `docs/backlog-pos-lancamento.md` atualizado.
- Dois bugs (A, B) e dois itens novos (G, K) confirmados ao vivo no navegador; os demais
  cobertos por teste automatizado determinístico.
