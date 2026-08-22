# Runbook — Mestre.IA em produção

O que fazer quando o link público (Etapa 9) cair, ficar lento, ou se comportar estranho. Ver também [ADR-0015](adr/0015-hospedagem-fly-vercel-neon.md) para o porquê de cada peça da infraestrutura.

**URLs:**
- Front: `https://mestre-ia-seven.vercel.app`
- API: `https://mestre-ia-backend.fly.dev` (health check em `/health`)
- Banco: Neon (console em [console.neon.tech](https://console.neon.tech))
- Traces: Langfuse Cloud, região US ([us.cloud.langfuse.com](https://us.cloud.langfuse.com))

---

## 1. "O site está fora do ar"

1. **`curl https://mestre-ia-backend.fly.dev/health`** — se não responder `{"status":"ok"}`, o problema é o backend (seção 3). Se responder, o problema é o front ou o proxy (seção 2).
2. **Cold start é normal, não é queda.** `fly.toml` tem `min_machines_running = 0` — a máquina desliga sozinha depois de um tempo sem tráfego (custo zero) e demora alguns segundos para subir de novo no próximo pedido. Se o `/health` responde depois de uma espera curta, não é incidente.
3. Se `/health` continuar falhando depois de ~30s: `fly status` (backend) — ver seção 3.

## 2. Front carrega mas login/jogo não funciona

- `GET https://mestre-ia-seven.vercel.app/api/health` deveria devolver o mesmo `{"status":"ok"}` do backend — se não devolver, o **proxy** (`Frontend/vercel.json`, `rewrites` de `/api/*`) é o problema, não o backend em si. Confirmar que o `vercel.json` ainda aponta para o hostname certo do Fly.io (o app pode ter sido recriado com outro nome).
- Login "funciona" (200, cookie na resposta) mas a próxima chamada volta 401: sintoma clássico de cookie cross-site quebrado — ver Lição 10. Confirmar que o front está mesmo passando pelo proxy (`/api/...`), não chamando o Fly.io direto (`VITE_API_URL` errado num build novo).
- Erro de CORS no console do navegador: `CORS_ORIGINS` no Fly.io não bate com a URL real da Vercel (ex.: a Vercel gerou um domínio novo). `fly secrets set CORS_ORIGINS=https://<url-da-vercel>` (string simples, sem colchetes — ver ADR-0015 sobre por que não é mais `list[str]`).

## 3. Backend não sobe / crash loop

`fly logs` — a causa quase sempre aparece nas primeiras linhas do log de boot:

- **`SettingsError` na inicialização** — uma variável de ambiente malformada (o `CORS_ORIGINS` em JSON quebrado já aconteceu uma vez, ver ADR-0015). Conferir `fly secrets list` e os valores com `fly ssh console` + `echo $NOME_DA_VAR` se necessário.
- **`RuntimeError: SESSION_SECRET ainda é o valor de desenvolvimento`** — alguém rodou `fly deploy` sem o secret `SESSION_SECRET` configurado (ou ele foi removido). `fly secrets set SESSION_SECRET=$(python -c "import secrets; print(secrets.token_hex(32))")`.
- **Falha na migration (`alembic upgrade head`, que roda no `CMD` do `Dockerfile` antes do `uvicorn` subir)** — o log mostra o traceback do Alembic. Checar `DATABASE_URL` (secret) e o status do projeto no console do Neon (pode estar em *sleep*, hibernação do free tier — o primeiro pedido acorda, mas pode demorar).

**Rollback:** `fly releases` lista os deploys anteriores; `fly deploy --image <referência da imagem anterior>` volta para uma versão que já funcionava. Mais simples ainda para reverter só código (sem mudança de schema): `git revert` do commit problemático e `fly deploy` de novo.

## 4. O jogo responde, mas a narração falha ou demora muito

- **"O mestre está sem acesso à IA"** — `GROQ_API_KEY` não configurada ou inválida. `fly secrets set GROQ_API_KEY=...`.
- **"A cota de uso da IA acabou por agora"** — a cadeia de fallback (ADR-0008) já tentou os modelos configurados e todos estouraram cota. Isso é esperado acontecer eventualmente (a chave é compartilhada entre todos os jogadores, ver §7 do `PLANO_MESTRE.md`) — não é bug, é o free tier da Groq. Se virar frequente, é o sinal de que dá para cobrar uma decisão real (ver a regra de dinheiro, seção 6).
- **429 do próprio backend** (`Retry-After` na resposta) — rate limit (`app/infra/rate_limit.py`) protegendo `/chat`/`/chat/stream` (20/min) ou `/auth/login`/`/auth/registrar` (10/min) **por IP**. Um jogador legítimo raramente bate nisso; se um IP achar isso injusto com frequência, é sinal de olhar os logs para força bruta/abuso antes de simplesmente afrouxar o limite.
- **Turno muito lento sem erro nenhum** — checar o Langfuse (trace "turno", nome "groq-chat"/"groq-chat-stream") para latência real por chamada; a Groq eventualmente tem picos de latência fora do controle deste projeto.

## 5. Onde olhar cada coisa

| O quê | Onde |
|---|---|
| Logs do backend | `fly logs` (ou dashboard em `fly.io/apps/mestre-ia-backend/monitoring`) |
| Status das máquinas | `fly status` |
| Secrets configurados (nomes, não valores) | `fly secrets list` |
| Banco (schema, linhas, queries) | Console do Neon, ou `psql`/script com `DATABASE_URL` |
| Custo/latência/tokens por turno | Langfuse — trace `turno`, filtrar por `metadata.personagem_id` |
| Sessões, turnos, retenção D1/D7, abandono | `uv run python scripts/telemetria_resumo.py` (aponta pro `DATABASE_URL` do ambiente, ou passe outro na frente do comando) |
| Deploys anteriores / rollback | `fly releases` |
| Build/deploy do front | Dashboard da Vercel, projeto `grupoprumo/mestre-ia` |

## 6. A regra de decisão sobre dinheiro

Escrita **antes** do lançamento, para não decidir na emoção (`PLANO_MESTRE.md`, §Etapa 9):

> Investir dinheiro apenas se, após 30 dias no ar: **(a)** a retenção D7 passar de X%, **ou** **(b)** o gargalo de qualidade for comprovadamente o modelo — e não o prompt, a memória ou o motor de regras.

Nenhuma decisão de upgrade (máquina paga no Fly.io, domínio próprio, modelo mais caro na Groq) deveria acontecer fora desse crivo, mesmo sob a tentação de "só custa uns trocados". `scripts/telemetria_resumo.py` é a fonte do lado (a) desta regra.
