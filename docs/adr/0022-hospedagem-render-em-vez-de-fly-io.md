# ADR-0022 — Hospedagem do backend: Render.com em vez de Fly.io

**Data:** 24/08/2026
**Status:** Aceito
**Etapa:** 14
**Supersede:** ADR-0015

---

## Contexto

O ADR-0015 (Etapa 9) escolheu Fly.io para o backend com um critério explícito: "free tier genuinamente utilizável", sem cartão de crédito associado — a organização usada não tinha cartão, o que já tinha desligado HA automaticamente no `fly launch` original.

Esse critério parou de valer. O trial do Fly.io acabou e a conta passou a exigir cartão de crédito para continuar rodando a máquina, mesmo em `shared-cpu-1x` com `auto_stop`/`min_machines_running = 0`. Isso quebra a premissa central do ADR-0015 — não é mais possível manter o backend no ar sem entrar com um método de pagamento, o que o projeto não tinha decidido fazer (a "regra de decisão sobre dinheiro" do §Etapa 9 do `PLANO_MESTRE.md` é sobre *investir* em melhorias após 30 dias de dados, não sobre pagar só para manter o link público existente).

Render.com oferece um plano free para Web Services com Docker que não exige cartão para o volume deste projeto (uma máquina pequena, tráfego baixo/esporádico de portfólio).

## Decisão

**Migrar o backend de Fly.io para Render.com**, mantendo Vercel (front) e Neon (Postgres) do ADR-0015 sem alteração. `render.yaml` na raiz do repo é o *Blueprint* que o Render lê para criar o serviço a partir do `Backend/Dockerfile` (`dockerfilePath`/`dockerContext` apontando para `Backend/`).

Duas consequências mecânicas da troca de plataforma:

- **`alembic upgrade head` volta para o `CMD` do `Backend/Dockerfile`.** O plano free do Render não tem equivalente ao `release_command` do `fly.toml` (um passo que roda uma vez por deploy, antes do tráfego virar para a versão nova) — então a migration volta a rodar a cada *boot* de máquina, como era antes do ADR-0016/A-6. É idempotente e barato (é um no-op se o banco já está na head); o custo real é só a checagem contra o Neon a cada *wake* do free tier.
- **O job `deploy-backend` sai do `.github/workflows/ci.yml`.** O Render tem GitHub App próprio: builda e implanta sozinho a cada push em `main`, sem precisar de token (`FLY_API_TOKEN` deixa de existir) nem de um step de deploy no CI. O CI continua garantindo lint/tipos/testes antes disso — o Render não sabe rodar essa checagem, só faz deploy do que chegar no branch.

`GOOGLE_REDIRECT_URI` aponta para `https://mestre-ia-seven.vercel.app/api/auth/google/callback` (a origem da Vercel, via proxy), não para `mestre-ia-backend.onrender.com` direto — a mesma razão de `SameSite=Lax` do ADR-0015 vale para o redirect do Google, e a primeira versão do `render.yaml` errou isso apontando direto para o Render antes de corrigir.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Continuar no Fly.io, cadastrar cartão | zero mudança de configuração, `fly.toml`/`release_command` já funcionando | quebra o critério original do ADR-0015 (free tier sem cartão); mesmo sem uso real além do free tier, expõe a um cobrança inesperada por engano de configuração | o projeto não decidiu investir dinheiro nesta etapa — a regra do §Etapa 9 existe para essa decisão ser deliberada, não forçada por uma mudança de política do provedor |
| Railway | onboarding parecido ao Render, também com Blueprint-like config | free tier mudou para crédito por uso com cartão de verificação em vários relatos recentes de usuários — mesmo problema do Fly.io, só que com um passo a mais para descobrir | não resolve o critério "sem cartão" que motivou a troca |
| Servir o front estático pelo próprio FastAPI (voltar a um único host, como já cogitado no ADR-0015) | eliminaria de vez o proxy da Vercel e qualquer questão de cross-site | perde o CDN/edge da Vercel para os assets estáticos; mistura o deploy de front e back de novo, quando os dois têm ciclos de mudança diferentes — o próprio ADR-0015 já tinha descartado isso por essa razão, e nada mudou nesse cálculo | o problema aqui é o provedor do backend, não a separação front/back |
| Hugging Face Spaces (citado como opção em `ROADMAP_PORTFOLIO.md`) | free tier sem cartão, já era a alternativa nomeada desde o início do projeto | pensado para demos de ML (Gradio/Streamlit), não para um Web Service com Postgres externo e sessão via cookie — exigiria mais adaptação do que trocar de PaaS Docker-first | Render aceita o `Dockerfile` existente quase sem mudança, HF Spaces não |

## Consequências

**Ganhamos:**
- O backend volta a rodar em free tier genuinamente sem cartão — o critério original do ADR-0015 fica restaurado, só que num provedor diferente.
- Deploy automático continua existindo, agora nativo do Render (GitHub App) em vez de um step de Action mantido à mão com um secret (`FLY_API_TOKEN`) — uma peça a menos para expirar ou vazar.
- `render.yaml` versiona a configuração do serviço no próprio repositório (Blueprint), em vez de viver só no `fly.toml` + na UI da Fly — mesmo espírito de infraestrutura como código que o projeto já tinha.

**Pagamos:**
- `alembic upgrade head` roda a cada boot de máquina em vez de uma vez por deploy — o Render free "dorme" o serviço sem tráfego, então isso é a cada volta de jogador depois de um tempo parado, não só a cada push (o mesmo trade-off que o Fly.io tinha *antes* do ADR-0016/A-6 introduzir `release_command`; volta a existir aqui porque o Render não tem o equivalente).
- CI perdeu a checagem de que o deploy propriamente dito funcionou — antes, o job `deploy-backend` falhar era sinal direto de problema; agora o único jeito de saber se o deploy do Render deu certo é olhar o dashboard do Render ou o `/health` depois do push.
- Mais um provedor no histórico do projeto (Fly.io → Render) sem um ADR de "por que Fly.io" ter sido escrito à parte da decisão de bundle do ADR-0015 — este ADR também cobre essa lacuna retroativamente.

**Fica em aberto:**
- Cold start: igual ao Fly.io, o Render free hiberna o serviço ocioso — o primeiro pedido depois de um tempo sem tráfego demora mais. Não medido ainda contra o Neon (o ADR-0015 tinha confirmado isso para o Fly.io antes do primeiro deploy; falta repetir o teste ao vivo para o Render).
- `GOOGLE_REDIRECT_URI` e `CONFIRMACAO_EMAIL_URL` em `render.yaml` citam `mestre-ia-backend.onrender.com` como nome do serviço — depende de esse ser de fato o nome que o Render atribuiu no primeiro deploy (mesmo cuidado que o comentário original do `render.yaml` já sinalizava; falta confirmar depois do deploy real, como o ADR-0015 confirmou as 6 migrations contra o Neon).

## Como saber que erramos

Se o Render também endurecer a política de free tier (exigir cartão, como o Fly.io fez) dentro do horizonte deste projeto, é sinal de que a causa raiz não é "provedor errado" e sim "depender de free tier sem plano B" — nesse caso, a resposta correta não é trocar de PaaS de novo, e sim aplicar a regra de decisão sobre dinheiro do §Etapa 9 e pagar por algo estável.

Se o cold start do Render for perceptivelmente pior que o do Fly.io (medido ao vivo, não por suposição), isso pesa contra esta escolha especificamente e a favor de reconsiderar Railway ou HF Spaces adaptado.

## Referências

- [ADR-0015](0015-hospedagem-fly-vercel-neon.md) — a decisão original de hospedagem que este ADR substitui; o proxy da Vercel e o raciocínio sobre `SameSite` continuam valendo sem alteração.
- [ADR-0016](0016-convidado-e-confirmacao-de-email-bloqueante.md) — não relacionado a hospedagem; citado incorretamente no `Backend/Dockerfile` antes desta correção (era a decisão de convidado/confirmação de e-mail, não a de Fly.io → Render).
- `render.yaml` — o Blueprint desta decisão.
- [Render — Blueprint specification](https://render.com/docs/blueprint-spec) — o formato do `render.yaml`.
- [Render — Free plan limits](https://render.com/docs/free) — hibernação por inatividade, o cold start equivalente ao `auto_stop_machines` do Fly.io.
