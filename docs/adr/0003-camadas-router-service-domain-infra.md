# ADR-0003 — Separar o backend em router / service / domain / infra

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 2
**Supersede:** —

---

## Contexto

Antes desta etapa, `Backend/api.py` tinha 291 linhas e fazia tudo: definia as rotas HTTP, chamava a Groq, validava point-buy, montava o prompt do prólogo, e acessava o banco diretamente — sem uma linha de separação entre essas responsabilidades. Enquanto o projeto tinha três rotas (`create_character`, `load_game`, `chat`), isso era administrável. Mas as Etapas 3 e 4 do `PLANO_MESTRE.md` vão adicionar um motor de regras determinístico (dados, combate, iniciativa) e tool calling (múltiplas ferramentas tipadas, loop de agente, guardrails de estado) — código que, misturado num único arquivo, deixaria de caber na cabeça de quem lê.

O sintoma concreto que forçou a decisão: para adicionar a revalidação de atributos na Etapa 1 (`ADR-0002`), a lógica de regra (constantes de point-buy, cálculo de modificador) já tinha que conviver no mesmo arquivo que a definição das rotas FastAPI e a chamada à Groq — três preocupações diferentes, sem fronteira nenhuma entre elas.

## Decisão

`Backend/api.py` vira o pacote `Backend/app/`, com quatro camadas de responsabilidade única:

- **`routers/`** — só HTTP. Recebe a requisição (já validada pelos modelos de `domain/`), chama uma função de `services/`, devolve a resposta. Não conhece Groq, não conhece SQL cru.
- **`services/`** — a lógica de negócio: `narrator.py` (fala com o LLM), `rules_engine.py` (determinístico, zero I/O — a base do motor de regras da Etapa 3), `memory.py` (hoje só o slice das últimas mensagens — a base da Etapa 5).
- **`domain/`** — os modelos Pydantic que definem a forma do estado do jogo: o que o cliente pode propor (`character.py`) e como o estado do mundo/combate/missão é tipado (`state.py`), em vez de dicionários soltos passados de função em função.
- **`infra/`** — tudo que fala com o mundo externo: banco (`db.py`, SQLAlchemy 2.0 tipado), config (`settings.py`, `pydantic-settings`), o client da Groq (`llm_client.py`), e o carregador dos JSONs de regras (`data_manager.py`).

A regra de dependência é de fora para dentro: `routers` pode importar de `services`/`domain`/`infra`; `services` pode importar de `domain`/`infra`; `domain` não importa de `services` nem de `infra` (com uma exceção pragmática registrada abaixo). Nenhum arquivo passa de ~150 linhas.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Manter um único `api.py`, só quebrado em funções | menor esforço imediato | não resolve o problema real: tudo continua importável e chamável de qualquer lugar, sem fronteira que o Python force | a Etapa 3 triplicaria esse arquivo; o problema só cresceria |
| Arquitetura hexagonal completa (ports & adapters, interfaces abstratas para cada dependência externa) | máximo desacoplamento, troca de banco/LLM sem tocar no domínio | overhead de abstração que este projeto — um monólito de um herói, sem múltiplos adaptadores concorrentes — não paga de volta | contraria a "regra anti-escopo" do próprio `PLANO_MESTRE.md` (§7): a complexidade tem que servir a uma métrica ou ao jogador, e interfaces abstratas para um único provedor de LLM não servem a nenhum dos dois hoje |
| Separar por feature (`create_character/`, `chat/`, cada um com seu router+service+domain) | escala bem quando features não compartilham nada | as três rotas de hoje compartilham quase tudo (o mesmo `Personagem`, a mesma `regras`, o mesmo `chamar_mestre`) — feature-first criaria import cruzado entre "features" desde o primeiro dia | prematuro: a divisão por camada é a que reflete o que o código realmente compartilha agora |

## Consequências

**Ganhamos:**
- cada arquivo tem uma pergunta que ele sozinho responde ("isso é HTTP?", "isso é regra?", "isso fala com o banco?") — o teste de "onde eu mexo para consertar X" fica mecânico
- `rules_engine.py` já nasce com zero I/O e zero LLM, exatamente o formato que a Etapa 3 ("O Juiz") exige — não é preciso extrair depois
- `domain/state.py` tipa `world_state`/`combat_state`/`quest_log`, que antes eram dicionários sem forma garantida — um erro de chave (`c_state.get("ativo")` vs `c_state.get("ativa")`) agora é pego pelo mypy, não em produção

**Pagamos:**
- `domain/character.py` importa de `services/rules_engine.py` (para `validar_point_buy` e as constantes de point-buy) — quebra a regra de dependência "de fora para dentro" que o resto do pacote segue. É uma concessão deliberada: a validação de point-buy é regra de D&D pura (zero I/O), então mora em `rules_engine.py` por afinidade de conteúdo, mesmo sendo consumida por um `field_validator` do domínio. Se isso se repetir em mais lugares, é sinal de que essas constantes deveriam estar em `domain/` desde o início.
- mais arquivos para navegar — abrir um IDE sem "ir para definição" fica mais lento que quando era um `api.py` só

**Fica em aberto:**
- `services/memory.py` e `services/rules_engine.py` hoje são esqueletos (um slice de lista, quatro funções). Eles só se justificam de verdade quando as Etapas 3 e 5 os preencherem — até lá, é fé de que a forma está certa, não prova.

## Como saber que erramos

Se, ao implementar a Etapa 3 (motor de regras) ou a Etapa 4 (tool calling), a divisão atual de `services/` precisar ser desfeita — por exemplo, se `rules_engine.py` precisar chamar `narrator.py` diretamente, ou se um router precisar importar de outro router — é sinal de que a fronteira foi traçada no lugar errado, e vale revisar antes de continuar empilhando código em cima dela.

## Referências

- [FastAPI — Bigger Applications, Multiple Files](https://fastapi.tiangolo.com/tutorial/bigger-applications/) — o padrão de `APIRouter` usado em `routers/`
- `PLANO_MESTRE.md`, Etapa 2 — a estrutura de diretório-alvo que este ADR implementa
