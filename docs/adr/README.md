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
| 0006 | **O LLM não é o motor de regras** | 3 | 🕓 previsto | — |
| 0007 | Tool calling em vez de JSON solto | 4 | 🕓 previsto | — |
| 0008 | Cadeia de fallback entre provedores de LLM | 4 | 🕓 previsto | — |
| 0009 | Memória hierárquica em três camadas | 5 | 🕓 previsto | — |
| 0010 | Busca híbrida BM25 + densa com fusão RRF | 5 | 🕓 previsto | — |
| 0011 | Estratégia de avaliação: determinístico + julgado | 6 | 🕓 previsto | — |
| 0012 | SSE em vez de WebSocket ou polling | 7 | 🕓 previsto | — |
| 0013 | TanStack Query para estado de servidor | 7 | 🕓 previsto | — |
| 0014 | Autenticação por e-mail mágico, implementada à mão | 8 | 🕓 previsto | — |
| 0015 | Escolha de hospedagem | 9 | 🕓 previsto | — |

**Legenda:** 🕓 previsto · ✅ aceito · ⛔ substituído

> A numeração acima é uma **previsão**, não um contrato. Decisões que aparecerem no caminho entram na sequência real; as previstas que se mostrarem desnecessárias simplesmente não nascem, e a lacuna no número fica como registro. Nunca renumere um ADR já escrito.

## Decisões já tomadas sem ADR

Registradas em [`../../PLANO_MESTRE.md`](../../PLANO_MESTRE.md) §4.4, ainda como intenção. Viram ADR quando forem implementadas:

- **Não usar Next.js** — backend é Python; o produto não tem SEO nem SSR a ganhar
- **Não usar LangChain / LlamaIndex** — esconderiam exatamente o que o projeto existe para demonstrar
- **Não usar banco vetorial dedicado** — `sqlite-vec` e `pgvector` bastam nesta escala
- **Não usar Kubernetes / microserviços** — monólito bem estruturado é a arquitetura correta para este tamanho
- **Não usar serviço de auth gerenciado** — e-mail mágico à mão é ~150 linhas e não tem hash de senha a errar

## Decisões de escopo

Tomadas em 18/08/2026 e registradas em [`../../PLANO_MESTRE.md`](../../PLANO_MESTRE.md) §9. Não são ADRs porque são decisões de *produto*, não de arquitetura — mas restringem várias das decisões acima:

- **Contas com múltiplos personagens** (não sessão anônima) → força o schema `usuario (1:N) personagem` já na Etapa 2
- **D&D 5e enxuto** (não sistema próprio) → dá referência externa de correção ao golden dataset da Etapa 6
- **Single-player** (multiplayer fora do plano, sem prazo) → o motor da Etapa 3 é um herói contra N inimigos
