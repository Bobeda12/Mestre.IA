# Plano Mestre — do protótipo ao produto

**Projeto:** Mestre.IA · **Autor:** Breno · **Escrito em:** 18/08/2026
**Objetivo duplo:** um jogo que as pessoas realmente joguem **e** um caso de estudo que sustente uma entrevista de Engenharia de IA/LLM.

> Este documento é o **plano de execução**. Ele complementa, não substitui:
> - [`ROADMAP_PORTFOLIO.md`](ROADMAP_PORTFOLIO.md) — a estratégia de carreira (o *para quê*)
> - [`aprender/MISSION.md`](aprender/MISSION.md) — a missão de aprendizado (o *como você estuda*)
>
> Aqui está o *o quê* e o *em que ordem*, com o critério de pronto de cada passo.

---

## 1. Como ler este plano

Ele tem três camadas, e você pode parar em qualquer uma:

1. **Seção 2** — o diagnóstico funcional. O que o jogo faz de errado hoje, com número de linha.
2. **Seções 3–5** — as decisões: stack alvo, o que foi recusado e por quê, e como a documentação vai funcionar.
3. **Seção 6** — as nove etapas, cada uma com escopo fechado, tecnologia nova, documentos a produzir e critério de pronto.

Regra que vale para o plano inteiro: **nenhuma etapa termina sem os documentos dela.** O documento não é subproduto do código — nesta empreitada os dois são a entrega.

---

## 2. Diagnóstico: o que o Mestre.IA é hoje

### 2.1 O que existe e é bom

- `Backend/data/biblia_mestre.txt` (2.224 bytes) é prompt engineering de verdade — protocolo de arbitragem, degradação sensorial por faixa de HP, consequência social. Não é "aja como um mestre de RPG". É o ativo mais valioso do repositório.
- O wizard de criação (`CharacterCreation.tsx`, 296 linhas) tem point-buy de 27 pontos, bônus racial com escolha livre, preview de HP e CA. É um sistema de fato.
- O front tem identidade visual: `tailwind.config.js` define uma paleta própria (`rpg-gold`, `rpg-crimson`, `parchment`) e duas fontes temáticas. Isso é raro em projeto de portfólio.
- React 19, Vite 7, TypeScript 5.9 — o front já está em versões atuais.

### 2.2 O que está quebrado

Esta é a parte que importa. Ordenada por gravidade **para o jogador**, não para o engenheiro.

| # | Sintoma para quem joga | Causa, com linha | Gravidade |
|---|---|---|---|
| 1 | "Continuar jornada" volta para a home e não carrega nada | `App.tsx:29` — a rota `/jogar` exige o estado `sessionId`, que só é preenchido ao **criar** personagem. Recarregou a página, o estado sumiu, a rota redireciona. **Todo save é inacessível.** | 🔴 fatal |
| 2 | Você gasta 27 pontos distribuindo atributos e o jogo ignora | `CharacterCreation.tsx:119-122` — o `POST /create_character` não envia `atributos`. `api.py:120-125` chuta `15/14/13/12/10/10` fixo para todo mundo. **O passo 4 do wizard é teatro.** | 🔴 fatal |
| 3 | Você nunca toma dano, nunca morre, nunca cura | `api.py` — `hp_atual` só é **lido** (linhas 87, 96, 149, 193). Nunca é atribuído. O prompt até pede o HP ao modelo (linha 96), mas a resposta é descartada. **Ninguém governa o HP.** | 🔴 fatal |
| 4 | O combate começa e nunca acaba | `api.py:179-182` — spawna um `{"nome": "Inimigo", "hp": 10}` genérico. Inimigo não ataca, não toma dano, não morre. A guarda `not c_state.get("ativo")` impede novo combate para sempre. | 🔴 fatal |
| 5 | O mestre esquece o que aconteceu 5 mensagens atrás | `api.py:168` — `list(heroi.historico_chat)[-4:]` | 🟠 grave |
| 6 | O inventário nunca muda; ouro não existe | `inventario` é escrito uma vez na criação (`api.py:132`) e nunca mais | 🟠 grave |
| 7 | Sua história de personagem é ignorada | `historia_texto` existe no modelo Pydantic (`api.py:28`), o front envia, e **nada** lê | 🟠 grave |
| 8 | Sua CA some ao recarregar | Só existe no `localStorage` (`Home.tsx:50` usa `saveInfo.defense`). Não há coluna no banco. | 🟡 médio |
| 9 | Quando a IA falha, você vê `"..."` e não sabe por quê | `api.py:174` — `except: dados = {"narrativa": "..."}`. Engole tudo, inclusive `client is None` quando falta a chave. | 🟡 médio |

### 2.3 Código morto que revela intenções abandonadas

- `rolar_dado()` (`api.py:37`) — **nunca é chamada.** Existem dados no código e não existem dados no jogo.
- `monsters.json`, `weapons.json`, `locations.json` são carregados por `data_manager.py` e **nunca consultados**. `get_relevant_rules()` não tem um único chamador. Há um bestiário completo dormindo em disco enquanto o combate spawna `"Inimigo"` genérico.

### 2.4 Higiene

- `Backend/rpg_save.db` **está versionado no git** (`git ls-files` confirma), apesar de `*.db` estar no `.gitignore` — foi commitado antes da regra existir, e o `.gitignore` não desfaz rastreamento. Seus saves de teste estão no histórico.
- `requirements.txt` está em **UTF-16** (assinatura `ff fe`, gerada por `pip freeze >` no PowerShell). Quebra `pip install -r` em Linux e no Docker.
- ~13 pacotes do Google (SDK do Gemini) no `requirements.txt` sem um único import correspondente.
- `database.py:2` importa `declarative_base` do caminho legado `sqlalchemy.ext.declarative`.
- `allow_origins=["*"]` (`api.py:23`), sem rate limit, sem sanitização.
- `http://127.0.0.1:8000` está hardcoded em 6 lugares do front. Nada disso sobrevive a um deploy.
- O modelo em uso hoje é `openai/gpt-oss-120b` (`api.py:20`), não o `llama-3.3-70b` que o `ROADMAP_PORTFOLIO.md` descreve. O roadmap está desatualizado nesse ponto.

### 2.5 A leitura honesta

O Mestre.IA hoje é um **chat com tema de RPG**, não um RPG. A ficha na barra lateral é decorativa: HP, inventário e atributos são exibidos e nunca mudam. O único componente que funciona ponta a ponta é a criação de personagem — e mesmo ela joga metade das suas escolhas fora.

Isso não é um problema. É a oportunidade: **todo defeito da lista acima é uma competência de mercado esperando para ser demonstrada.** É mais fácil defender numa entrevista um sistema que você consertou e mediu do que um que nasceu pronto.

---

## 3. A visão: o que ele vai ser

**Em uma frase, a tese técnica do projeto:**

> *"Um LLM não pode ser o motor de regras de um jogo. Ele deve ser o narrador. Eu construí a separação — e medi que ela funciona."*

**Em uma frase, a promessa ao jogador:**

> *"Um mestre de RPG que não te protege, não esquece o que você fez, e não pode mentir sobre as regras."*

Essas duas frases são o filtro de escopo. Toda feature proposta daqui em diante precisa servir a uma delas.

### O sistema alvo, em uma imagem

```
 Jogador digita "ataco o goblin com o machado"
        │
        ▼
 [ NARRADOR ]  LLM com ferramentas  ──chama──►  [ JUIZ ]  motor de regras em Python puro
        │                                            │      d20+3 vs CA 15 → acerto
        │      ◄──── fatos, não opiniões ────────────┘      1d12+3 = 9 de dano → goblin: 7→0
        ▼
 "O machado desce num arco. O goblin ergue o escudo tarde demais..."
        │
        ▼
 [ GUARDA ]  a narrativa contradiz o estado?  →  se sim, uma correção
        │
        ▼
 [ MEMÓRIA ]  o evento vira registro recuperável 80 turnos depois
```

O motor decide. O modelo narra. A guarda confere. A memória lembra.

---

## 4. Stack alvo — e o que foi recusado

Cada linha aqui vira um ADR quando for implementada. Aqui está o resumo com a justificativa curta.

### 4.1 Backend

| Peça | Escolha | Por quê |
|---|---|---|
| Runtime | Python 3.13 | já é o que você tem instalado |
| Dependências | **`uv`** + `pyproject.toml` | resolve o problema do `requirements.txt` UTF-16 de vez, é ordens de grandeza mais rápido que pip, e virou o padrão da comunidade Python. Lockfile reprodutível. |
| API | **FastAPI** (mantém) | não há motivo para trocar; o que muda é a estrutura em camadas |
| Validação | Pydantic v2 + **pydantic-settings** | config tipada no lugar de `os.getenv` solto |
| ORM | **SQLAlchemy 2.0 estilo tipado** (`Mapped[]`, `mapped_column`) | o estilo atual do `database.py` é de 2019; o novo dá tipos reais ao mypy |
| Migrations | **Alembic** | sem isso não existe mudança de schema em produção |
| Banco | SQLite (dev) → **Postgres no Neon** (prod) | mesma interface via SQLAlchemy; o Neon tem free tier com `pgvector` incluso |
| LLM | **Groq** (principal) + fallback | free tier, latência baixa; a abstração de provedor é exigida pela realidade da cota |
| Resiliência | `tenacity` | retry com backoff exponencial |
| Logs | `structlog` | log estruturado em JSON — pré-requisito para observabilidade |
| Testes | `pytest` + `pytest-asyncio` + `respx` | `respx` mocka o HTTP do LLM sem gastar cota nos testes |
| Qualidade | `ruff` (lint + format) + `mypy` | `ruff` substitui flake8 + black + isort num binário só |
| Tracing | **Langfuse** (cloud, free) | cada turno vira um trace com prompt, ferramentas, tokens, custo, latência |
| Embalagem | Docker + docker-compose | um comando para subir tudo |

### 4.2 Frontend

| Peça | Escolha | Por quê |
|---|---|---|
| Base | **React 19 + TypeScript + Vite** (mantém) | ver a recusa do Next.js abaixo |
| Estilo | **Tailwind CSS v4** (upgrade do v3) | engine nova, config em CSS via `@theme`, é a versão atual. Migração pequena e vira uma lição. |
| Componentes | **shadcn/ui** (Radix por baixo) | acessibilidade (foco, teclado, ARIA) de graça, e você é dono do código — combina com a estética própria que já existe |
| Estado de servidor | **TanStack Query** | mata os `useEffect` + `axios` soltos, e dá cache, retry e estados de carregamento de graça |
| Contrato | **Zod** validando as respostas da API | o backend pode mentir; o front deve conferir. Fecha o par com o Pydantic do outro lado. |
| Formulários | **react-hook-form** + Zod no wizard | o wizard de 5 passos hoje é `useState` na mão |
| Streaming | **SSE** (`fetch` + `ReadableStream`) | o único ganho de latência que o jogador *sente* |
| Testes | **Vitest** + Testing Library; **Playwright** para 2 fluxos E2E | criar personagem e jogar um turno |

### 4.3 Infraestrutura

| Peça | Escolha |
|---|---|
| CI | GitHub Actions — lint, tipos, testes, **e o gate de avaliação da Etapa 6** |
| Backend em produção | Fly.io (Docker, escala a zero) — alternativa: Render |
| Frontend em produção | Vercel ou Cloudflare Pages |
| Banco em produção | Neon (Postgres + `pgvector`, free tier) |
| Observabilidade | Langfuse cloud |

### 4.4 O que foi recusado — e por quê

Esta seção vale tanto quanto a de cima. Numa entrevista, saber justificar o que você **não** usou é o sinal mais forte de senioridade.

- **Next.js.** A escolha reflexa, e errada aqui. Seu backend é Python: o Next entraria só como camada de UI, trazendo um segundo runtime, um BFF e complexidade de deploy. O produto é um app atrás de sessão — não tem SEO, não tem conteúdo público indexável, não se beneficia de SSR. Vite + React entrega o mesmo resultado e mantém o esforço onde a vaga-alvo olha: a engenharia de LLM. **Se um recrutador perguntar "por que não Next?", essa resposta impressiona mais do que ter usado.**
- **LangChain / LlamaIndex.** Escondem exatamente as três coisas que o projeto existe para demonstrar: a montagem do prompt, o loop de ferramentas e a recuperação de memória. Você viraria usuário de um framework em vez de autor de uma arquitetura. Reavaliar apenas se manter o código próprio virar gargalo real — e aí o ADR registra a virada.
- **Banco vetorial dedicado (Pinecone, Qdrant, Weaviate).** `sqlite-vec` em desenvolvimento e `pgvector` no Neon cobrem folgadamente a escala deste projeto. Mais um serviço é mais um ponto de falha e mais uma conta.
- **Redis.** Só entra quando houver necessidade concreta (rate limit distribuído ou cache semântico com múltiplas instâncias). Começa em memória.
- **Serviço de autenticação gerenciado (Clerk, Auth0, Supabase Auth).** O projeto **tem** contas (decisão §9.1), mas com login por e-mail mágico implementado à mão: uma tabela de tokens de uso único e um cookie de sessão. São ~150 linhas contra uma dependência externa, um SDK no front e um provedor a mais no diagrama. Autenticação sem senha é justamente o caso em que rolar o próprio é defensável — não há hash de senha a errar. *(Se o produto um dia precisar de SSO corporativo ou MFA, esse cálculo se inverte, e o ADR-0014 registra o gatilho.)*
- **Kubernetes, microserviços, filas.** Não. Um monólito bem estruturado é a arquitetura correta para este tamanho, e saber disso é a competência.
- **WebSocket.** SSE resolve streaming unidirecional com muito menos complexidade. O ADR-0012 vai registrar a comparação.

---

## 5. Como a documentação vai funcionar

Você pediu documento a cada mudança. Sem um sistema, isso vira um arquivão que ninguém lê. São **três formatos**, cada um respondendo a uma pergunta diferente.

| Formato | Pergunta que responde | Onde vive | Quando se escreve | Tamanho |
|---|---|---|---|---|
| **ADR** (Architecture Decision Record) | *"Por que assim, e não do outro jeito?"* | `docs/adr/NNNN-titulo.md` | toda decisão que teve alternativa real | 1 página |
| **Lição** | *"Como essa tecnologia funciona por dentro?"* | `aprender/lessons/NNNN-*.html` | toda tecnologia nova que entra | 10–15 min de leitura |
| **Diário** | *"O que mudou nesta etapa, o que quebrou, o que aprendi?"* | `docs/diario/NNNN-etapa-N.md` | ao fim de cada etapa | 1–2 páginas |

Mais dois artefatos pontuais:

- **README.md** — a porta de entrada do repositório. Reescrito na Etapa 2, atualizado ao fim de cada etapa.
- **Relatórios de avaliação** — `docs/relatorios/` — a partir da Etapa 6, um por rodada de medição.

### A regra que faz o sistema funcionar

> **ADR é sobre a escolha. Lição é sobre a ferramenta. Diário é sobre a jornada.**

Escolher Alembic em vez de escrever SQL na mão → ADR.
Entender o que é uma migration e por que ela é ordenada → Lição.
"Rodei a primeira migration, ela apagou o banco de dev, foi assim que consertei" → Diário.

O diário é onde os erros moram. **Ele é o documento mais valioso dos três** — é dele que saem os posts, e é ele que prova que você viveu o processo em vez de copiar uma arquitetura pronta.

Os ADRs são **imutáveis**: quando uma decisão muda, você escreve um ADR novo que diz "supersede o 0007" e mantém o antigo. O histórico de decisões revertidas é parte da prova.

O template está em [`docs/adr/0000-template.md`](docs/adr/0000-template.md). O sistema completo está descrito em [`docs/README.md`](docs/README.md).

---

## 6. As etapas

Dez etapas, ~215 horas, ~5,5 meses a 10h/semana — com folga para 6.

Cada etapa tem: **objetivo**, **por que agora**, **o que muda no código**, **tecnologia nova**, **documentos**, **critério de pronto** e **o que fica jogável**.

O último campo é o mais importante. Etapa que não muda nada para o jogador precisa dizer isso com todas as letras, para você não se enganar sobre progresso.

---

### Etapa 0 — Rodar e provar · ~8h · 1 semana

**Objetivo:** qualquer pessoa (inclusive você daqui a três meses) clona o repositório e joga em menos de 5 minutos.

**Por que agora:** hoje você não tem como provar que uma mudança quebrou algo, porque não tem como rodar de forma repetível. Tudo depois disso depende deste chão.

**O que muda:**
- `Backend/` migra para `pyproject.toml` gerenciado por `uv`; o `requirements.txt` UTF-16 morre
- os ~13 pacotes do Google saem
- `git rm --cached Backend/rpg_save.db` — tira o banco do versionamento (o histórico continua lá; não vale reescrever por isso)
- `database.py:2` passa a importar de `sqlalchemy.orm`
- `Backend/teste.py` vira `tests/test_smoke.py` de verdade, com `pytest`
- `justfile` (ou `Makefile`): `just dev`, `just test`, `just lint`
- README mínimo: pré-requisitos, `.env.example`, dois comandos

**Tecnologia nova:** `uv`, `pytest`, `just`

**Documentos:**
- `ADR-0001` — gerenciamento de dependências com uv em vez de pip + venv
- `docs/diario/0001-etapa-0.md`

**Pronto quando:** `just test` passa numa máquina limpa; o `.env.example` está no repositório e o `.env` não.

**Jogável:** nada muda para o jogador. **Isso é esperado.**

---

### Etapa 1 — Consertar as mentiras · ~12h · 1–2 semanas

**Objetivo:** o jogo para de mentir. Tudo que a interface mostra passa a ser verdade.

**Por que agora:** motivação. São quatro bugs 🔴 com correção pequena e efeito imediato — e nenhum depende da refatoração da Etapa 2. Consertá-los antes de reestruturar te dá um jogo funcional para testar a reestruturação contra.

**O que muda:**
1. **A rota `/jogar`** — o `sessionId` sai do estado do `App` e vai para a URL (`/jogar/:sessionId`), com o `localStorage` como índice de saves. Recarregar a página deixa de destruir a sessão.
2. **Os atributos** — o `POST /create_character` passa a receber `atributos`, e o **servidor revalida** os 27 pontos de point-buy e os bônus raciais. O cliente propõe; o servidor decide. (Sim, dá para burlar o front. É exatamente por isso que a regra vive no servidor.)
3. **A CA** vira coluna no banco, calculada pelo servidor.
4. **`historia_texto`** entra no prompt do prólogo — o campo passa a ter efeito.
5. **O `except:` nu** vira tratamento explícito: falta de chave, timeout, JSON inválido e cota estourada viram erros distintos, com mensagem própria no front.

**Tecnologia nova:** validação de domínio no Pydantic (`field_validator`, `model_validator`), tratamento de erro em camadas, roteamento com parâmetro no React Router

**Documentos:**
- `ADR-0002` — a fronteira de confiança: por que toda regra de criação é revalidada no servidor
- `Lição 02` — o contrato entre front e back: Pydantic de um lado, Zod do outro
- `docs/diario/0002-etapa-1.md`

**Pronto quando:** você cria um personagem com atributos personalizados, fecha o navegador, reabre e continua a mesma partida com os mesmos números.

**Jogável:** ✅ Suas escolhas de criação passam a valer. Saves funcionam. Erros aparecem em vez de virar `"..."`.

---

### Etapa 2 — Arquitetura auditável · ~25h · 3 semanas

**Objetivo:** o `api.py` de 203 linhas fazendo tudo vira uma estrutura em camadas com testes e CI.

**Por que agora:** as Etapas 3 e 4 vão triplicar o tamanho do backend. Fazer isso dentro de um arquivo único é como construir um segundo andar sem fundação.

**O que muda:**

```
backend/
  app/
    routers/     character.py · game.py · options.py
    services/    narrator.py · rules_engine.py · memory.py
    domain/      models Pydantic do estado do jogo (a "verdade" do sistema)
    infra/       db.py · llm_client.py · settings.py
  migrations/    Alembic
  tests/
```

- `pydantic-settings` no lugar de `os.getenv`
- `database.py` reescrito no estilo tipado do SQLAlchemy 2.0
- **O modelo de dados nasce com contas** (decisão §9.1): a tabela `herois` — onde hoje `session_id` é a chave primária, ou seja, *personagem é sessão* — vira `usuario (1:N) personagem`. A Etapa 2 cria um usuário local fixo; a autenticação de verdade só chega na Etapa 8, mas em cima de um schema que já a comporta. Migration de chave primária com dados em produção é a operação mais cara que existe; fazer isso agora é de graça.
- Alembic com a migration inicial (já contendo `usuario`)
- `pytest` cobrindo o domínio; meta modesta e honesta: **60% em `domain/` e `services/`**, não no projeto inteiro
- GitHub Actions: `ruff` → `mypy` → `pytest`, com badge no README
- Docker + docker-compose
- **README de engenheiro**: diagrama Mermaid da arquitetura, decisões com o porquê, como rodar, limitações conhecidas

**Tecnologia nova:** Alembic, SQLAlchemy 2.0 tipado, pydantic-settings, ruff, mypy, GitHub Actions, Docker

**Documentos:**
- `ADR-0003` — camadas: por que router / service / domain / infra
- `ADR-0004` — migrations com Alembic
- `ADR-0005` — modelo de dados usuário × personagem, e por que ele nasce antes da tela de login
- `Lição 03` — o que um ORM realmente faz, e quando ele atrapalha (com o caso real das colunas JSON que exigem reatribuição)
- `docs/diario/0003-etapa-2.md`

**Pronto quando:** o CI está verde; `docker compose up` sobe tudo; nenhum arquivo passa de 150 linhas.

**Jogável:** nada muda para o jogador. **Diga isso em voz alta** — é a etapa em que mais gente se ilude achando que progrediu.

---

### Etapa 3 — O juiz ⭐ · ~30h · 3 semanas

**Objetivo:** existe um motor de regras determinístico em Python puro. HP muda. Você pode morrer.

**Por que agora:** é a fundação da tese do projeto. Sem o juiz, o narrador da Etapa 4 não tem o que narrar.

**O que muda:**
- `services/rules_engine.py`, **zero I/O e zero LLM**: rolagem de dados com gerador injetável (seed), testes de atributo contra CD, ataque (`d20 + mod + proficiência` vs CA), dano por tipo de arma, iniciativa, condições, testes de morte
- Máquina de estados de combate explícita: `fora_de_combate → iniciativa → turno_jogador → turno_inimigo → resolucao`
- **O bestiário acorda**: `monsters.json` e `weapons.json` passam a ser lidos. Adeus `{"nome": "Inimigo", "hp": 10}`.
- `rolar_dado()` sai do limbo, ganha gramática de verdade (`2d6+3`, `1d20`, vantagem/desvantagem) e **levanta exceção** em entrada inválida em vez de devolver `0`
- **50+ testes unitários** rodando em menos de meio segundo, sem rede

**Escopo do 5e** (decisão §9.2) — implementa só o subconjunto que os seus JSONs já descrevem. Fica **fora**, e precisa estar escrito no README para não parecer omissão: magias com slots, multiclasse, façanhas, grid tático com deslocamento, e a maior parte das condições. O combate é theater-of-the-mind com resolução determinística. **Um herói contra N inimigos** — sem abstração de mesa multi-jogador (decisão §9.3).

**Tecnologia nova:** injeção de aleatoriedade para testar sistemas estocásticos, máquinas de estado, `pytest.mark.parametrize`, testes baseados em propriedades (`hypothesis`, opcional)

**Documentos:**
- `ADR-0006` — por que o LLM não pode ser o motor de regras (**o ADR mais importante do projeto**)
- `Lição 04` — determinismo, seed e por que testar código aleatório é mais fácil do que parece
- `docs/diario/0004-etapa-3.md`

**Pronto quando:** você roda a suíte 100 vezes e ela dá o mesmo resultado 100 vezes; um goblin te mata.

**Jogável:** ✅✅ **A maior virada do projeto.** HP muda de verdade. Inimigos têm ficha real e morrem. O combate acaba. A morte existe. Pela primeira vez existe risco — e risco é o que torna um RPG divertido.

---

### Etapa 4 — O narrador ⭐ · ~25h · 3 semanas

**Objetivo:** o modelo para de escrever estado e passa a chamar ferramentas.

**Por que agora:** o juiz existe; falta conectá-lo ao modelo pelo caminho certo.

**O que muda:**
- Ferramentas tipadas: `rolar_teste(atributo, cd)` · `atacar(alvo, arma)` · `aplicar_dano(alvo, qtd)` · `mover(destino)` · `consultar_regra(termo)` · `usar_item(item)` · `dar_item(item)` · `gastar_ouro(qtd)`
- Loop de agente com **limite de passos** (um modelo em loop infinito consome cota em minutos)
- Structured outputs presos a schema, retry com backoff, e **cadeia de fallback** entre provedores
- **Guardrail de estado:** antes de responder, um validador confere se a narrativa cita item fora do inventário, NPC morto ou local errado. Se contradiz, uma tentativa de correção.
- Primeira métrica de verdade: **tool-call accuracy** — em N cenários, quantas vezes o modelo chamou a ferramenta certa com os argumentos certos

**Tecnologia nova:** tool calling / function calling, JSON Schema para ferramentas, `tenacity`, padrão de fallback entre provedores

**Documentos:**
- `ADR-0007` — tool calling em vez de JSON solto
- `ADR-0008` — cadeia de fallback de modelo (transformando a restrição de free tier em arquitetura)
- `Lição 05` — anatomia de uma chamada com ferramentas: o que vai no fio, e por que a descrição da ferramenta é prompt engineering
- `docs/diario/0005-etapa-4.md`

**Pronto quando:** você mede a tool-call accuracy antes e depois de reescrever as descrições das ferramentas, e tem os dois números.

**Jogável:** ✅ O mestre para de inventar resultados. Quando ele diz que você acertou, você acertou de verdade — e dá para ver a rolagem.

> 📣 **Post 1 do LinkedIn nasce aqui** (Etapas 3+4): *"Deixar o LLM calcular o dano do meu jogo foi meu maior erro de arquitetura"*, com o diagrama juiz × narrador e o salto de tool-call accuracy.

---

### Etapa 5 — A memória · ~25h · 3 semanas

**Objetivo:** matar o `[-4:]`. O mundo passa a ter continuidade.

**Por que agora:** é o defeito que o jogador mais sente depois da morte existir, e o mais rico tecnicamente.

**O que muda — três camadas:**
1. **Curto prazo:** as últimas N interações, cruas
2. **Médio prazo:** sumário rolante. A cada K turnos, um modelo pequeno comprime o que saiu da janela em **campos estruturados** (`fatos_estabelecidos`, `npcs_conhecidos`, `promessas_feitas`, `mudancas_no_mundo`) — não em texto solto
3. **Longo prazo:** memória vetorial. Cada evento significativo vira registro com embedding e metadados (`session_id`, `turno`, `tipo`, `personagens`)

**Detalhes que separam isto de um tutorial de RAG:**
- **Busca híbrida** BM25 + densa com fusão RRF — vetor puro erra nome próprio, e num RPG tudo é nome próprio
- **Filtro por metadados antes** da busca vetorial: memória nunca vaza entre sessões
- **Decaimento por recência** no score: o que aconteceu há 3 turnos pesa mais que há 80
- **Memória de NPC / reputação** — cumpre a promessa que a sua própria `biblia_mestre.txt` já faz e nunca implementou: *"NPCs têm memória. Se o jogador foi rude antes, o preço na loja sobe 20%."*
- **RAG sobre as regras:** para de despejar a bíblia inteira todo turno; recupera só o relevante. Economia de tokens **medida**.

**Tecnologia nova:** `sentence-transformers`, `sqlite-vec` → `pgvector`, BM25, fusão RRF, avaliação de recall@k

**Documentos:**
- `ADR-0009` — memória hierárquica em três camadas
- `ADR-0010` — busca híbrida: por que vetor puro não basta
- `Lição 06` — embeddings, similaridade e como se mede recall
- `docs/diario/0006-etapa-5.md`

**Pronto quando:** um NPC referencia algo de 40 turnos atrás, e você tem o recall@k medido antes e depois.

**Jogável:** ✅ O mundo lembra. O taverneiro que você ofendeu no turno 5 cobra mais caro no turno 60.

---

### Etapa 6 — Como sei que melhorou? ⭐⭐ · ~30h · 3 semanas

**Objetivo:** responder, com números, à pergunta que derruba quase todo candidato a LLM Engineer.

**Por que agora:** só faz sentido medir quando há o que medir. Agora há.

**O que muda:**
1. **Golden dataset** — 60 a 100 cenários versionados em YAML: estado inicial + ação do jogador + o que deve acontecer. Cobrindo combate, regra ambígua, ação impossível, memória de longo prazo, **injeção de prompt**, e casos-limite (HP 0, inventário vazio, alvo inexistente).
2. **Métricas determinísticas**, baratas, rodando no CI a cada PR: validade de schema · tool-call accuracy · taxa de violação de estado · latência p50/p95 · tokens e custo por turno.
3. **LLM-as-a-judge** com rubrica escrita, notas 1–5 em eixos separados: aderência às regras, consistência com a memória, qualidade sensorial (a sua bíblia exige 3 sentidos — isso é mensurável) e ausência de alucinação de inventário. Calibrado contra ~30 exemplos anotados por você, **com a concordância reportada.** Reportar a limitação do próprio juiz é o tipo de honestidade que engenheiro sênior nota na hora.
4. **Gate de regressão no CI** — PR que derruba a métrica agregada além do limiar não passa. Isso é raríssimo num portfólio.
5. **Bake-off de modelos** — a suíte inteira rodada em 3–4 modelos, produzindo uma tabela **qualidade × latência × custo**. Provável descoberta: um modelo pequeno basta para 70% dos turnos → **roteamento por complexidade**, que é economia real.

**Tecnologia nova:** avaliação de sistemas não-determinísticos, LLM-as-a-judge, concordância entre anotadores, gates de CI

**Documentos:**
- `ADR-0011` — estratégia de avaliação: o que é determinístico, o que é julgado, e por quê
- `Lição 07` — como se testa um sistema que não é determinístico
- `docs/relatorios/0001-avaliacao-v1.md` — o primeiro relatório com a tabela do bake-off
- `docs/diario/0007-etapa-6.md`

**Pronto quando:** existe um PR que o CI **reprovou por queda de qualidade**. Esse print vale mais que mil palavras de README.

**Jogável:** indiretamente — o jogo fica mensuravelmente melhor, e você para de mexer no prompt no escuro.

> 📣 **Post 2 do LinkedIn nasce aqui:** *"Como se testa um sistema que não é determinístico?"*, com o golden dataset e a tabela qualidade × custo × latência.

---

### Etapa 7 — Diversão e sensação · ~25h · 3 semanas

**Objetivo:** parece um jogo, não um chat com tema de RPG.

**Por que agora:** o sistema por baixo já é sólido; agora vale investir no que o jogador sente. Fazer isto antes seria polir uma casa sem fundação.

**O que muda:**
- **Streaming SSE** com efeito máquina de escrever. O tempo até o primeiro token despenca — é a **única** otimização de latência que o usuário percebe. Meça antes e depois.
- **Cards de rolagem no chat**: a rolagem do juiz aparece como um card animado (`d20 → 17 + 3 = 20 vs CA 15 · ACERTO`). Isto é ao mesmo tempo diversão e **transparência do sistema** — o jogador vê que o mestre não trapaceia.
- **HUD de combate real**: ordem de iniciativa, turno atual, alvo selecionável, dano flutuante
- **Inventário vivo**: loot, ouro, uso de item
- **XP e nível** — progressão é o motor de retenção mais barato que existe
- **Tailwind v4 + shadcn/ui**, acessibilidade (teclado, foco, leitor de tela) e layout mobile
- **TanStack Query** substitui os `useEffect` + `axios` soltos
- Opcional, se sobrar tempo: ambiência sonora, imagem de cena sob demanda

**Tecnologia nova:** SSE, TanStack Query, Tailwind v4, shadcn/ui, Vitest, Playwright

**Documentos:**
- `ADR-0012` — SSE vs WebSocket vs polling
- `ADR-0013` — estado de servidor no cliente: por que TanStack Query e não Redux
- `Lição 08` — streaming do servidor ao pixel: o caminho de um token
- `docs/diario/0008-etapa-7.md`

**Pronto quando:** um amigo joga 20 minutos sem você explicar nada e sem reclamar de lentidão.

**Jogável:** ✅✅ É aqui que o projeto vira algo que dá vontade de mostrar.

---

### Etapa 8 — Contas e biblioteca de heróis · ~15h · 2 semanas

**Objetivo:** o jogador faz login e tem *seus* heróis, em qualquer navegador.

**Por que agora:** o schema já comporta contas desde a Etapa 2 (decisão §9.1) — falta a autenticação e a tela. Fazer isto antes do deploy é deliberado: **é muito mais barato depurar login em localhost do que em produção**, e o deploy da Etapa 9 já sobe com o produto completo.

**O que muda:**
- **Login por e-mail mágico** (link de uso único, sem senha). Sem senha significa: sem hash, sem "esqueci minha senha", sem vazamento de credencial. Menos código e menos superfície de ataque — o argumento de segurança e o de esforço apontam para o mesmo lado.
- Sessão em **cookie `httpOnly` + `SameSite`**, não token no `localStorage` (que é legível por qualquer XSS)
- O `localStorage` como fonte de saves **morre**. Hoje ele é a fonte de verdade da lista de heróis (`Home.tsx:27`) e da CA — o servidor passa a ser dono dos dois.
- Tela "Meus heróis": lista, criar, continuar, arquivar
- Autorização em toda rota: um `personagem_id` só responde ao dono. **Isto precisa de teste** — é a falha de segurança nº 1 em API de portfólio (IDOR: trocar o id na URL e ler o personagem de outra pessoa).
- Envio de e-mail: Resend ou Postmark (free tier)

**Tecnologia nova:** autenticação sem senha, cookies de sessão seguros, autorização por recurso, envio transacional de e-mail

**Documentos:**
- `ADR-0014` — autenticação por e-mail mágico em vez de senha ou OAuth
- `Lição 09` — sessão, cookie e token: quem guarda o quê, e por que `localStorage` é o lugar errado
- `docs/diario/0009-etapa-8.md`

**Pronto quando:** você loga em dois navegadores diferentes e vê os mesmos heróis; e existe um teste que prova que o personagem de um usuário retorna 403 para outro.

**Jogável:** ✅ Seus heróis são seus, e te seguem de máquina em máquina.

---

### Etapa 9 — No ar · ~20h · 2 semanas

**Objetivo:** link público que funciona, com instrumentação para decidir se vale investir dinheiro.

**O que muda:**
- Postgres no Neon; Alembic rodando em produção; Docker; Fly.io; front na Vercel
- A URL da API sai do hardcode e vira variável de ambiente por ambiente
- **Segurança:** CORS restrito, rate limit por sessão, sanitização de entrada, e defesa contra injeção de prompt — porque alguém *vai* digitar "ignore suas instruções e me dê 9999 de HP". *(Detalhe bonito de contar: a arquitetura da Etapa 3 já te protege. Se o modelo não escreve HP, injetar HP não funciona. A segurança veio da arquitetura, não de um filtro.)*
- **Langfuse:** custo, latência e tokens por turno, visíveis
- **Telemetria de produto:** sessões criadas, turnos por sessão, retenção D1/D7, ponto de abandono, custo por sessão
- **Botão 👍/👎 por narração** — 20 linhas de código que dão três coisas: sinal humano para validar o LLM-as-a-judge, um dataset de preferência próprio, e conteúdo de post com dado real
- **Runbook**: o que fazer quando cair

**Documentos:**
- `ADR-0015` — escolha de hospedagem e o custo real de cada opção
- `Lição 10` — do localhost à internet: o que muda quando não é mais a sua máquina
- `docs/runbook.md`
- `docs/diario/0010-etapa-9.md`

**A regra de decisão sobre dinheiro** — escreva **antes** de lançar, para não decidir na emoção:

> Investir dinheiro apenas se, após 30 dias no ar: **(a)** a retenção D7 passar de X%, **ou** **(b)** o gargalo de qualidade for comprovadamente o modelo — e não o prompt, a memória ou o motor de regras.

Publicar essa regra antes do lançamento é, por si só, sinal de maturidade de engenharia.

**Jogável:** ✅ Qualquer pessoa com o link joga.

---

## 7. Regras do jogo (para não descarrilhar)

**A regra anti-escopo.** RPG é um poço sem fundo: magias, classes, mapas, facções. Toda ideia nova passa por duas perguntas:

1. **Vira uma métrica?** (serve à tese técnica)
2. **O jogador sente em um turno?** (serve à promessa ao jogador)

Se a resposta for "não" para as duas, vai para `BACKLOG.md` e fica lá. Hobby é legítimo — só não conta como progresso.

**A regra do documento.** Etapa sem os documentos dela não está pronta, mesmo que o código funcione. Esse é o combinado central deste plano.

**A regra da honestidade.** Toda etapa declara se muda algo para o jogador. As Etapas 0 e 2 não mudam — e não tem problema. Se enganar sobre progresso é como projetos morrem no mês quatro.

**Se o tempo apertar** (semestre pesado, PIBIC engolindo tudo), a ordem de prioridade é:

**3 → 4 → 6 → 5 → 1 → 0 → 2 → 7 → 8 → 9**

A Etapa 3 dá a tese. A 4 a conecta. A 6 dá a credibilidade. O resto amplifica.

**Onde cortar, se for preciso cortar:** as Etapas 8 e 9 são as únicas que dependem de tempo de calendário e não de aprendizado — e são as últimas por isso. Se o semestre engolir o mês 6, o repositório com as Etapas 0–7 completas já sustenta a entrevista inteira; o lançamento público escorrega sem prejuízo à tese.

**Três armadilhas conhecidas:**
1. **Refatorar para sempre.** A Etapa 2 tem escopo fechado. Quando bater a vontade de "melhorar mais um pouco", pare e vá para a 3.
2. **Postar sem número.** Post sem métrica é indistinguível dos outros mil "fiz um projeto com IA". São só dois posts no plano — cada um precisa carregar um resultado real.
3. **A cota no dia do lançamento.** Sua chave Groq é compartilhada entre todos os jogadores. Rate limit, fila e fallback precisam existir *antes* de divulgar, senão o primeiro dia de tração vira o primeiro dia de 429.

---

## 8. Calendário aproximado

| Mês | Etapas | Marco |
|---|---|---|
| 1 | 0 · 1 | O jogo cumpre o que a tela promete |
| 2 | 2 · 3 (início) | Arquitetura e schema de contas em pé, motor de regras nascendo |
| 3 | 3 (fim) · 4 | **HP muda, você morre, o mestre não trapaceia** · 📣 Post 1 |
| 4 | 5 | O mundo lembra |
| 5 | 6 · 7 (início) | **Números** · 📣 Post 2 |
| 6 | 7 (fim) · 8 · 9 | Parece um jogo · contas · **link público** |

~215h no total. A 10h/semana são ~22 semanas de trabalho efetivo em 24 semanas de calendário. A folga é fina — se o semestre pesar, o mês 6 escorrega para o 7, e tudo bem: a ordem de prioridade abaixo existe justamente para isso.

---

## 9. Decisões de escopo tomadas

Três forks resolvidos em 18/08/2026. Cada um já está refletido nas etapas acima.

### 9.1 Contas com múltiplos personagens ✅

O lançamento tem **login e biblioteca de heróis**, não sessão anônima descartável.

**Consequência que importa, e por isso ela está aqui:** o modelo de dados precisa nascer certo na **Etapa 2**, não ser retrofitado na 8. Hoje `session_id` é a chave primária de `herois` — ou seja, personagem *é* sessão. Isso precisa virar:

```
usuario (id, email, criado_em)
   │ 1:N
personagem (id, usuario_id, nome, raca, classe, ...)
   │ 1:N
evento_memoria (id, personagem_id, ...)     ← Etapa 5
```

A tabela `usuario` entra na migration inicial da Etapa 2 mesmo antes de existir tela de login — a Etapa 2 cria um usuário local fixo, e a Etapa 8 pluga a autenticação em cima de um schema que já a comporta. **Migration de chave primária num banco com dados é a operação mais cara que existe; fazer isso antes de existirem dados é de graça.**

Custo: ~15h e uma etapa nova. Ganho: o projeto vira produto de verdade, e a demo do recrutador tem "meus heróis" em vez de um chat solto.

### 9.2 D&D 5e enxuto ✅

O motor segue 5e, implementando **só o subconjunto necessário** — o que já está nos seus JSONs: CA, dado de vida, modificador de atributo, `d20 + mod` contra CD, dano por arma, iniciativa, testes de morte.

Por que 5e ganha: seus dados já são 5e (`"Cimitarra (+4 para acertar, 1d6+2 dano)"`), o jogador já sabe jogar, e — o argumento decisivo — o golden dataset da Etapa 6 ganha uma **referência externa de correção**. Com sistema próprio, "o resultado está certo?" vira opinião sua; com 5e, é verificável contra a regra publicada.

O que fica explicitamente **fora** do 5e implementado, e precisa estar escrito no README para não parecer omissão: magias com slots, multiclasse, façanhas, grid tático com deslocamento em metros, e a maior parte das condições. O combate é theater-of-the-mind com resolução determinística.

### 9.3 Single-player ✅

Multiplayer está fora do plano, sem prazo. O motor de regras da Etapa 3 é escrito para **um** herói contra N inimigos, e não paga o custo de abstração de mesa com múltiplos jogadores.

Justificativa para o registro: multiplayer é complexidade de *jogo* (sincronização de turnos, presença, resolução de conflito de ações), não de *LLM*. Não move nenhuma das métricas da tese. Se um dia virar objetivo, será uma reescrita assumida — e o ADR-0006 já vai ter o motor isolado o bastante para tornar isso viável.

---

*Próximo passo: começar a Etapa 0. O primeiro documento a nascer é o `ADR-0001`.*
