# Índice de decisões (ADRs)

Registro imutável das decisões de arquitetura do Mestre.IA. Cada linha aponta para a decisão, não para o resumo dela — leia o arquivo antes de discordar.

Template: [`0000-template.md`](0000-template.md) · Sistema completo: [`../README.md`](../README.md)

| # | Decisão | Etapa | Status | Data |
|---|---|---|---|---|
| [0001](0001-uv-para-dependencias.md) | Gerenciar dependências com `uv` em vez de pip + venv | 0 | ✅ aceito | 19/08/2026 |
| [0002](0002-revalidacao-servidor.md) | Revalidar as regras de criação de personagem no servidor | 1 | ✅ aceito | 19/08/2026 |
| [0003](0003-camadas-router-service-domain-infra.md) | Separar o backend em router / service / domain / infra | 2 | ✅ aceito | 19/08/2026 |
| [0004](0004-alembic-para-migrations.md) | Adotar Alembic para migrations | 2 | ✅ aceito | 19/08/2026 |
| [0005](0005-usuario-personagem-antes-do-login.md) | Modelo de dados usuário × personagem, antes da tela de login | 2 | ✅ aceito | 19/08/2026 |
| [0006](0006-llm-nao-e-motor-de-regras.md) | **O LLM não é o motor de regras** | 3 | ✅ aceito | 19/08/2026 |
| [0007](0007-tool-calling-em-vez-de-json-solto.md) | Tool calling em vez de JSON solto | 4 | ✅ aceito | 19/08/2026 |
| [0008](0008-cadeia-de-fallback-de-modelo.md) | Cadeia de fallback entre modelos da Groq | 4 | ✅ aceito | 19/08/2026 |
| [0009](0009-memoria-hierarquica-em-tres-camadas.md) | Memória hierárquica em três camadas | 5 | ✅ aceito | 19/08/2026 |
| [0010](0010-busca-hibrida-bm25-mais-densa-e-por-que-nao-sqlite-vec.md) | Busca híbrida BM25 + densa com fusão RRF | 5 | ✅ aceito | 19/08/2026 |
| [0011](0011-estrategia-de-avaliacao.md) | Estratégia de avaliação: determinístico + julgado, gate manual | 6 | ✅ aceito | 20/08/2026 |
| [0012](0012-sse-em-vez-de-websocket-ou-polling.md) | SSE em vez de WebSocket ou polling, fallback só antes do 1º chunk | 7 | ✅ aceito | 21/08/2026 |
| [0013](0013-tanstack-query-em-vez-de-redux.md) | TanStack Query para estado de servidor | 7 | ✅ aceito | 21/08/2026 |
| [0014](0014-senha-com-google-opcional.md) | Login por senha (PBKDF2) com Google OAuth opcional, cookie assinado à mão | 8 | ✅ aceito | 22/08/2026 |
| [0015](0015-hospedagem-fly-vercel-neon.md) | Hospedagem: Fly.io + Vercel + Neon, proxy em vez de cookie cross-site | 9 | ✅ aceito | 22/08/2026 |
| [0016](0016-convidado-e-confirmacao-de-email-bloqueante.md) | Convidado como `Usuario` sem e-mail; confirmação de e-mail bloqueante | 10 | ✅ aceito | 22/08/2026 |
| [0017](0017-identidade-visual-pixel-art-rota-2.md) | Identidade visual 8-bit: Rota 2 (sprites reais), fonte única CC0 | 11 | ⚠️ parcialmente superseded por [0025](0025-retratos-por-ia-pixelizados-por-script.md) | 23/08/2026 |
| [0021](0021-sistema-de-componentes-pixel-ui.md) | Sistema de componentes pixel (PanelFrame, PixelButton, PixelIcon) | 14 | ✅ aceito | 24/08/2026 |
| [0022](0022-hospedagem-render-em-vez-de-fly-io.md) | Hospedagem do backend: Render.com em vez de Fly.io | 14 | ✅ aceito | 24/08/2026 |
| [0023](0023-embeddings-via-api-gemini.md) | Embeddings via API (Gemini) em vez de modelo local (`fastembed`) | 14 | ✅ aceito | 24/08/2026 |
| [0024](0024-cadeia-multi-provedor-groq-gemini.md) | Cadeia de fallback atravessando provedores (Groq + Gemini) | 14 | ✅ aceito | 24/08/2026 |
| [0025](0025-retratos-por-ia-pixelizados-por-script.md) | Retratos de raça/classe: sprites CC0 do Dungeon Crawl | 14 | ✅ aceito | 24/08/2026 |
| [0026](0026-curva-de-xp-propria-e-escalonamento-de-perigo.md) | Curva de XP própria, XP fora de combate e escalonamento de perigo pelo servidor | Revisão de gameplay (Fase 0) | ✅ aceito | 25/08/2026 |
| [0027](0027-companheiros-mecanicos-revisao-do-9-3.md) | Companheiros mecânicos: revisão parcial do §9.3 (single-player) | Revisão de gameplay (Fase 2) | ✅ aceito | 25/08/2026 |
| [0028](0028-locais-inventados-revisao-da-validacao-fechada-de-mover.md) | Locais inventados: revisão da validação fechada de `mover` | Revisão de gameplay (Fase 5) | ✅ aceito | 25/08/2026 |
| [0029](0029-pele-e-ficha-separadas.md) | Pele e ficha separadas: nome do monstro/local inicial deixam de estar presos à ficha | Rodada de conserto (Parte 2, item J) | ✅ aceito | 26/08/2026 |
| [0030](0030-excluir-personagem-de-verdade-em-vez-de-arquivar.md) | Excluir personagem apaga a linha de verdade, não só marca `arquivado` | Polimento de UX pós-lançamento (Home/Login) | ✅ aceito | 26/08/2026 |

**Legenda:** 🕓 previsto · ✅ aceito · ⛔ substituído

> A numeração acima é uma **previsão**, não um contrato. Decisões que aparecerem no caminho entram na sequência real; as previstas que se mostrarem desnecessárias simplesmente não nascem, e a lacuna no número fica como registro. Nunca renumere um ADR já escrito.
>
> A lacuna entre 0017 e 0021 (0018-0020) era a numeração prevista pelo antigo `docs/backlog-pos-lancamento.md` para as Etapas 12a/13/12b — nenhuma das duas etapas rodou, então esses ADRs nunca nasceram. A revisão de gameplay que os substitui começa em **0026** (ver a nota no topo do backlog).

## Decisões já tomadas sem ADR

Registradas em [`../../PLANO_MESTRE.md`](../../PLANO_MESTRE.md) §4.4, ainda como intenção. Viram ADR quando forem implementadas:

- **Não usar Next.js** — backend é Python; o produto não tem SEO nem SSR a ganhar
- **Não usar LangChain / LlamaIndex** — esconderiam exatamente o que o projeto existe para demonstrar
- **Não usar banco vetorial dedicado** — `sqlite-vec` e `pgvector` bastam nesta escala
- **Não usar Kubernetes / microserviços** — monólito bem estruturado é a arquitetura correta para este tamanho
- **Não usar serviço de auth gerenciado** — login por senha + Google à mão é pequeno o bastante para não justificar mais uma conta, mais um SDK e mais um provedor no diagrama (ver ADR-0014)

## Decisões de escopo

Tomadas em 18/08/2026 e registradas em [`../../PLANO_MESTRE.md`](../../PLANO_MESTRE.md) §9. Não são ADRs porque são decisões de *produto*, não de arquitetura — mas restringem várias das decisões acima:

- **Contas com múltiplos personagens** (não sessão anônima) → força o schema `usuario (1:N) personagem` já na Etapa 2
- **D&D 5e enxuto** (não sistema próprio) → dá referência externa de correção ao golden dataset da Etapa 6
- **Single-player** (multiplayer fora do plano, sem prazo) → o motor da Etapa 3 é um herói contra N inimigos
