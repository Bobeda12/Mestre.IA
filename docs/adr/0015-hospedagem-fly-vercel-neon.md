# ADR-0015 — Hospedagem: Fly.io (backend) + Vercel (front) + Neon (Postgres), com proxy em vez de CORS cross-site

**Data:** 22/08/2026
**Status:** Aceito
**Etapa:** 9
**Supersede:** —

---

## Contexto

Etapas 0–8 rodam só em `localhost`. A Etapa 9 promete um link público — `PLANO_MESTRE.md` já apontava a direção (`ROADMAP_PORTFOLIO.md`: "back no Fly.io ou HF Spaces, front na Vercel/Cloudflare Pages, Postgres no Neon"), com uma restrição dura: **free tier**, porque o lançamento público é o próprio gatilho para decidir se vale investir dinheiro (§Etapa 9, "a regra de decisão sobre dinheiro").

O deploy expôs um problema de arquitetura que não existia em `localhost`: até a Etapa 8, front e back sempre foram o **mesmo site** do ponto de vista do navegador (mesmo hostname, portas diferentes — ver Lição 09, o bug de `localhost` × `127.0.0.1`). Em produção, `*.vercel.app` e `*.fly.dev` são domínios **de verdade** diferentes, e o cookie de sessão (`SameSite=Lax`, sem `Secure`) simplesmente não sobrevive a uma chamada `fetch`/`axios` cross-site. Essa questão não estava resolvida no plano original — apareceu só ao verificar o código antes de começar a implementar.

## Decisão

**Fly.io** hospeda o backend (Docker, o `Dockerfile` já existente desde antes da Etapa 9), **Vercel** hospeda o front (build estático do Vite), **Neon** hospeda o Postgres. E — a parte que não estava no plano — **a Vercel faz proxy de `/api/*` para o Fly.io** (`Frontend/vercel.json`, `rewrites`), em vez do front chamar `https://mestre-ia-backend.fly.dev` direto.

Com o proxy, o navegador só enxerga a origem da Vercel — front e API viram a mesma origem do ponto de vista do `SameSite`, o cookie de sessão continua `httpOnly` + `SameSite=Lax` sem nenhuma mudança em `services/auth.py`/`routers/auth.py`, e evita a categoria inteira de problema de cookie de terceiro em vez de só contornar o sintoma (ver "Alternativas consideradas").

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Front chama o Fly.io direto + `SameSite=None; Secure` no cookie | mais simples de montar (sem `vercel.json`); não depende de a Vercel suportar proxy/rewrite bem | cookie vira de terceiro de verdade — navegadores com *tracking prevention* agressivo (Safari ITP, e o Chrome vem endurecendo isso) podem bloquear mesmo com `SameSite=None; Secure` corretamente configurado; a sessão pode simplesmente parar de funcionar num navegador específico, sem erro nenhum no console | o proxy custa uma config a mais e resolve a causa, não o sintoma |
| Tudo num único host (ex.: servir o front estático pelo próprio FastAPI/Fly.io) | zero problema de cross-site, zero proxy | perde o CDN/edge da Vercel para os assets estáticos, e mistura deploy de front e back num único processo/pipeline, quando os dois têm ciclos de mudança bem diferentes | o proxy dá o melhor dos dois sem essa mistura |
| Render/Railway/Heroku em vez de Fly.io | onboarding mais simples em alguns casos | free tier mais restrito ou inexistente hoje em vários desses (ver "Custo real" abaixo); `ROADMAP_PORTFOLIO.md` já recomendava Fly.io | Fly.io tem free tier genuinamente utilizável para uma única máquina `shared-cpu-1x` pequena, que é o que este projeto precisa |
| Postgres do próprio Fly.io em vez de Neon | um provedor a menos para gerenciar | Fly Postgres não tem um free tier tão direto quanto o Neon hoje, e Neon já vem com `pgvector` pronto (relevante se a busca híbrida da Etapa 5 migrar de embeddings locais para vetor no banco no futuro) | Neon é a recomendação que já estava em `ROADMAP_PORTFOLIO.md` |

## Consequências

**Ganhamos:**
- Link público real: `https://mestre-ia-seven.vercel.app` (front) proxyando para `https://mestre-ia-backend.fly.dev` (API).
- Cookie de sessão continua exatamente como a Etapa 8 desenhou — nenhuma mudança em `SameSite`/`Secure`, porque o proxy elimina o cross-site em vez de precisar lidar com ele.
- `alembic upgrade head` já roda automaticamente no boot do container (`Dockerfile`, `CMD`) — confirmado contra o Postgres real do Neon antes do primeiro deploy (as 6 migrations existentes aplicaram limpo, sem incompatibilidade de dialeto, diferente do que a Etapa 8 encontrou entre SQLite e um `ALTER COLUMN`).
- `CORS_ORIGINS` virou string separada por vírgula em vez de `list[str]` (JSON estrito) — mais robusto para configurar via `fly secrets set`, depois que a primeira tentativa (JSON com colchetes/aspas) chegou corrompida pelo shell.

**Pagamos:**
- Mais uma camada (`vercel.json`) entre o front e a API — depurar um erro de rede exige lembrar que existe um proxy no meio, não só CORS.
- `fly.toml` está com `auto_stop_machines = 'stop'`/`min_machines_running = 0` (custo zero quando ocioso) — significa **cold start**: o primeiro pedido depois de um tempo sem tráfego demora mais (a máquina precisa subir). Aceitável para um projeto de portfólio com tráfego baixo/esporádico; documentado no runbook.
- Streaming (`/chat/stream`) atravessando o proxy da Vercel foi verificado funcionando (`curl -N` contra a URL da Vercel entrega os frames SSE em tempo real, sem buffering perceptível) — mas é uma dependência a mais que poderia, em tese, quebrar numa mudança futura de infraestrutura da Vercel.

**Fica em aberto:**
- Domínio próprio — hoje só os subdomínios padrão (`*.fly.dev`, `*.vercel.app`), decisão deliberada para não gastar/complicar antes de decidir se vale a pena (ver a regra de dinheiro do §Etapa 9).
- Rate limit (Fase E) é em memória, por processo — não sobrevive a múltiplas instâncias do Fly.io. Documentado em `app/infra/rate_limit.py`; só vira problema se o app crescer para mais de uma máquina.

## Como saber que erramos

Se o cold start (máquina subindo do zero) virar reclamação real de latência no primeiro turno de sessões novas, considerar `min_machines_running = 1` — custa dinheiro 24/7 em vez de só sob demanda, e é exatamente o tipo de decisão que a regra de dinheiro do §Etapa 9 existe para governar (só depois de dado real, não de desconforto).

Se o proxy da Vercel um dia falhar em streaming (buffering, timeout) de um jeito que `SameSite=None; Secure` direto no Fly.io não teria, essa é a evidência para reconsiderar esta decisão — hoje o teste ao vivo (`curl -N` e um turno jogado de verdade pelo navegador) não mostrou nenhum sinal disso.

## Custo real (free tier, nesta escala)

- **Fly.io**: 1 máquina `shared-cpu-1x`/1GB, `auto_stop`/`auto_start` — free tier cobre isso para tráfego baixo; sem cartão associado à organização usada aqui, o que já desligou HA automaticamente ("This organization has no payment method, turning off high availability" no log do `fly launch`).
- **Vercel**: plano Hobby — build e hospedagem do front, sem custo para este volume.
- **Neon**: free tier — um projeto Postgres pequeno, adequado ao volume de um projeto de portfólio.
- **Langfuse Cloud** (Fase F, relacionado): free tier — tracing por turno.

Nenhum dos quatro exigiu cartão de crédito para o uso feito nesta etapa.

## Referências

- `ROADMAP_PORTFOLIO.md` — a recomendação original de Fly.io + Vercel + Neon.
- [Fly.io — Machines & Autostop](https://fly.io/docs/launch/autostop-autostart/) — o mecanismo por trás do cold start.
- [Vercel — Rewrites](https://vercel.com/docs/edge-network/rewrites) — o mecanismo do proxy `/api/*`.
- [web.dev — SameSite cookies explained](https://web.dev/articles/samesite-cookies-explained) — por que cross-site com `SameSite=None` ainda pode ser bloqueado por *tracking prevention*.
- Lição 09 — a primeira vez que `SameSite` apareceu neste projeto (localhost × 127.0.0.1).
- Lição 10 — esta decisão explicada por dentro, com os bugs que só apareceram testando em produção de verdade.
