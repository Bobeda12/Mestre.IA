# Relatório de latência 0003 — Etapa 10 (A-6)

**Data:** 22/08/2026 · **Motivação:** relato do autor de que o jogo "ficou mais lento depois do deploy" — o item mais caro do backlog pós-lançamento (10h estimadas, a maior parte dele em achar a causa, não em corrigir).

**Regra seguida:** medir antes de mexer. As duas famílias suspeitas eram bem diferentes — o boot da máquina (só aparece em produção, no Fly.io) e o custo por turno (aparece em qualquer lugar, cresce com a sessão) — e cada uma pedia um jeito diferente de provar.

## 1. Família 1 — o boot da máquina

Não dá para medir isto em `localhost` (a máquina de dev nunca desliga). A prova aqui é de código, verificada com `docker build`/`docker run` de verdade, não com números de produção — um deploy real fica para quando o autor aprovar, à parte desta sessão.

| # | Correção | Evidência |
|---|---|---|
| 1 | Modelo de embedding baixado em **build time**, carregado no **boot** (`lifespan`), não mais no primeiro pedido de um jogador | `docker build`: download do modelo aconteceu no `Step 7/9` (build), ~15s, uma vez por imagem. `docker run`: log do boot mostra `Carregando modelo de embeddings no boot...` → `Modelo de embeddings carregado.` em **~1,1s**, sem nenhuma linha de download — confirma que leu do cache, não baixou de novo. `/health` respondeu em 53ms logo depois do boot completar. |
| 2 | `alembic upgrade head` saiu do `CMD` do Dockerfile, virou `release_command` em `fly.toml` | Log do `docker run` não tem nenhuma menção a `alembic`/`migration` — confirma que não roda mais a cada boot de máquina, só uma vez por deploy (via o mecanismo do próprio Fly, não testável localmente). |

**Achado ao lado, não estava no plano:** o diretório de cache do modelo (`app/infra/embeddings.py:CACHE_DIR`) precisou ficar dentro de `/app` (não `/tmp`, o default do fastembed) — alguns runtimes de container montam um tmpfs por cima de `/tmp`, o que apagaria o cache baixado em build time antes do container sequer subir. E precisou ser `fastembed_cache`, sem ponto na frente — `.fastembed_cache` falhava ao criar a pasta pela primeira vez no Windows local (achado ao vivo, ver seção 4).

## 2. Família 2 — custo por turno

Medido com turnos reais contra a Groq (não mockados), via `TestClient` local — 5 turnos de uma sessão nova, ação curta ("Eu observo...", "Eu pergunto...", etc.), instrumentados com `app.infra.tracing.medir()` (novo — loga `fase`, `duracao_ms` sempre, não só com Langfuse configurado).

| Fase | n | Valores (ms) | p50 | p95 |
|---|---|---|---|---|
| `memoria` (`memory.memorias_relevantes`) | 5 | 5.5 / 58.4 / 58.8 / 60.4 / 61.0 | **58.8ms** | **61.0ms** |
| `agente` (laço de tool calling, `executar_turno`) | 5 | 1781 / 2032 / 2179 / 2470 / 5957 | **2179ms** | **5957ms** |

**Leitura honesta:**

- O laço do agente **domina o turno de longe** (segundos, contra dezenas de milissegundos da memória) — é a chamada de verdade à Groq, com possivelmente mais de uma ida e volta por ferramenta chamada (ADR-0007). Isso não é o que a Etapa 10 tentou corrigir (é o "custo de estar chamando um LLM", não uma ineficiência do projeto), mas explica por que o turno nunca vai ser instantâneo mesmo com tudo mais otimizado.
- `memoria` estabilizou em ~59ms depois do primeiro turno — o teto de eventos (`limite_eventos_memoria=200`, correção #3) está fazendo o trabalho: a query não cresce com o tamanho da sessão. **Amostra pequena de propósito** (5 turnos, sessão nova) — o ganho real do teto só aparece de verdade numa sessão *longa* (centenas de eventos), que é exatamente o cenário que o motivou; um teste dedicado (`tests/test_memory.py::test_query_nao_traz_mais_eventos_que_o_teto`) prova o comportamento com 10 eventos e teto artificialmente baixo (3), sem precisar gerar uma sessão longa de verdade só para medir.
- **Lacuna conhecida desta medição:** `rag_regras.regras_relevantes` (RAG sobre a bíblia) também chama `embed_fn` e não ficou dentro de nenhuma fase nomeada — o custo dela está diluído em algum lugar entre `memoria` e `agente` nesta rodada. Não invalida os números acima (a ordem de grandeza — memória em dezenas de ms, agente em segundos — está clara), mas uma medição futura deveria nomear essa fase também.
- Escrita de memória (`registrar_evento`/`atualizar_resumo_rolante`, correção #4) **não aparece nesta tabela de propósito** — ela saiu do caminho crítico (roda depois da resposta, via `BackgroundTasks`/`background=`), então não é mais latência que o jogador paga. Ainda vale monitorar a duração dela em produção (fica em background, não em best-effort — uma falha ali não derruba o turno, mas merece log próprio numa etapa futura).

## 3. Ordem de ataque (a que foi seguida)

1. Embeddings na imagem + boot — ✅ código e Dockerfile, verificado com build real.
2. `alembic` fora do boot — ✅ config, verificado com build real.
3. Limitar eventos de memória por turno — ✅ código + teste dedicado + medição real (memória estável).
4. Escrita de memória fora do caminho crítico — ✅ código + suíte inteira (268 testes) confirma que o turno persiste certo mesmo com a escrita adiada.
5. `min_machines_running = 1` — **não decidido nesta etapa**, custa dinheiro por mês; fica para depois de ver o quanto os passos 1–4 já resolveram em produção.

## 4. Achado que não estava no escopo, mas atrasou a etapa: Docker Desktop e Acesso Controlado a Pastas

Vale registrar porque pode voltar a acontecer: o Docker Desktop desta máquina começou a falhar no boot com `"The file cannot be accessed by the system"` ao criar sockets internos (`dockerInference`, `docker-secrets-engine`, `userAnalyticsOtlpHttp`) — sintoma clássico do **Acesso Controlado a Pastas** (Windows Defender) bloqueando o Docker de mexer em `AppData\Local\Docker`. Resolvido permitindo o Docker Desktop na lista de apps confiáveis.

**Efeito colateral, não previsto:** depois desse ajuste, o `python.exe` do venv (não o Docker) passou a ser bloqueado de **criar pastas/arquivos novos** dentro do projeto (que vive em `OneDrive\Documentos\...`, também protegido por padrão) — `ruff` (cache), `pytest` (cache) e `fastembed` (cache do modelo) todos falharam com o mesmo padrão até rodarem com cache desligado ou apontando para fora da pasta protegida. **Se isso continuar incomodando no dia a dia, vale adicionar `python.exe`/`uv.exe` à mesma lista de apps permitidos do Docker Desktop** — não fiz essa mudança porque é configuração de segurança, fora do que devo alterar sozinho.

## 5. O que ainda falta

- **Deploy real e números de produção** — o autor ainda não aprovou um deploy nesta sessão; os números da seção 1 são evidência de código (build+boot locais via Docker), não p50/p95 de produção de verdade. Quando o deploy acontecer, vale repetir a medição da seção 2 contra o Fly.io — ali entra a rede real (Neon em vez de SQLite local), que é onde a correção #3 (teto de eventos) tende a importar mais.
- `min_machines_running = 1` — decisão separada, ainda em aberto.
