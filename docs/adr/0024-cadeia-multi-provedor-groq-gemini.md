# ADR-0024 — Cadeia de fallback atravessando provedores (Groq + Gemini), não só modelos

**Data:** 24/08/2026
**Status:** Aceito
**Etapa:** 14
**Supersede:** revisa ADR-0008 (não substitui — a mecânica de retry/fallback continua a mesma, só passa a atravessar provedores)

---

## Contexto

O ADR-0008 (Etapa 4) criou uma cadeia de fallback entre três modelos, todos da Groq — e documentou explicitamente por que não um segundo provedor: *"não há uma segunda chave de API configurada hoje... criar uma credencial nova só para este ADR não era decisão que o código pudesse tomar sozinho"*. A interface (`chamar_com_fallback`, uma lista ordenada de tentativas) já foi desenhada para comportar isso sem reescrita.

Dois fatos novos tornam essa segunda chave necessária agora, não só desejável:

1. **ADR-0023** (mesma etapa) já introduz `GEMINI_API_KEY` no projeto — para embeddings. A chave existe; não usá-la também para chat é deixar capacidade paga (no sentido de já configurada) na mesa.
2. **A cota do free tier da Groq é pequena demais para o próprio teto que o projeto já define.** O modelo principal (`openai/gpt-oss-120b`) tem 200.000 tokens/dia no free tier. As evals do próprio projeto (`evals/cache/full_run.json`, `evals/cache/bakeoff.json`) medem 1.788 a 5.144 tokens por cenário — um turno real (bíblia + memórias + histórico + esquema de ferramentas, com o agent loop podendo fazer 2-3 chamadas) é mais caro que um cenário de eval. Isso dá **~40 a 110 turnos por dia no aplicativo inteiro**, contra um teto de `teto_turnos_conta = 60` (`app/infra/settings.py`) **por usuário** — dois jogadores animados no mesmo dia já encostam no teto da conta inteira. `teto_turnos_conta` foi um chute, não um orçamento calculado (nenhuma medição de tokens/turno existia até este ADR).

O ADR-0011 (Etapa 6, estratégia de avaliação) já registrava a mesma lacuna do outro lado: o LLM-as-judge usa o mesmo modelo forte do narrador por falta de um segundo provedor — risco de viés correlacionado (o juiz "gostar" do próprio estilo).

## Decisão

`app/infra/llm_client.py` troca o SDK `groq` pelo SDK `openai` — Groq, Gemini e outros provedores compatíveis expõem o mesmo endpoint OpenAI-compatible (só o `base_url` muda: `https://api.groq.com/openai/v1` para a Groq, `https://generativelanguage.googleapis.com/v1beta/openai/` para o Gemini), então um cliente só serve os dois, com as mesmas classes de exceção (`openai.RateLimitError`, `openai.APITimeoutError`, `openai.APIConnectionError`, `openai.APIStatusError`) que a Groq já usava (ambos os SDKs são gerados pela mesma stack, os nomes batem).

`settings.cadeia_llm` passa a ser uma lista de `"provedor:modelo"` (`"groq:openai/gpt-oss-120b"`, `"gemini:gemini-3.5-flash"`, ...), atravessando provedores de propósito: cada elo tenta o provedor correspondente, pulando silenciosamente qualquer um sem chave configurada. `clients: dict[str, openai.OpenAI]` guarda um cliente por provedor configurado — `_build_clients()` só inclui um provedor se a chave dele existir, o mesmo padrão condicional já usado para Google OAuth/Langfuse (`app/infra/settings.py`).

Cadeia padrão: Groq (`gpt-oss-120b`) → Gemini (`gemini-3.5-flash`) → Groq (`gpt-oss-20b`) → Groq (`qwen3.6-27b`). O LLM-as-judge (`evals/judge.py`) e o resumo rolante (`services/memory.py`) passam a usar `settings.modelo_barato` (`"gemini:gemini-3.5-flash-lite"`) — um provedor DIFERENTE do primeiro elo da cadeia, resolvendo de propósito a limitação que o ADR-0011 já registrava (juiz e narrador de famílias diferentes, menos viés correlacionado), e barato o bastante para o resumo continuar sendo uma chamada de baixo custo.

`_chamar_modelo` ganha `provedor` como parâmetro explícito — usado na trace do Langfuse (nome `f"{provedor}-chat"`, metadata `{"provedor": provedor}`), a instrumentação que falta hoje para medir consumo POR PROVEDOR e transformar `teto_turnos_conta` num número calculado, não um chute (ver "Como saber que erramos").

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Manter só Groq, e só subir `teto_turnos_conta` para caber na cota real (~40-50) | zero mudança de código | reduz o produto (menos turnos por jogador) em vez de resolver o problema — a cota da Groq sozinha continua pequena para qualquer uso além de um usuário só | resolve o sintoma, não a causa; o ADR-0008 já tinha deixado a porta aberta para isto |
| Um cliente `openai.OpenAI` só, apontando pra Groq, e um `google.genai` separado só pro Gemini (dois SDKs) | cada SDK "nativo" do seu provedor | dois formatos de exceção diferentes para tratar, duas formas de chamar `chat.completions`/`generate_content` — exatamente a duplicação que o ADR-0008 original evitava mantendo tudo numa função só | o endpoint OpenAI-compatible do Gemini existe precisamente para evitar isto |
| Round-robin entre provedores a cada chamada (em vez de fallback ordenado) | distribui carga de forma mais uniforme, potencialmente atrasando o esgotamento de cada cota | perde a ordem de qualidade deliberada da cadeia (o ADR-0008 escolheu a ordem testando tool-calling manualmente); complexidade de estado (qual foi o último usado) sem ganho claro na escala de tráfego deste projeto | fallback ordenado já resolve o problema real (esgotamento de cota), sem introduzir estado novo |
| Circuit breaker persistente (marcar um provedor "fora" por N minutos após 429, não retentar até o cooldown) | evita gastar uma chamada tentando um provedor sabidamente esgotado | mesmo trade-off que o ADR-0008 já registrou para modelos: estado precisaria persistir entre turnos/processos, ganho pequeno na escala de tráfego atual (um projeto de portfólio) | reavaliar se o tráfego crescer a ponto de "gastar uma tentativa" ter custo real |

## Consequências

**Ganhamos:**
- A cota diária de tokens deixa de ser um teto único (200k/dia da Groq): Groq e Gemini têm contas separadas, então um provedor esgotado no dia não derruba o outro — exatamente o objetivo original do ADR-0008 ("por que não um segundo provedor ainda"), agora resolvido.
- `chamar_com_fallback`/`chamar_stream_com_fallback` pulam provedor sem chave silenciosamente (não é uma falha, é ausência de configuração) — testado em `tests/test_llm_client.py::test_provedor_sem_chave_e_pulado_sem_contar_como_falha`.
- O juiz (`evals/judge.py`) passa a rodar num provedor/família diferente do narrador por padrão — a limitação do ADR-0011 vira decisão tomada, não mais "fica em aberto".
- `narrator.py` perdeu o import direto de `groq` e a duplicação de tradução de exceção — `chamar_mestre` delega inteiramente para `llm_client.chamar_modelo_unico`, o mesmo caminho usado por qualquer outra chamada única do projeto.
- A trace do Langfuse agora carrega `provedor` na metadata — o instrumento que faltava para medir consumo por provedor de verdade.

**Pagamos:**
- `tests/test_llm_client.py` precisou de um redesenho dos dublês de cliente (um `_FakeClient` compartilhado registrado sob cada provedor de `CADEIA`, em vez de um único `client` monkeypatchado) — mais peças móveis no teste, ainda que o comportamento coberto seja o mesmo.
- Um bug real apareceu ao fazer esta mudança e foi corrigido no processo: `services/narrator.py` importava `clients`/`chamar_modelo_unico` por nome (`from ... import clients`), criando uma referência presa no momento do import — um teste que só faz `monkeypatch.setattr(llm_client, "clients", ...)` não afetaria essa referência local, só `monkeypatch.setattr(narrator, "clients", ...)` afetaria (e só o guard, não a chamada real dentro de `chamar_modelo_unico`, que lê a referência PRÓPRIA do módulo `llm_client`). Corrigido importando o módulo inteiro (`from app.infra import llm_client`) e acessando `llm_client.clients`/`llm_client.chamar_modelo_unico` sempre por atributo — a mesma classe de bug que motivaria desconfiar de qualquer `from modulo import nome_mutavel` num código que espera ser monkeypatchado de fora.
- Cadeia mais longa entre "todos os provedores falharam" pode levar mais tempo até desistir (mais elos, cada um com até 2 tentativas de `tenacity`) — não medido nesta etapa, mesmo trade-off que o ADR-0008 original já pagava por modelo, agora por modelo × provedor.

**Testado ao vivo** (chave real configurada em `.env`, não só dublê de teste): `chamar_modelo_unico("gemini:gemini-3.5-flash", ...)` respondeu texto simples, respondeu com `tool_calls` corretos (nome e argumentos certos) dado um cenário de teste de atributo, e respondeu em `response_format=json_object` válido no modelo barato (`gemini-3.5-flash-lite`, o caminho do resumo rolante). `chamar_stream_com_fallback` também testado ao vivo (primeiro elo, Groq) — streaming chegando chunk a chunk normalmente. O que este ADR não testou: o Gemini como fallback de fato assumindo depois de o Groq falhar de verdade (forçar isso exigiria esgotar cota real, não feito de propósito — mesma lacuna que o ADR-0008 original já tinha para o fallback entre modelos da Groq).

**Fica em aberto:**
- `teto_turnos_conta`/`teto_turnos_convidado` continuam sendo os mesmos números de antes (60/20) — a instrumentação por provedor que este ADR adiciona é o que permite calculá-los de verdade a partir de tokens/turno reais, não foi refeito aqui.
- Nenhuma distinção entre "429 por minuto" (vale re-tentar em instantes) e "429 por dia" (só volta amanhã) — os dois caem no mesmo `_ERROS_TRANSITORIOS`/retry curto antes de cair pro próximo elo, o que é seguro (só custa uma tentativa extra) mas não é o mais eficiente possível.
- Tool-calling e qualidade de narrativa do Gemini como segundo elo da cadeia principal não foram validados com o bake-off de modelos (`evals/run_eval.py --bake-off`) antes de fixar a ordem — a ordem escolhida (Groq → Gemini → Groq → Groq) é uma hipótese razoável (family diversity cedo na cadeia), não uma medição.

## Como saber que erramos

Se, depois de configurar `GEMINI_API_KEY` em produção e rodar por um tempo, a trace do Langfuse mostrar que `gemini-3.5-flash` tem uma taxa de tool-call accuracy sensivelmente pior que os modelos da Groq (o bake-off, `evals/run_eval.py --bake-off`, é o jeito de medir isso formalmente), reordenar a cadeia ou tirar o Gemini do meio dela — `settings.cadeia_llm` existe justamente para isso ser um ajuste de configuração, não uma mudança de código.

Se a metadata `provedor` do Langfuse mostrar que um provedor nunca é de fato usado (a cota da Groq nunca esgota na prática), o segundo provedor não estava resolvendo o problema que motivou este ADR — vale medir antes de adicionar um terceiro.

## Referências

- ADR-0008 — a decisão original de cadeia de fallback, cuja interface esta revisão estende sem reescrever.
- ADR-0011 — a limitação do juiz de família única, resolvida aqui.
- ADR-0023 (mesma etapa) — a chave do Gemini que esta decisão reaproveita para chat, já introduzida para embeddings.
- [Groq — Rate limits](https://console.groq.com/docs/rate-limits) — 30 RPM / 1.000 RPD / 8.000 TPM / 200.000 TPD para `openai/gpt-oss-120b` no free tier, o número que motivou esta ADR.
- [Groq — OpenAI compatibility](https://console.groq.com/docs/openai) — `base_url` e o que funciona através dele.
- [Gemini API — OpenAI compatibility](https://ai.google.dev/gemini-api/docs/openai) — `base_url`, suporte a tool calling/streaming/`response_format`.
- `evals/cache/full_run.json`, `evals/cache/bakeoff.json` — os números reais de tokens/cenário usados para estimar o teto de turnos/dia.
