# ADR-0011 — Estratégia de avaliação: determinístico + julgado, gate manual

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 6
**Supersede:** —

---

## Contexto

Desde a Etapa 0, toda mudança de prompt, de descrição de ferramenta ou de política de memória foi validada "no escuro" — rodando o jogo à mão e olhando se pareceu melhor. `services/guardrail.py` já nomeia essa lacuna no próprio docstring desde a Etapa 4: *"não é um LLM-as-judge (isso é a Etapa 6)"*. E dois scripts fora de `tests/` (`scripts/tool_call_accuracy.py`, Etapa 4; `scripts/memory_recall.py`, Etapa 5) já são protótipos do padrão "cenário fixo → resultado esperado → métrica agregada" — só que com os cenários embutidos em Python, sem dataset versionado nem gate de CI.

O problema concreto: não existe like nenhum jeito de responder "essa mudança de prompt melhorou ou piorou o sistema?" com um número. É a pergunta que mais derruba candidato a LLM Engineer em entrevista, e o projeto não tinha ferramenta nenhuma para respondê-la.

## Decisão

Um framework de avaliação em `Backend/evals/` com quatro peças, cada uma resolvendo uma parte diferente do problema:

1. **Golden dataset** — 60 cenários versionados em YAML (`evals/golden/*.yaml`), 10 por categoria (combate, regra ambígua, ação impossível, memória de longo prazo, injeção de prompt, caso-limite), validados por um schema Pydantic (`evals/schema.py`).
2. **Harness** (`evals/harness.py`) que roda cada cenário pelo **caminho de produção real** — `narrator.montar_contexto` + `agent_loop.executar_turno` + `tools.ToolExecutor` + `guardrail.validar_narrativa` — em vez de uma simulação paralela que poderia divergir do sistema de verdade sem ninguém notar.
3. **Métricas determinísticas** (`evals/metrics.py`, sem LLM): taxa de ferramenta válida, tool-call accuracy (ferramenta certa / ferramenta+args certos), taxa de violação de estado (reusa o guardrail existente), latência p50/p95, tokens de prompt/completion.
4. **LLM-as-judge** (`evals/judge.py`): uma segunda chamada, depois da narrativa já pronta, pontuando 1-5 em 4 eixos (aderência às regras, consistência com a memória, qualidade sensorial, ausência de alucinação de inventário), com uma rubrica fixa em texto.

O gate de CI (`avaliacao`, `.github/workflows/ci.yml`) é **manual** (`workflow_dispatch`), não roda em todo PR/push — ver seção de alternativas.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Simular o turno sem passar pelo `agent_loop`/`ToolExecutor` reais (harness próprio, "leve") | mais rápido de escrever, sem depender de `app.services` | pode divergir do comportamento de produção sem ninguém notar — exatamente o tipo de "teste que passa, produção que quebra" que o projeto já tentou evitar desde a Etapa 0 | avaliação que não testa o caminho real não prova nada sobre o sistema real |
| Gate de CI automático em todo PR, chamando a Groq de verdade | mais parecido com "CI de verdade"; pega regressão antes do merge sem depender de alguém lembrar de rodar manualmente | a chave da Groq é **compartilhada com os jogadores** (`ROADMAP_PORTFOLIO.md` já alerta sobre isso); rodar 60 cenários × múltiplas chamadas a cada push/PR queima a cota rápido — é o oposto do que o próprio roadmap recomenda antes do lançamento público | preservar a cota compartilhada pesa mais que ter o gate automático agora; o gate manual ainda cumpre o critério de pronto ("existe um PR que o CI reprovou por queda de qualidade") sem esse custo |
| Um segundo provedor/modelo de família diferente como juiz (ex: Gemini) | juiz e narrador vindo de famílias diferentes reduz o risco de viés correlacionado (o juiz "gostar" do estilo do próprio narrador) | integrar um segundo provedor é escopo novo, reabre a discussão do ADR-0008 ("por que não um segundo provedor ainda"), e não estava no plano desta etapa | fica registrado como limitação conhecida (ver Consequências), não escondido — reavaliar se a Etapa 9 trouxer um segundo provedor por outro motivo |
| Calibrar o juiz com anotação gerada por outro LLM, chamando isso de "anotação humana" | mais rápido, não depende de ninguém sentar e anotar 30 exemplos | seria simplesmente falso — o projeto inteiro é construído sobre documentar o que de fato aconteceu, não o que seria conveniente ter acontecido | a ferramenta de anotação (`evals/annotate.py`) está pronta; a anotação de verdade fica pendente, documentada como tal (ver Fica em aberto) |

## Consequências

**Ganhamos:**
- Uma pergunta que antes não tinha resposta ("essa mudança melhorou?") agora tem um comando: `uv run python -m evals.run_eval`.
- O harness roda o caminho real de produção — um bug de integração entre `montar_contexto`/`agent_loop`/`ToolExecutor` apareceria na suíte de avaliação, não só nos testes unitários que mockam cada peça isoladamente.
- `tool_call_accuracy` deixa de viver só em `scripts/tool_call_accuracy.py` (10 cenários hardcoded) e passa a cobrir 60 cenários versionados, com histórico em git.
- O bake-off (`--bake-off`) reusa `chamar_modelo_unico` generalizado (agora aceita `tools=`/`tool_choice=`, Etapa 6) para medir qualidade×latência×tokens por modelo — fecha o ciclo do ADR-0008 com dado real em vez de intuição.

**Pagamos:**
- O juiz por padrão usa o **mesmo modelo mais forte** da cadeia de fallback do narrador (`settings.model_name`) — não há separação de família entre "quem narra" e "quem julga". Um juiz tendencioso a favor do próprio estilo é um risco conhecido de LLM-as-judge; sem calibração humana real (ver abaixo), não dá para quantificar o quanto isso pesa aqui ainda.
- O harness **não replica 100% de `routers/game.py`** — falta a persistência em banco (deliberado: cenários não devem depender de estado de banco) e o desvio especial para `heroi.hp_atual <= 0` (que troca para um prompt sem ferramentas). O cenário `caso_hp_zero_via_caminho_normal` existe justamente para deixar essa lacuna visível, não para escondê-la.
- A pontuação agregada usada pelo gate de CI (`evals/run_eval.py::pontuacao_agregada`) é uma média ponderada com pesos escolhidos por julgamento de engenharia (40% juiz, 25% tool-call, 15% ferramenta válida, 15% sem violação de estado, 5% sem erro de execução), não derivada de um experimento — é um ponto de partida razoável, não uma fórmula validada.

**Fica em aberto:**
- **A calibração humana×juiz não foi feita nesta rodada.** `evals/annotate.py` está pronto (CLI que mostra cenário + narrativa e pede 4 notas por teclado, grava em `evals/annotations/humanas.yaml`) e `evals/calibracao.py` calcula weighted Cohen's kappa por eixo — mas os ~30 exemplos anotados por uma pessoa de verdade (não o autor deste harness) ainda não existem. `evals/annotations/humanas.yaml` só tem um piloto pequeno, marcado `anotador: "piloto-ia"`, que `calibracao.py` **explicitamente ignora** ao calcular concordância — existe só para provar que o formato funciona ponta a ponta. Enquanto isso não acontecer, a confiabilidade do juiz é uma suposição, não um número medido.
- O secret `GROQ_API_KEY` do job `avaliacao` no GitHub Actions precisa ser configurado manualmente (Settings → Secrets do repositório) — fora do alcance deste ADR/código.
- Não existe conversão de tokens para custo em R$/US$ no relatório — não há uma tabela de preço da Groq confiável o bastante para publicar; `evals/metrics.py::tokens_totais` mede só tokens.

## Como saber que erramos

Se, depois de calibrar o juiz contra anotação humana real, o kappa por eixo ficar sistematicamente baixo (ex: <0.4, "fraca" na escala usual de interpretação de Cohen's kappa) — o juiz não está medindo o que um humano mediria, e a pontuação agregada do gate de CI está confiando demais num sinal ruim. Nesse caso, os próximos passos são: revisar a rubrica (pode estar ambígua o bastante para o próprio juiz variar), ou trazer um segundo provedor como juiz (reabrindo a discussão do ADR-0008), antes de continuar usando a pontuação do juiz como parte do gate.

## Referências

- `PLANO_MESTRE.md`, Etapa 6 ("Como sei que melhorou?") — a especificação original.
- [ADR-0006](0006-llm-nao-e-motor-de-regras.md) — por que o motor de regras nunca é o LLM; a mesma separação é o que torna a maioria dos cenários de `injecao_prompt` estruturalmente seguros, mesmo sem o juiz.
- [ADR-0008](0008-cadeia-de-fallback-de-modelo.md) — por que só a Groq, ainda; o bake-off desta etapa mede exatamente a pergunta que motivou aquele ADR.
- Cohen, J. (1968) — *Weighted kappa: Nominal scale agreement with provision for scaled disagreement or partial credit* — a métrica usada em `evals/calibracao.py`.
