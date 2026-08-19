# Documentação do Mestre.IA

Este diretório existe por causa de um combinado: **nenhuma mudança relevante entra no projeto sem o documento que explica por que ela entrou.**

Não é burocracia. É o que transforma um repositório de código num caso de estudo defensável — e é o que permite, daqui a seis meses, responder "por que assim?" sem reabrir o código.

---

## Os três formatos

| Formato | Pergunta | Onde | Quando | Imutável? |
|---|---|---|---|---|
| **ADR** | *Por que assim, e não do outro jeito?* | `docs/adr/` | toda decisão com alternativa real | ✅ sim |
| **Lição** | *Como essa tecnologia funciona por dentro?* | `aprender/lessons/` | toda tecnologia nova | ❌ pode ser revisada |
| **Diário** | *O que mudou, o que quebrou, o que aprendi?* | `docs/diario/` | ao fim de cada etapa | ✅ sim (é um registro histórico) |

### A regra de bolso

> **ADR é sobre a escolha. Lição é sobre a ferramenta. Diário é sobre a jornada.**

Exemplo, com uma mudança só:

| O que aconteceu | Vai para |
|---|---|
| "Escolhi Alembic em vez de escrever `ALTER TABLE` na mão" | **ADR** |
| "Uma migration é um arquivo ordenado que descreve uma transformação de schema; o Alembic guarda a revisão atual numa tabela própria" | **Lição** |
| "A primeira migration apagou meu banco de dev porque autogenerate não vê coluna JSON; foi assim que descobri e assim que consertei" | **Diário** |

---

## ADR — Architecture Decision Record

**Formato:** `docs/adr/NNNN-titulo-em-kebab-case.md`
**Template:** [`0000-template.md`](adr/0000-template.md)
**Tamanho:** uma página. Se passar disso, provavelmente são dois ADRs.

**Quando escrever um:** quando existiu uma alternativa real. "Usei Python" não é ADR — não havia escolha. "Usei uv em vez de pip + venv" é ADR — havia, e você descartou uma opção viável.

**Por que são imutáveis:** um ADR registra o que você sabia *naquele momento*. Quando a decisão muda, você escreve um novo com `Supersede: ADR-0007` no cabeçalho e marca o antigo como `Substituído`. O par de ADRs contando "decidi X, depois descobri Y e virei para Z" vale mais numa entrevista do que qualquer decisão que nunca precisou mudar.

**Índice:** [`adr/README.md`](adr/README.md)

---

## Lição

**Formato:** `aprender/lessons/NNNN-titulo.html`, usando `aprender/assets/curso.css`
**Modelo de referência:** [`0001-o-caminho-de-uma-jogada.html`](../aprender/lessons/0001-o-caminho-de-uma-jogada.html)

**Regras herdadas de [`aprender/NOTES.md`](../aprender/NOTES.md):**
- Toda explicação ancorada numa **linha real deste código**, com o caminho do arquivo. Nada de exemplo genérico.
- Nada de explicar fundamentos (função, dicionário, complexidade) — a lacuna é em bibliotecas e arquitetura, não em programação.
- Terminar com um **achado**: algo concreto e um pouco desconfortável sobre o próprio projeto.
- Português. Denso é bom.

Cada lição rende um registro em `aprender/learning-records/`, que é a memória de *o que já foi ensinado* — para não repetir e para saber o que revisar.

---

## Diário de etapa

**Formato:** `docs/diario/NNNN-etapa-N.md`

**Tom: calmo e em termos simples — não em jargão de engenheiro.** O ADR pode ser técnico (é uma comparação de alternativas, gênero naturalmente mais formal). O diário é para reler meses depois, já tendo esquecido o contexto — então explica cada termo técnico (ferramenta, sigla, comando) na primeira vez que ele aparece, com uma frase simples entre parênteses. "Lockfile", "PATH", "TestClient" não podem aparecer sem uma explicação ao lado.

Estrutura sugerida:

```markdown
# Etapa N — <nome>

**Período:** dd/mm – dd/mm · **Horas reais:** Xh (estimado: Yh)

## O que foi entregue
## O que quebrou no caminho
## Decisões tomadas (links para os ADRs)
## Números
## O que eu faria diferente
## O que ficou para depois
```

**A seção mais importante é "o que quebrou".** É de lá que saem os posts, e é ela que prova que você viveu o processo em vez de copiar uma arquitetura pronta. Um diário sem erro registrado é um diário incompleto — ou desonesto.

**A seção "horas reais vs estimado"** é o que calibra o plano. Depois de três etapas você sabe o seu fator de erro e para de estimar mal.

---

## Relatórios de avaliação

**Formato:** `docs/relatorios/NNNN-avaliacao-vN.md` — a partir da Etapa 6.

Um por rodada de medição. Contém a tabela qualidade × latência × custo, a concordância do LLM-as-a-judge com a anotação humana, e o que mudou desde a rodada anterior.

---

## Onde cada coisa mora, no repositório inteiro

```
PLANO_MESTRE.md          o plano de execução (o quê, em que ordem)
ROADMAP_PORTFOLIO.md     a estratégia de carreira (para quê)
README.md                a porta de entrada do repositório
BACKLOG.md               as ideias recusadas pela regra anti-escopo

docs/
  adr/                   decisões, imutáveis
  diario/                a jornada, por etapa
  relatorios/            medições (Etapa 6+)
  runbook.md             o que fazer quando cair (Etapa 8+)

aprender/
  MISSION.md             o que o Breno quer conseguir fazer
  NOTES.md               como ele quer ser ensinado
  RESOURCES.md           fontes confiáveis já avaliadas
  lessons/               as lições, em HTML
  reference/             glossários e material de consulta
  learning-records/      o que já foi ensinado, e o que revisar
```
