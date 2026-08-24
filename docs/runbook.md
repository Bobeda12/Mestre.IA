# Runbook — Mestre.IA em produção

O que fazer quando o link público (Etapa 9) cair, ficar lento, ou se comportar estranho. Ver também [ADR-0022](adr/0022-hospedagem-render-em-vez-de-fly-io.md) (Render.com, hospedagem atual) e [ADR-0015](adr/0015-hospedagem-fly-vercel-neon.md) (o raciocínio original de proxy/`SameSite`, que continua valendo) para o porquê de cada peça da infraestrutura.

**URLs:**
- Front: `https://mestre-ia-seven.vercel.app`
- API: `https://mestre-ia-backend.onrender.com` (health check em `/health`)
- Banco: Neon (console em [console.neon.tech](https://console.neon.tech))
- Traces: Langfuse Cloud, região US ([us.cloud.langfuse.com](https://us.cloud.langfuse.com))
- Deploys/logs do backend: [dashboard.render.com](https://dashboard.render.com) — não há CLI equivalente ao `fly` neste projeto; tudo é pelo dashboard.

---

## 1. "O site está fora do ar"

1. **`curl https://mestre-ia-backend.onrender.com/health`** — se não responder `{"status":"ok"}`, o problema é o backend (seção 3). Se responder, o problema é o front ou o proxy (seção 2).
2. **Cold start é normal, não é queda.** O plano free do Render hiberna o serviço depois de um tempo sem tráfego (custo zero) e demora alguns segundos a mais de um minuto para subir de novo no próximo pedido. Se o `/health` responde depois de uma espera curta, não é incidente.
3. Se `/health` continuar falhando depois de ~1 min: abrir o dashboard do Render (aba **Logs** do serviço) — ver seção 3.

## 2. Front carrega mas login/jogo não funciona

- `GET https://mestre-ia-seven.vercel.app/api/health` deveria devolver o mesmo `{"status":"ok"}` do backend — se não devolver, o **proxy** (`Frontend/vercel.json`, `rewrites` de `/api/*`) é o problema, não o backend em si. Confirmar que o `vercel.json` ainda aponta para o hostname certo do Render (o serviço pode ter sido recriado com outro nome).
- Login "funciona" (200, cookie na resposta) mas a próxima chamada volta 401: sintoma clássico de cookie cross-site quebrado — ver Lição 10. Confirmar que o front está mesmo passando pelo proxy (`/api/...`), não chamando o Render direto (`VITE_API_URL` errado num build novo).
- Erro de CORS no console do navegador: `CORS_ORIGINS` no Render não bate com a URL real da Vercel (ex.: a Vercel gerou um domínio novo). Editar em dashboard.render.com → serviço → **Environment** (string simples separada por vírgula, sem colchetes — ver ADR-0015 sobre por que não é mais `list[str]`); salvar reinicia o serviço automaticamente.

## 3. Backend não sobe / crash loop

Dashboard do Render → serviço → **Logs** — a causa quase sempre aparece nas primeiras linhas do log de boot:

- **`SettingsError` na inicialização** — uma variável de ambiente malformada (o `CORS_ORIGINS` em JSON quebrado já aconteceu uma vez no Fly.io, ver ADR-0015; o mesmo risco existe aqui). Conferir os valores em **Environment** no dashboard.
- **`RuntimeError: SESSION_SECRET ainda é o valor de desenvolvimento`** — o secret `SESSION_SECRET` não está configurado (ou foi removido). O `render.yaml` gera esse valor automaticamente (`generateValue: true`) só no primeiro deploy do Blueprint — se foi apagado manualmente depois, gerar um novo com `python -c "import secrets; print(secrets.token_hex(32))"` e colar em **Environment**.
- **Falha na migration (`alembic upgrade head`, que roda no `CMD` do `Dockerfile` antes do `uvicorn` subir — a cada boot, não só a cada deploy, ver ADR-0022)** — o log mostra o traceback do Alembic. Checar `DATABASE_URL` (secret) e o status do projeto no console do Neon (pode estar em *sleep*, hibernação do free tier — o primeiro pedido acorda, mas pode demorar).
- **OOM (o processo simplesmente some do log, sem traceback)** — sinal de que algo voltou a carregar peso na memória do processo web (o motivo original de sair do Fly.io/`fastembed` local, ver ADR-0023: o teto aqui é 512 MB). Suspeitar de qualquer dependência nova pesada antes de suspeitar do Render.

**Rollback:** dashboard do Render → serviço → aba **Deploys** → escolher um deploy anterior → **Rollback to this deploy**. Mais simples ainda para reverter só código (sem mudança de schema): `git revert` do commit problemático e `git push` — o Render reimplanta sozinho a cada push em `main` (GitHub App próprio, sem step de CI para isso).

## 4. O jogo responde, mas a narração falha ou demora muito

- **"O mestre está sem acesso à IA... (GROQ_API_KEY ou GEMINI_API_KEY)"** — nenhum provedor da cadeia (`app/infra/llm_client.py`, ADR-0024) está configurado. Conferir as duas chaves em **Environment**.
- **"A cota de uso da IA acabou por agora"** — a cadeia de fallback (ADR-0008, revista pelo ADR-0024) já tentou todos os elos configurados e todos falharam por erro transitório. Desde a Etapa 14 a cadeia atravessa dois provedores (Groq + Gemini) com cotas diárias separadas — se isso vira frequente mesmo assim, é sinal de que dá para cobrar uma decisão real (ver a regra de dinheiro, seção 6), ou de que um elo específico está mal ordenado (ver o Langfuse abaixo).
- **429 do próprio backend** (`Retry-After` na resposta) — rate limit (`app/infra/rate_limit.py`) protegendo `/chat`/`/chat/stream` (20/min) ou `/auth/login`/`/auth/registrar` (10/min) **por IP**. Um jogador legítimo raramente bate nisso; se um IP achar isso injusto com frequência, é sinal de olhar os logs para força bruta/abuso antes de simplesmente afrouxar o limite.
- **Turno muito lento sem erro nenhum** — checar o Langfuse (trace "turno", nome `"{provedor}-chat"`/`"{provedor}-chat-stream"`, ex. `"groq-chat"` ou `"gemini-chat"` — a metadata de cada geração carrega `provedor` desde o ADR-0024, então dá para ver por qual provedor o turno passou) para latência real por chamada.
- **Busca de memória/RAG "esquecendo" coisas óbvias, sem erro nenhum** — checar se `GEMINI_API_KEY` está configurada: sem ela, `app/infra/embeddings.py` (ADR-0023) degrada sozinho para busca só léxica (BM25), sem avisar o jogador — o sintoma é memória pior, não um erro visível.

## 5. Onde olhar cada coisa

| O quê | Onde |
|---|---|
| Logs do backend | Dashboard do Render → serviço → **Logs** |
| Status/histórico de deploys | Dashboard do Render → serviço → **Deploys** |
| Variáveis de ambiente / secrets (nomes e valores) | Dashboard do Render → serviço → **Environment** |
| Banco (schema, linhas, queries) | Console do Neon, ou `psql`/script com `DATABASE_URL` |
| Custo/latência/tokens por turno, por provedor | Langfuse — trace `turno`, filtrar por `metadata.personagem_id` ou `metadata.provedor` |
| Sessões, turnos, retenção D1/D7, abandono | `uv run python scripts/telemetria_resumo.py` (aponta pro `DATABASE_URL` do ambiente, ou passe outro na frente do comando) |
| Build/deploy do front | Dashboard da Vercel, projeto `grupoprumo/mestre-ia` |
| Secrets do GitHub Actions (job `avaliacao`) | GitHub → Settings → Secrets and variables → Actions (`GROQ_API_KEY`, `GEMINI_API_KEY`) |

## 6. A regra de decisão sobre dinheiro

Escrita **antes** do lançamento, para não decidir na emoção (`PLANO_MESTRE.md`, §Etapa 9):

> Investir dinheiro apenas se, após 30 dias no ar: **(a)** a retenção D7 passar de X%, **ou** **(b)** o gargalo de qualidade for comprovadamente o modelo — e não o prompt, a memória ou o motor de regras.

Nenhuma decisão de upgrade (instância paga no Render, domínio próprio, modelo mais caro) deveria acontecer fora desse crivo, mesmo sob a tentação de "só custa uns trocados". `scripts/telemetria_resumo.py` é a fonte do lado (a) desta regra.
