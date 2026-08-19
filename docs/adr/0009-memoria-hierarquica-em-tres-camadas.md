# ADR-0009 — Memória em três camadas: curto, médio e longo prazo

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 5
**Supersede:** —

---

## Contexto

Desde a Etapa 1, `services/memory.py:contexto_recente` corta o histórico de conversa nas últimas 4 mensagens (`historico_chat[-4:]`) antes de montar o prompt (`routers/game.py:chat_endpoint`). É o único mecanismo de memória que existe: o que saiu da janela desaparece de vez. Um NPC ofendido no turno 5 não tem como ser lembrado no turno 60 — não há registro nenhum do evento fora da janela, e a janela nunca cresce.

O custo de simplesmente aumentar `n` em `contexto_recente` é linear em tokens (e em custo, e em latência) e não resolve o problema de fundo: mesmo uma janela de 50 mensagens ainda esquece o que aconteceu na mensagem 51. A pergunta não é "quantas mensagens crua guardar", é "como decidir o que vale a pena lembrar, e por quanto tempo".

## Decisão

Três camadas, cada uma resolvendo um prazo diferente:

1. **Curto prazo** (sem mudança) — `contexto_recente`, as últimas N mensagens cruas.
2. **Médio prazo** (`services/memory.py:atualizar_resumo_rolante`) — a cada `k_turnos` (8 por padrão) que saem da janela curta, um modelo comprime essa fatia em quatro listas estruturadas (`domain/memoria.py:ResumoRolante`: `fatos_estabelecidos`, `npcs_conhecidos`, `promessas_feitas`, `mudancas_no_mundo`), mescladas ao resumo já acumulado (`Personagem.resumo_rolante`, coluna JSON). Usa o modelo mais barato da cadeia de fallback (`settings.modelos_fallback[-1]`, via `llm_client.chamar_modelo_unico`) — comprimir texto não precisa da qualidade do modelo principal, e uma falha aqui não derruba o turno: o resumo antigo continua valendo, sem retry automático (a próxima chamada, com uma janela maior, tenta de novo).
3. **Longo prazo** (`services/memory.py:registrar_evento` / `memorias_relevantes`) — cada turno vira uma linha em `EventoMemoria` (`turno`, `tipo`, `texto`, `personagens_citados`, `embedding`), recuperável por busca híbrida (ver ADR-0010) filtrada sempre por `personagem_id` — nunca vaza memória entre personagens/sessões diferentes, o filtro acontece na query, antes de qualquer busca.

`routers/game.py:chat_endpoint` monta as três camadas antes de cada turno (curto prazo cru, memórias relevantes recuperadas, resumo estruturado acumulado) e persiste a camada de longo prazo depois — nunca no meio do processamento do turno.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Só aumentar a janela curta (`n` maior em `contexto_recente`) | zero código novo | custo/latência cresce linear com o tamanho da partida; ainda esquece tudo fora da janela, só empurra o problema | não resolve memória de longo prazo, só adia |
| Resumo em texto solto (um parágrafo, não campos estruturados) | mais simples de gerar | o narrador não consegue citar um fato específico sem reinterpretar um parágrafo inteiro a cada turno; pior para o guardrail (`services/guardrail.py`) conferir contradição | campos estruturados custam pouco a mais e valem muito mais na hora de usar |
| Registrar TODO evento relevante manualmente, via uma ferramenta nova que o modelo chama (`registrar_memoria(texto)`) | controle fino do que vira memória | mais uma ferramenta para o modelo decidir usar (ver os três casos documentados no diário da Etapa 4 de "narrou sem chamar a ferramenta") — arriscar perder memória exatamente pelo mesmo motivo que perdíamos movimento/item | o servidor já sabe o suficiente (ação do jogador + narrativa) para registrar automaticamente, sem depender do modelo lembrar de chamar mais uma ferramenta |

## Consequências

**Ganhamos:**
- Um NPC pode ser referenciado por eventos de dezenas de turnos atrás — testado com `scripts/memory_recall.py` (ver ADR-0010 para os números de recall) e ao vivo (ver diário desta etapa).
- Falha no resumo rolante (erro de API, JSON inválido) não derruba o turno — `atualizar_resumo_rolante` devolve `False` e o resumo antigo continua no banco, coberto por `tests/test_memory.py::TestAtualizarResumoRolante::test_falha_do_modelo_nao_derruba_e_preserva_resumo_antigo`.
- Registrar um evento por turno é automático (`routers/game.py`), não depende do modelo lembrar de chamar uma ferramenta — elimina a classe de bug "esqueceu de registrar" que apareceu três vezes na Etapa 4 para outras ferramentas.

**Pagamos:**
- Um embedding a mais por turno (a ação do jogador, para buscar memórias relevantes) e outro depois (o evento que acabou de acontecer, para registrar) — dois cálculos de embedding local por turno, além do já existente para o RAG de regras (ADR-0010). Latência medida: ver diário.
- `EventoMemoria` cresce sem limite dentro de uma partida — não existe expiração/poda ainda. Para o volume de uma sessão single-player (centenas de eventos, não milhões), a busca em Python puro (ADR-0010) ainda é rápida o bastante; não é uma solução que escala para milhares de sessões simultâneas sem revisão.
- O resumo rolante mescla por igualdade de string (`_mesclar`, dedupe exato) — duas frases que dizem a mesma coisa com palavras diferentes viram duas entradas na lista. Aceitável no volume atual (dezenas de itens por lista, não centenas).

**Fica em aberto:**
- Poda/expiração de eventos muito antigos e de baixa relevância, se uma partida ficar longa o bastante para o volume importar.
- O resumo rolante hoje só cresce (concatena e deduplica) — nunca reescreve/resume o que já está lá. Se a lista de `fatos_estabelecidos` ficar muito longa, vale considerar uma segunda camada de compressão (resumir o resumo).
- **O resumo rolante pode divergir do estado real** — visto ao vivo nesta etapa: depois de um pedido de desculpas ao NPC Grum, o resumo gerado registrou em `mudancas_no_mundo` que "reputação com Grum recuperou +2 pontos", mas a coluna `reputacao_npcs` (a fonte de verdade, escrita só pela ferramenta `ajustar_reputacao_npc`) continuava em -5 — o modelo que resume inventou uma mudança que a ferramenta nunca aplicou. O guardrail (`services/guardrail.py`, Etapa 4) confere a narrativa do turno contra o estado; não confere o resumo rolante contra nada. É a mesma classe de risco que motivou o guardrail, só que numa camada nova que ainda não tem rede de segurança nenhuma.

## Achados ao vivo (não fica em aberto — já testado)

Testado com o servidor rodando de verdade, chave da Groq real, sem mock nenhum (ver diário): um personagem insultou o taverneiro Grum no turno 2; seis turnos depois (fora da janela de curto prazo, `n=4`), perguntado se Grum ainda estava bravo, a narrativa referenciou corretamente o insulto ("ainda sinto o eco das palavras duras... a confiança leva tempo pra se curar") — a memória de longo prazo influenciou a narração de forma perceptível, não só em teste sintético.

## Como saber que erramos

Se, medindo o recall@k em partidas reais (não só no `scripts/memory_recall.py` sintético), a memória de longo prazo raramente influenciar a narrativa de forma perceptível — ou se o custo de embedding por turno se tornar o gargalo de latência dominante — o design de "um evento por turno, sempre" deveria virar "só eventos que passam por um filtro de relevância mínima antes de gravar".

## Referências

- `PLANO_MESTRE.md`, Etapa 5 ("A memória") — a especificação original das três camadas.
- `aprender/lessons/0006-embeddings-similaridade-e-recall.html` — o que é um embedding e como se mede recall@k.
- [ADR-0010](0010-busca-hibrida-bm25-mais-densa-e-por-que-nao-sqlite-vec.md) — como a camada de longo prazo é buscada.
