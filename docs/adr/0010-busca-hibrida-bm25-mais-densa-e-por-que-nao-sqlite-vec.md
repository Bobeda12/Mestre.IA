# ADR-0010 — Busca híbrida (BM25 + densa, fundidas por RRF) em Python puro, sem sqlite-vec

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 5
**Supersede:** — (revisa a tecnologia prevista para vetor no `ROADMAP_PORTFOLIO.md`, Fase 2/Etapa 5 do `PLANO_MESTRE.md`)

---

## Contexto

O `ROADMAP_PORTFOLIO.md` (Fase 2) previa `sentence-transformers` + `sqlite-vec` em desenvolvimento, subindo para `pgvector` no Neon em produção — a mesma seção (§4.4) já reconhecia, ao recusar um banco vetorial dedicado (Pinecone/Qdrant/Weaviate), que "a escala deste projeto" não exige infraestrutura de vetor pesada: uma partida single-player gera algumas centenas de eventos de memória, não milhões.

O ADR-0006 já estabeleceu que busca por palavra-chave sozinha (o `consultar_regra` da Etapa 4) tem limite: não generaliza paráfrase. O oposto também é verdade e é o motivo real deste ADR — busca vetorial pura erra nome próprio. Um embedding de frase representa "sentido geral"; um nome inventado de NPC ou de local vira um token fora do vocabulário do modelo e se dilui no vetor. Um RPG é feito de nome próprio: NPC, local, item. Confirmado na prática com `scripts/memory_recall.py` (ver "Consequências").

## Decisão

Duas escolhas, tomadas com o usuário antes de implementar (ver a conversa desta etapa):

1. **Armazenamento vetorial em Python puro**, não a extensão `sqlite-vec`. Embeddings ficam como `JSON` numa coluna comum (`EventoMemoria.embedding`); a similaridade de cosseno é calculada em `services/hybrid_search.py:_cosseno`, um loop Python simples. Nenhuma extensão nativa para carregar, nenhuma tabela virtual `vec0`, nenhum ponto a mais de fragilidade multiplataforma (o projeto já roda em Windows local e Ubuntu no CI).
2. **Embeddings via `fastembed`** (ONNX Runtime), não `sentence-transformers` (PyTorch). Mesmo resultado — vetor denso local, sem chamada de rede depois do primeiro download do modelo — sem trazer PyTorch (centenas de MB) como dependência de `uv sync` e do CI. Modelo escolhido: `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` (384 dimensões, ~220MB) — precisa ser multilíngue porque o jogo é em português, e a maioria dos modelos pequenos padrão do `fastembed` é treinada só em inglês.

Sobre a busca em si: `services/hybrid_search.py` combina três técnicas, nesta ordem —

- **BM25** (`rank_bm25.BM25Okapi`) sobre os textos tokenizados (regex `\w+`, minúsculo, sem *stopwords* de uma lista fixa curta em português) — pega nome próprio e termo exato.
- **Cosseno** sobre os embeddings densos — pega paráfrase e sinônimo.
- **Reciprocal Rank Fusion** (`fusao_rrf`, `k=10`) combina as duas listas ranqueadas sem precisar normalizar escalas diferentes (BM25 não é limitado; cosseno é -1..1).
- **Decaimento por recência** (`decaimento_recencia`, meia-vida configurável, com piso de 50%) — só entra quando a busca tem noção de turno (memória de longo prazo; não entra no RAG sobre a bíblia, que é conteúdo estático).

O mesmo motor (`hybrid_search.buscar`) é reaproveitado por dois consumidores: `services/memory.py` (memória de longo prazo, ADR-0009) e `services/rag_regras.py` (RAG sobre a bíblia — a bíblia deixa de ser despejada inteira em todo turno; só as seções situacionais relevantes entram, as diretrizes de narração sempre presentes ficam de fora do corpus buscável).

## Dois bugs reais encontrados construindo isto

Vale registrar — são o tipo de coisa que só aparece rodando com dado de verdade, não em teoria:

1. **RRF com `k=60` (o valor "clássico" do paper original) achata demais um corpus pequeno.** Com poucas dezenas de documentos por busca (eventos de uma partida, seções da bíblia), a diferença de score entre a 1ª e a 3ª posição de uma lista fica pequena o bastante para o decaimento por recência dominar sozinho o resultado final — rodando `scripts/memory_recall.py` pela primeira vez, a busca híbrida devolvia sempre os 3 eventos mais recentes, não importava a pergunta. Corrigido baixando `k` para 10 e dando um piso de 50% ao decaimento (nunca deixa a recência sozinha vencer relevância nenhuma).
2. **BM25 sem correspondência nenhuma ainda "ranqueia".** Quando nenhum termo da consulta aparece em nenhum documento, `BM25Okapi.get_scores` devolve zero para todo mundo — e ordenar uma lista de zeros produz uma ordem baseada só na posição de entrada, não em relevância nenhuma. Essa ordem falsa entrava na fusão RRF como se fosse um sinal de verdade, e podia vencer o ranking dado (genuíno) da busca densa. Pego rodando o RAG sobre a bíblia: uma pergunta sobre chuva ("Está chovendo, eu me abrigo embaixo da árvore") não compartilha nenhuma palavra literal com a seção de clima (que fala em "chuva", não "chovendo") e a seção de combate vencia por estar em primeiro na lista de entrada. Corrigido: `busca_lexica` devolve `[]` (não uma ordem) quando o score máximo é zero — ver `tests/test_hybrid_search.py::TestBuscaLexica::test_query_sem_nenhum_termo_em_comum_devolve_vazio_em_vez_de_ordem_falsa`.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| `sqlite-vec` (extensão nativa, tabela virtual `vec0`) | mais fiel ao roadmap original; mesma família de API que `pgvector` (a migração para produção seria mais direta) | carregar extensão nativa via `enable_load_extension`/`sqlite_vec.load` em cada conexão, inclusive em teste/CI; mais um ponto de fragilidade multiplataforma (Windows local + Ubuntu no CI) | a própria seção 4.4 do roadmap já admite que a escala não exige isso; Python puro entrega o mesmo recall (ver números abaixo) sem o risco de infraestrutura |
| `sentence-transformers` (PyTorch) | citado no roadmap; reforça a progressão com o Sinapse (mesma ferramenta usada lá) | traz PyTorch como dependência — deixa `uv sync` e o CI sensivelmente mais lentos, para um ganho que `fastembed` entrega igual | custo de CI não compensa o valor de repetir exatamente a mesma lib; a *técnica* (embeddings locais, busca híbrida) é o que importa para a tese, não o nome do pacote |
| Só busca densa (sem BM25) | mais simples, um caminho só | erra nome próprio, exatamente o caso mais comum num RPG (nomes de NPC, item, local inventados) — visto na prática nos dois bugs acima e no par adversarial do `memory_recall.py` (ver números) | motivou o ADR inteiro |
| Só BM25 (sem embedding) | mais simples, zero dependência de ML | não generaliza paráfrase — "o taverneiro" e "o dono da taverna" não batem léxico nenhum | perde exatamente o caso que a Etapa 2 do roadmap (`get_relevant_rules` nunca filtrado) já sinalizava como necessário |

## Consequências

**Ganhamos:**
- `recall@1` medido em `scripts/memory_recall.py` (15 eventos sintéticos + 2 adversariais, 6 consultas com resposta certa conhecida): **50% denso puro → 83% híbrido**. O caso que a busca densa mais erra: perguntas sobre um NPC específico quando existem vários eventos parecidos sobre ele em turnos diferentes (a densa reconhece "o tema" mas não desempata por quem exatamente é citado).
- RAG sobre a bíblia: a seção certa (clima, combate ou consequência social) é recuperada corretamente para consultas de teste — incluindo o caso que o bug #2 acima quebrava antes da correção.
- `tests/test_hybrid_search.py` cobre BM25 isolado, cosseno isolado, fusão RRF, decaimento e os dois bugs, tudo com um `embed_fn` falso e determinístico — 100% de cobertura em `hybrid_search.py`, zero rede nos testes (embeddings reais só rodam em `scripts/memory_recall.py`, fora do CI).

**Pagamos:**
- Busca em Python puro é O(n) por query — ok para centenas de eventos por personagem, não pensado para escala maior sem revisão (ver ADR-0009, "Fica em aberto").
- `fastembed` ainda baixa ~220MB na primeira execução (modelo do Hugging Face) — não é zero-dependência de rede, só zero rede *por turno* depois do primeiro carregamento.
- O piso de 50% no decaimento por recência é um número escolhido por observação (o comportamento antes/depois no `memory_recall.py`), não derivado de um princípio — pode precisar de ajuste com mais dado real.

**Fica em aberto:**
- Migrar para `pgvector` (Neon, produção — Etapa 9) exigirá reescrever `busca_densa`/armazenamento (a interface `Documento`/`buscar` foi desenhada para isso ser uma troca de implementação, não uma reescrita de quem chama).
- Ajustar `meia_vida`/`piso` do decaimento com dado de partidas reais, não só o cenário sintético.

## Como saber que erramos

Se o volume de eventos por personagem crescer a ponto da busca O(n) em Python virar gargalo de latência perceptível por turno, ou se `recall@k` medido em partidas reais (não sintéticas) ficar consistentemente abaixo do que a busca densa pura já entregava sozinha, revisar a fusão (pesos, `k` do RRF) antes de trocar de tecnologia de armazenamento.

## Referências

- `PLANO_MESTRE.md`, Etapa 5 — "busca híbrida BM25 + densa, fusão RRF, decaimento por recência, RAG sobre regras".
- `ROADMAP_PORTFOLIO.md`, Fase 2, §4.4 — a análise original que já apontava que um banco vetorial dedicado não se justifica na escala do projeto.
- [Reciprocal Rank Fusion outperforms Condorcet and individual rank learning methods](https://plg.uwaterloo.ca/~gvcormac/cormacksigir09-rrf.pdf) (Cormack, Clarke, Büttcher, 2009) — o paper original do RRF, origem do `k=60` que se mostrou grande demais para este corpus.
- [`fastembed`](https://github.com/qdrant/fastembed) — biblioteca de embeddings via ONNX Runtime.
- [`rank-bm25`](https://github.com/dorianbrown/rank_bm25) — implementação de BM25Okapi usada.
- ADR-0009 — a camada de memória de longo prazo que consome esta busca.
