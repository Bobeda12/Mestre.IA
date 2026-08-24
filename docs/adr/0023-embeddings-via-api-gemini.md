# ADR-0023 — Embeddings via API (Gemini) em vez de modelo local (`fastembed`)

**Data:** 24/08/2026
**Status:** Aceito
**Etapa:** 14
**Supersede:** —

---

## Contexto

O ADR-0022 troca a hospedagem do backend de Fly.io para Render.com porque o Fly.io deixou de ter free tier sem cartão. O Render tem — mas com um teto que o Fly.io não tinha: **512 MB de RAM** no plano free (contra 1 GB no Fly.io), e **0,1 vCPU**.

Medindo o processo web deste projeto localmente (`app/infra/embeddings.py`, antes desta mudança, com o venv real do `Backend/`): Python puro fica em ~19 MB; com FastAPI/SQLAlchemy/psycopg/Groq/Langfuse carregados, ~91 MB; importar `fastembed`, ~121 MB; **carregar o modelo de embedding** (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, via ONNX Runtime), **639 MB**; depois de um embed de verdade, pico de **656 MB**. O arquivo do modelo em disco tem 225 MB (`fastembed_cache/.../model_optimized.onnx`) — o ONNX Runtime infla isso para ~520 MB em memória.

O `lifespan` do FastAPI (`app/main.py`, desde a Etapa 10/A-6) carregava esse modelo **no boot**, antes de servir o primeiro pedido — no Render free, isso estoura os 512 MB e o container morre por OOM antes de responder `/health`. Mesmo que coubesse, os 0,1 vCPU tornariam os ~60ms por embed (medidos localmente) e os ~2s de carregamento do modelo desproporcionalmente lentos: dois embeds por turno (busca de memória + `registrar_evento`, `services/memory.py`) mais o boot, competindo por um décimo de núcleo.

`docs/backlog-pos-lancamento.md` (Família 1, item "boot da máquina") já registrava a preocupação simétrica no Fly.io — o modelo rodando num vCPU compartilhado era lento, mesmo com RAM sobrando; aqui o problema virou binário: nem cabe.

## Decisão

`app/infra/embeddings.py` chama a API do Gemini (`gemini-embedding-001`, REST puro via `httpx`) em vez de carregar um modelo local. Mesma interface pública (`embed`, `embed_um`) — nenhum consumidor (`services/hybrid_search.py`, `services/memory.py`, `services/rag_regras.py`) muda, porque todos já recebiam `embed_fn` como parâmetro injetável (o mesmo padrão que já servia os testes).

`outputDimensionality=768` (um dos três valores recomendados pela doc da API — 768/1536/3072 — o dobro da dimensão do modelo local anterior, ainda pequeno para guardar como JSON). REST direto ao endpoint nativo (`:embedContent`), não o SDK `openai`/`google-genai` nem a camada de compatibilidade OpenAI do Gemini: esta última não documenta com clareza o suporte a `outputDimensionality`, enquanto o endpoint nativo documenta o contrato exato (`embedContentConfig.outputDimensionality`), sem ambiguidade — importava ter certeza da forma da chamada sem precisar testar contra os dois formatos.

Falha (sem chave, rate limit, timeout, erro do servidor) nunca derruba o turno: `embed()` degrada para um vetor de zeros por texto que falhou, que `hybrid_search._cosseno` já trata como "sem similaridade" (norma zero) — o documento afetado continua recuperável por busca léxica (BM25), só perde o sinal denso. O `lifespan` do FastAPI perdeu a etapa de preload (não há mais nada para carregar no boot); o `Dockerfile` perdeu o `RUN` que baixava o modelo em build time.

Dimensão nova (768) é incompatível com a antiga (384) — `hybrid_search._cosseno` ganhou uma guarda explícita (`len(a) != len(b)` → `0.0`, mesma degradação de "falha") em vez de deixar o `zip(..., strict=True)` levantar `ValueError` contra eventos gravados antes desta mudança. `scripts/reembed_eventos.py` (novo) reprocessa os eventos antigos com o provedor atual, para quem quiser restaurar o sinal denso neles — não é obrigatório rodar, o jogo funciona sem.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Manter `fastembed` local, aceitar o Render pago (Starter, 512 MB → não ajuda; precisaria do Standard, 2 GB, US$ 25/mês) | zero mudança de código, zero dependência de rede externa | contraria a regra de dinheiro do §Etapa 9 (só investir depois de dado real de uso); US$ 25/mês é caro para um projeto de portfólio sem tráfego | a regra de dinheiro já decide isto — não há dado nenhum ainda que justifique pagar |
| Modelo local quantizado (INT8) menor, tentando caber em 512 MB | ainda sem rede externa | não testado — mesmo cortando pela metade, ~260-300 MB de runtime ONNX + o resto do processo (FastAPI/SQLAlchemy/psycopg) já passa de 512 MB sozinho (91 MB medidos); a folga que sobraria seria mínima, arriscando o mesmo problema de novo na próxima dependência adicionada | risco alto por uma economia pequena — API resolve com folga de sobra (3× nos 512 MB) |
| Jina AI embeddings (multilíngue, sem cartão) em vez de Gemini | também sem cartão, também multilíngue | free tier é 1M tokens **uma vez**, não renovável — vira um teto que acaba e não volta, ao contrário do Gemini (cota diária) | pior ajuste para um serviço que roda indefinidamente, não um teste único |
| SDK `openai`/`google-genai` contra a camada de compatibilidade OpenAI do Gemini (`/v1/embeddings`), em vez de REST puro | um cliente só (o mesmo já usado para chat, ver ADR-0024) para tudo, menos código | doc não confirma com clareza o suporte a `outputDimensionality` nessa camada — arriscar adivinhar a forma certa da chamada numa parte crítica (a dimensão do vetor precisa bater em toda comparação de cosseno) | o endpoint nativo documenta o contrato exato; `httpx` já é dependência do projeto, não é peso extra |

## Consequências

**Ganhamos:**
- RSS do processo web cai de ~656 MB (pico, com o modelo local carregado) para a faixa de ~150 MB — folga de ~3× nos 512 MB do Render free, em vez de estourar.
- Imagem Docker menor: sem `fastembed`/`onnxruntime`/`huggingface-hub` (17 pacotes a menos no lockfile) e sem os 225 MB do modelo baixados em build time.
- Boot mais rápido: nenhum modelo para carregar antes do primeiro pedido — o `lifespan` do FastAPI (`app/main.py`) deixou de existir.
- `hybrid_search._cosseno` ganhou uma degradação explícita para dimensão incompatível, um caso real (a própria migração desta ADR) que antes quebraria com `ValueError`.

**Pagamos:**
- Latência de rede por embed (~150-300ms não medidos ao vivo ainda, ver "Como saber que erramos") onde antes era leitura de disco — parcialmente escondida dentro de um turno que já espera o LLM, mas soma para as duas chamadas síncronas por turno que `docs/backlog-pos-lancamento.md` já apontava como Família 2 do custo por turno.
- Mais um provedor externo vendo o texto do jogador (a query e os eventos de memória passam pela API do Gemini) — o free tier do Google pode usar dados de entrada para treino; não investigado a fundo nesta etapa.
- Falha da API do Gemini agora é uma dependência externa nova no caminho crítico de memória/RAG — mitigada pela degradação para BM25, mas ainda um novo modo de falha que não existia com o modelo local (que só falhava se a máquina não tivesse RAM/disco, algo já resolvido pelo build time).
- Eventos gravados antes desta mudança (384 dim) perdem o sinal denso até alguém rodar `scripts/reembed_eventos.py` contra o banco de produção — não rodado ainda (precisa do `DATABASE_URL` do Neon, fora do alcance desta sessão).

**Testado ao vivo** (chave real configurada em `.env`, não só mock): `embed_um` devolve 768 dimensões, norma 1.0, cosseno entre o mesmo texto duas vezes = 1.0, entre textos diferentes < 1.0 — comportamento correto. `scripts/memory_recall.py` (17 eventos fixos, 6 consultas) contra a API real: recall@1 denso-apenas 67%, híbrido 83% — mesmo padrão que o ADR-0010 já documentava (léxico resgata o que o denso perde), confirmando que a troca de provedor não mudou a característica da busca.

**Achado ao vivo, só apareceu testando contra a API de verdade:** a forma "moderna" documentada (`embedContentConfig: {taskType, outputDimensionality}`, aninhada) é aceita pela API — devolve `200 OK` — mas é **silenciosamente ignorada**: toda chamada voltava com 3072 dimensões, nunca as 768 pedidas, sem nenhum erro ou aviso no corpo da resposta que denunciasse isso. A forma "deprecada" (os mesmos dois campos soltos no topo do corpo, fora de qualquer bloco aninhado) é a que a API realmente respeita hoje. O código usa a forma deprecada, documentado inline em `_chamar_api`. Sem testar ao vivo, isto teria ido para produção quieto: nenhum teste teria pegado, porque o formato errado não falha — só devolve um vetor certo, só do tamanho errado, o que ainda "funciona" (cosseno calcula normal) até alguém notar o custo de armazenamento 4× maior ou comparar contra um vetor de 768 gravado por outro caminho.

**Fica em aberto:**
- Rodar `scripts/reembed_eventos.py` contra o banco de produção (Neon), para restaurar o sinal denso nos eventos de memória gravados antes desta mudança.
- Gemini recomenda `taskType` diferente para indexar (`RETRIEVAL_DOCUMENT`) e para consultar (`RETRIEVAL_QUERY`) — esta troca usa `RETRIEVAL_DOCUMENT` para os dois, mesma simplificação que o modelo local anterior já tinha (nenhuma assimetria entre indexar e consultar). Ganho de qualidade não medido; mudar exigiria `embed_fn` carregar um segundo parâmetro em todo call site (`hybrid_search.buscar`, `memory.memorias_relevantes`, `rag_regras.regras_relevantes`), escopo maior que o desta etapa.

## Como saber que erramos

Se a latência por turno (Langfuse, `medir`/spans de `embedding`) subir de forma visível depois de configurar o Gemini em produção — o custo de rede que hoje é uma hipótese, não uma medição — vale considerar cachear embeddings de texto repetido, ou paralelizar os dois embeds síncronos do turno (busca + `registrar_evento`) em vez de serializá-los.

Se o rate limit do free tier do Gemini (~100 req/min, ~1000 req/dia por conta) virar gargalo real de uso — dois embeds por turno, então ~500 turnos/dia de teto — é o sinal concreto para considerar cache ou um segundo provedor de embeddings, não antes.

## Referências

- [Gemini API — Embeddings](https://ai.google.dev/gemini-api/docs/embeddings) — o modelo, `outputDimensionality`, a exigência de normalização manual para dimensão truncada.
- [Gemini API — Embeddings, referência REST](https://ai.google.dev/api/embeddings) — a forma exata do request/response (`embedContentConfig`, `{"embedding": {"values": [...]}}`).
- [Render — Free instance types](https://render.com/docs/free) — 512 MB / 0,1 CPU, o teto que motivou esta troca.
- ADR-0022 — a migração de hospedagem que expôs este limite.
- ADR-0010 — por que busca híbrida (BM25 + densa) em vez de vetor puro; a degradação para BM25 desta ADR se apoia nessa decisão anterior.
- `docs/backlog-pos-lancamento.md`, Família 1 ("o boot da máquina") — o mesmo modelo local já era apontado como fonte de lentidão no Fly.io, antes de virar um limite rígido no Render.
