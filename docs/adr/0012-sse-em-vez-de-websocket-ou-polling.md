# ADR-0012 — SSE em vez de WebSocket ou polling, com cadeia de fallback só antes do primeiro chunk

**Data:** 21/08/2026
**Status:** Aceito
**Etapa:** 7
**Supersede:** —

---

## Contexto

Até esta etapa, `POST /chat` (`routers/game.py`) é uma chamada síncrona clássica: o cliente manda a ação, o servidor roda o loop de ferramentas inteiro (`agent_loop.executar_turno`) e só devolve JSON quando a narrativa completa já está pronta. `Frontend/src/components/GameChat.tsx` reflete isso — a bolha de resposta aparece de um golpe só, depois de um `axios.post` esperar o corpo inteiro.

O plano desta etapa (`PLANO_MESTRE.md`) pede duas coisas concretas: efeito de máquina de escrever de verdade (não CSS simulando, texto real chegando aos poucos) e **medir** o tempo até o primeiro token antes/depois — "é a única otimização de latência que o usuário percebe". Medir de verdade exige que o primeiro token saia do servidor assim que o modelo o produzir, não que o cliente finja.

A complicação é a cadeia de fallback entre modelos (ADR-0008): `chamar_com_fallback` troca de modelo quando um falha, e isso só é seguro **antes** de qualquer coisa ter sido mandada para o jogador. Streaming quebra essa suposição — depois do primeiro chunk, o jogador já viu texto de um modelo específico.

## Decisão

Um endpoint novo, `POST /chat/stream` (`routers/game.py`), via `StreamingResponse` do Starlette puro — sem `sse-starlette`, formatando `event:`/`data:` à mão (`_sse()`, ~2 linhas). `/chat` **continua existindo sem mudanças**: os testes e o framework de avaliação da Etapa 6 (`evals/harness.py`) dependem dele, e nada nesta etapa tinha motivo para arriscar esse contrato.

A cadeia de fallback ganha uma versão em streaming, `llm_client.chamar_stream_com_fallback`: tenta cada modelo com `stream=True`; troca de modelo é permitida **só antes do primeiro chunk** chegar (erro de conexão/4xx/5xx na hora de abrir a stream). Depois do primeiro chunk, a stream está "comprometida" com aquele modelo — uma falha a partir daí vira `ErroMestre` (o cliente recebe um frame `event: error`), nunca uma troca silenciosa que costuraria a resposta de dois narradores diferentes.

`agent_loop.executar_turno_stream` espelha `executar_turno` (mesmo loop de ferramentas, mesmo limite de passos) mas devolve um generator de `EventoStream` — `token` (delta de texto), `tool_event` (uma ferramenta resolveu; carrega o `DadosRolagem` estruturado da Fase 1 desta etapa) e `erro`. Deltas de `tool_calls` nunca viram `token`: só texto de narração é mostrado ao vivo, o JSON de uma ferramenta em montagem não interessa ao jogador — e, na prática, o modelo usado (`openai/gpt-oss-120b`) também manda tokens de **raciocínio** num canal `reasoning`/`channel: "analysis"` separado de `content`; como o código só olha `delta.content`, esse raciocínio nunca vaza para a tela.

No frontend, como `EventSource` não manda corpo em POST, um parser SSE feito à mão (`lib/sse.ts`, `fetch` + `ReadableStream`) substitui o `axios.post`.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| WebSocket | canal bidirecional, reconexão nativa em várias libs | o jogo não precisa do servidor iniciar mensagens fora de uma resposta a uma ação do jogador — é sempre pergunta→resposta, nunca push espontâneo; exige gerenciar ciclo de vida de conexão (handshake, ping/pong, reconexão) que HTTP já resolve sozinho | complexidade paga por uma capacidade (bidirecionalidade) que este turno de jogo nunca usa |
| Polling (cliente pergunta "terminou?" a cada N ms) | mais simples de implementar, funciona com qualquer proxy/CDN sem configuração especial | não resolve o problema que motivou a etapa: o texto ainda só aparece quando o polling flagra o turno pronto, não token a token; e desperdiça requisição a cada intervalo mesmo sem novidade | não ataca a métrica que o plano pede pra medir (tempo até o primeiro token visível) |
| Streaming sem ajustar a cadeia de fallback (deixar `chamar_com_fallback` como está, só trocar `/chat` por streaming por cima) | menos código novo | ou perde o fallback inteiro (uma falha de rede no meio derruba o turno sem alternativa), ou tenta trocar de modelo depois que o jogador já viu texto — os dois errados | o fallback é uma decisão já tomada (ADR-0008); a versão em streaming precisa preservar a garantia, não descartá-la |

## Consequências

**Ganhamos:**
- Testado contra a Groq de verdade (não só com fake roteirizado): um turno de combate real produziu o `tool_event` da rolagem (`d20(17)+4=21 vs CA 15 → ACERTO! 7 de dano`) antes do `token` da narração final, e a XP da Fase 1 desta mesma etapa foi concedida corretamente no meio do fluxo — a integração ponta a ponta funciona, não só cada peça isolada.
- O jogador vê a narração crescendo em tempo real, e o card de rolagem aparece no momento exato em que o dado "caiu" — não só no fim, misturado no texto como emoji solto.
- `evals/harness.py` e `/chat` continuam intocados: a Etapa 6 não corre risco nenhum por causa desta.

**Pagamos:**
- **O achado desconfortável de medir de verdade**: numa amostra ao vivo (turno de 2 passos — ferramenta `mover`, depois narração), o primeiro token visível saiu em **~1,26s**, com o texto inteiro (222 tokens noutro turno de combate) terminando pouco depois. Isso não é rede lenta — é o modelo gastando tempo no canal `reasoning` (raciocínio interno, escondido do jogador) antes de emitir qualquer conteúdo público. Streaming reduz o tempo até o *resto* do texto aparecer, mas não elimina essa espera inicial: para um modelo de raciocínio, "tempo até o primeiro token" ainda é dominado pelo pensamento, não pela rede. Ver Lição 08 para a medição completa.
- `routers/game.py` agora tem duas versões da mesma montagem de contexto (`chat_endpoint` e `chat_stream_endpoint`) lado a lado, deliberadamente duplicadas — ver "Fica em aberto".
- O guardrail (Etapa 4) corrige a narrativa **depois** que o jogador já a viu chegando ao vivo. Reescrever em silêncio na tela seria mais confuso (o texto "mudaria sozinho"); a solução adotada é um frame `event: correcao` à parte, que o cliente usa pra atualizar o que fica salvo, mas o jogador já leu a versão não corrigida no momento em que ela apareceu.
- Uma falha de rede genuína no meio de uma stream vira um erro duro pro jogador (sem fallback), em troca de nunca misturar dois narradores na mesma resposta — trade-off deliberado, não um bug.

**Fica em aberto:**
- Fundir `chat_endpoint`/`chat_stream_endpoint` numa montagem de contexto compartilhada, sem duplicar a lógica de morte/memória/guardrail — adiado por risco ao contrato de `/chat` que os testes e o `evals/harness.py` usam, não por não saber como fazer.
- Não existe uma bateria sistemática de medições antes/depois (múltiplos turnos, percentis) — só a amostra ao vivo documentada na Lição 08. Um número p50/p95 de verdade, como o que `evals/metrics.py` já faz para latência de chamada única, ficaria mais forte.
- `aria-live="polite"` no container de mensagens (acessibilidade) recebe um `token` a cada poucos caracteres — pode soar picotado num leitor de tela real. Debounce por frase/sentença ficou para depois.

## Como saber que erramos

Se a duplicação entre `/chat` e `/chat/stream` virar fonte real de bug (uma correção aplicada num e esquecida no outro, pega em revisão ou ao vivo), vale parar e fundir os dois caminhos, mesmo com o risco ao contrato do `evals/harness.py` — nesse ponto a duplicação já estaria custando mais do que a proteção vale.

## Referências

- [MDN — Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) — formato de frame `event:`/`data:` usado por `lib/sse.ts` e `_sse()`.
- [ADR-0008](0008-cadeia-de-fallback-de-modelo.md) — a cadeia de fallback que `chamar_stream_com_fallback` adapta pra streaming.
- `PLANO_MESTRE.md`, Etapa 7 — "streaming SSE... o tempo até o primeiro token despenca — é a única otimização de latência que o usuário percebe. Meça antes e depois."
- Lição 08 — a medição ao vivo completa, incluindo o achado do canal `reasoning`.
