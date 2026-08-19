# ADR-0008 — Cadeia de fallback entre modelos da Groq, com retry por erro transitório

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 4
**Supersede:** —

---

## Contexto

Até esta etapa, `app/infra/llm_client.py` tinha um único `Groq(api_key=...)` e um único `MODEL_NAME` (`openai/gpt-oss-120b`, `app/infra/settings.py`). Um `RateLimitError` (cota de free tier estourada), um `APITimeoutError` ou um `APIStatusError` (modelo indisponível) derrubava o turno inteiro: `narrator.chamar_mestre` convertia qualquer um desses em `ErroMestre`, e o jogador via uma mensagem de erro sem alternativa nenhuma — sem retry, sem segundo modelo, sem nada.

O free tier da Groq limita cota **por modelo**, não por conta — um turno que falha porque `openai/gpt-oss-120b` estourou a cota é resolvível na hora só trocando de modelo, não esperando. Isso transforma uma restrição de custo (não dá para pagar por uma conta paga só para este projeto de portfólio) numa oportunidade real de arquitetura de confiabilidade, em vez de só um limite a contornar.

## Decisão

`app/infra/llm_client.py` ganha uma cadeia de modelos (`MODELOS = [settings.model_name, *settings.modelos_fallback]`) e uma função única de entrada, `chamar_com_fallback(msgs, tools, tool_choice)`. Por modelo, `tenacity` cobre até 2 tentativas com backoff exponencial curto (`wait_exponential(multiplier=0.5, max=4)`) para erro transitório (`RateLimitError`, `APITimeoutError`, `APIConnectionError`); esgotado, ou em `APIStatusError` (modelo indisponível/decomissionado), a chamada cai para o próximo modelo da lista, na ordem. Só levanta `ErroMestre` — a mesma exceção de sempre, agora movida de `services/narrator.py` para `app/infra/llm_client.py` (é um erro de cliente de LLM, não uma regra de narrativa; movê-la evita `services/agent_loop.py` precisar importar de `services/narrator.py`, o que inverteria a direção de dependência do ADR-0003) — se todos os modelos da cadeia falharem.

Confirmado com o usuário: a cadeia é **entre modelos da própria Groq**, não entre provedores diferentes — não há uma segunda chave de API configurada hoje (`.env` só tem `GROQ_API_KEY`), e criar uma credencial nova só para este ADR não era decisão que o código pudesse tomar sozinho. A interface (`chamar_com_fallback`, uma lista ordenada de "tentativas") já é genérica o bastante para um segundo provedor real (ex: um cliente OpenAI-compatible de outro host) entrar como mais um item da cadeia, sem reescrever a função.

Os dois modelos de fallback (`openai/gpt-oss-20b`, `qwen/qwen3.6-27b`) foram escolhidos consultando o catálogo real da Groq (`client.models.list()`) e testando tool calling manualmente em cada um antes de fixar no `settings.py` — não foram chutados. `qwen/qwen3.6-27b` é de uma família de modelo diferente da principal (`openai/gpt-oss-*`), o que também reduz a chance de as duas cotas serem impactadas pelo mesmo tipo de limite ao mesmo tempo.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Um segundo provedor real (ex: Cerebras, OpenRouter) já nesta etapa | fallback de verdade, cotas de infraestrutura totalmente independentes | exige uma chave de API que não existe hoje — decisão de conta, não de código, e o usuário optou por não criar uma agora | escopo confirmado com o usuário antes de implementar (ver decisão acima) |
| Só retry, sem fallback de modelo (esperar e tentar de novo o mesmo modelo até funcionar) | mais simples | contra exatamente o problema mais comum (cota de free tier *esgotada*, não uma falha momentânea) — esperar não ajuda quando o limite é por período, e um turno de RPG não pode ficar preso em retry por minutos | não resolve o caso que mais acontece na prática (free tier) |
| Circuit breaker completo (marcar um modelo como "fora" por N minutos após falha, não tentar de novo até o cooldown) | evita tentar um modelo que sabidamente está de cota estourada | estado teria que ser persistido entre turnos (processo pode reiniciar), e o ganho sobre "só tentar e cair pro próximo" é pequeno na escala de tráfego deste projeto (um jogador) | complexidade não paga pelo volume — reavaliar se isto virar produto com mais de um usuário simultâneo |

## Consequências

**Ganhamos:**
- `chamar_com_fallback` testado com um cliente Groq falso (`tests/test_llm_client.py`) simulando `RateLimitError` esgotando o retry do primeiro modelo e caindo para o segundo — sem rede, sem esperar o backoff de verdade (o teste zera `_chamar_modelo.retry.wait` via `tenacity.wait_none()`).
- Um turno não morre mais por causa de UM modelo estar de cota estourada — testado ao vivo (`Backend/` rodando de verdade) que o modelo primário (`openai/gpt-oss-120b`) segue respondendo turno após turno sem esbarrar em rate limit na sessão de teste desta etapa; o caminho de fallback em si foi validado só pelo teste com cliente falso, não ao vivo (forçar rate limit de verdade exigiria esgotar a cota real, o que não foi feito de propósito).
- `ErroMestre` como exceção de infraestrutura, não de serviço, resolve a violação de camada que existiria se `services/agent_loop.py` precisasse importar de `services/narrator.py` só para pegar um tipo de exceção.

**Pagamos:**
- Um turno que esgota a cadeia inteira (3 modelos, até 2 tentativas cada) pode levar alguns segundos a mais que uma chamada única antes de finalmente falhar — não medido com precisão nesta etapa, mas o pior caso é `3 × 2` chamadas de rede mais o backoff entre elas.
- A cadeia hoje é só modelos Groq: se a própria Groq cair (não um modelo, a infraestrutura inteira), a cadeia inteira falha junto — o "provedor" da promessa do nome do ADR ainda não é redundância de infraestrutura, só de modelo.

**Fica em aberto:**
- Adicionar um segundo provedor real quando/se fizer sentido (chave disponível, ou o projeto crescer além de portfólio pessoal) — a interface já comporta.
- Não existe hoje telemetria de qual modelo da cadeia respondeu cada turno (só logging implícito via exceção). Se o padrão de qual modelo "salva" o turno mais frequentemente for interessante para o relatório da Etapa 6, vale expor isso como métrica.

## Como saber que erramos

Se, na prática, `openai/gpt-oss-20b` ou `qwen/qwen3.6-27b` se mostrarem significativamente piores em tool-call accuracy que o modelo principal (o que os tornaria um fallback pior que simplesmente falhar o turno), trocar a ordem ou os membros da cadeia — a lista em `settings.modelos_fallback` existe justamente para isso ser um ajuste de configuração, não uma mudança de código.

## Referências

- `PLANO_MESTRE.md`, Etapa 4 ("O narrador") — "cadeia de fallback entre provedores (transformando a restrição de free tier em arquitetura)".
- [Groq — Rate limits](https://console.groq.com/docs/rate-limits) — cota por modelo, a restrição que motiva esta decisão.
- [`tenacity`](https://tenacity.readthedocs.io/) — biblioteca de retry usada; único pacote novo desta etapa.
