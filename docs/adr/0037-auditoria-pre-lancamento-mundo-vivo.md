# ADR-0037 — Auditoria pré-lançamento: dupla guarda em ferramentas e orçamento de tokens como limite de sanidade, não de cobrança

**Data:** 15/09/2026
**Status:** Aceito
**Etapa:** Auditoria pré-lançamento da Fase 1 ("Mundo Vivo") do plano "jogo completo" (ver diário 0038)

---

## Contexto

A Fase 1 do plano "jogo completo" (economia, instalações, organizações, projetos,
emergência, imersão) chegou ao fim do desenvolvimento ainda não commitada. Antes de
integrar esse volume de trabalho, uma auditoria pré-lançamento revisou o conjunto —
backend, frontend e operação — em busca de bugs e riscos que só aparecem quando várias
fases somam código, não numa fase isolada. Dois achados no backend são estruturais o
bastante para virar decisão registrada, não só um commit de correção:

1. **Uma ferramenta que muta o save pode ficar disponível ao narrador durante combate.**
   `app/services/tools.py` mantém `_SO_FORA_DE_COMBATE`, um conjunto de nomes de
   ferramentas que `tools_para()` esconde do narrador quando `c_state.ativo`. Todas as
   ferramentas mutantes da Fase 0 (`registrar_cena`, `registrar_conflito`,
   `propor_aprendizado`...) estão nesse conjunto. As nove ferramentas equivalentes da
   Fase 1 (`despachar_remessa`, `propor_instalacao`, `registrar_organizacao`,
   `mobilizar_organizacao`, `planejar_projeto`, `registrar_avanco_projeto`,
   `propor_acordo_projeto`, `cumprir_acordo_projeto`, `apresentar_oportunidades`) não
   estavam. Como `tools_para()` também ativa grupos de ferramentas por palavra-gatilho no
   texto do jogador (`gatilhos`, mesmo arquivo — ex. "organizacao", "projeto", "acordo"),
   uma frase de combate que colidisse com um desses gatilhos oferecia a ferramenta ao
   narrador mesmo em combate. Das nove, quatro (`planejar_projeto`,
   `registrar_avanco_projeto`, `cumprir_acordo_projeto`, `apresentar_oportunidades`)
   também não tinham a guarda interna `c_state.ativo`/`hp_atual <= 0` que as outras cinco
   já tinham por conta própria — ou seja, para essas quatro, não havia nenhuma linha de
   defesa.
2. **O teto local de tokens (`agent_limite_entrada_estimado`) não é o mesmo teto da Groq.**
   `OrcamentoTurno.registrar` (`app/services/orcamento_ia.py`) usa uma régua de
   `chars/3` para estimar tokens e bloquear a chamada antes de sair para o provedor. A
   contagem real da Groq (medida ao vivo, ver diário 0026) fica mais perto de `chars/4` —
   ou seja, a régua interna já é conservadora (superestima), mas o número absoluto do
   teto (12000) foi calibrado para caber o schema COMPLETO de ferramentas (51, sem
   filtro), um cenário que só acontece em teste (quando uma chamada não passa
   `tools=tools_para(...)` explicitamente), não em produção.

Nenhum dos dois é um bug de lógica de jogo isolado — os dois são sobre o que acontece
quando peças que se comportam bem sozinhas (cada ferramenta nova, cada `gatilho` novo)
se somam sem ninguém comparar contra o padrão já estabelecido pela fase anterior.

## Decisão

1. **Toda ferramenta que muta `w_state.mundo` fora de um fluxo exclusivo do jogador
   (`_NUNCA_PARA_O_NARRADOR`) entra em `_SO_FORA_DE_COMBATE`, sem exceção — e também
   carrega sua própria guarda `c_state.ativo`/`hp_atual <= 0` internamente.** As duas
   camadas não são redundantes: o filtro em `tools_para()` decide o que o narrador *vê*;
   a guarda interna decide o que a ferramenta *faz* se for chamada de qualquer jeito (um
   caminho futuro que ignore `tools_para` — outro `chamar_fn`, um teste, uma chamada
   direta — não pode reintroduzir a mesma falha). Checklist para toda ferramenta nova que
   mute estado: (a) está em `_SO_FORA_DE_COMBATE`? (b) tem a guarda interna? Nenhuma das
   duas perguntas substitui a outra.
2. **`agent_limite_entrada_estimado`/`agent_limite_turno_estimado` continuam sendo um
   limite de sanidade local (evitar um schema patologicamente grande, como o completo sem
   filtro), não uma substituição da medição real contra o provedor.** Não reduzimos os
   números para "proteger" contra o teto real da Groq — fizemos a conta (ver diário 0038)
   e reduzir o suficiente para fechar essa margem quebra o cenário de teste do schema
   completo sem trazer proteção real proporcional (o risco real está concentrado em
   quantos `gatilhos` disparam ao mesmo tempo, não no teto absoluto). A proteção de
   verdade contra o teto de 8000 tokens/minuto da Groq continua sendo manter
   `tools_para()` enxuto por turno: `_CAMPOS_DO_SERVIDOR` (campos que o servidor sempre
   sobrescreve, fora do schema do modelo) e `gatilhos` (só ativa o grupo de ferramentas
   que o texto do jogador realmente sugere) precisam ser revisados toda vez que um grupo
   de ferramentas novo entra — o mesmo processo que o diário 0026 já descrevia, agora
   também documentado aqui como regra permanente, não só um relato da vez em que doeu.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Reduzir `agent_limite_entrada_estimado` para caber com folga no teto real | Fecha a lacuna teórica entre estimativa e teto real numa linha só | Quebra ~20 testes de `agent_loop` que chamam `executar_turno` sem passar `tools=` (usam o default `TOOLS_SCHEMA` completo, só de conveniência de teste); a folga real só importa para o caso raro de muitos `gatilhos` disparando juntos, já coberto pelo item 2 | O custo (reescrever ~20 call sites de teste) não compra proteção proporcional; o risco real está em `tools_para`, não no teto absoluto |
| Um único guard genérico (`_mutante(nome)`) decidido por convenção de nome em vez de dois conjuntos explícitos | Menos código para manter | Convenção de nome é frágil (uma ferramenta chamada `atualizar_x` pode ou não mutar; a Fase 1 já tem `usar_instalacao`, que muta mas é exclusiva do jogador) | Explícito (dois conjuntos, checklist manual) é mais fácil de auditar numa revisão futura do que implícito |
| Confiar só na guarda interna de cada ferramenta, sem o filtro em `tools_para` | Uma única fonte de verdade | O narrador ainda "vê" a ferramenta e pode tentar chamá-la em combate, gastando uma rodada do agente com um erro previsível em vez de nunca oferecer a opção | Esconder é mais barato em tokens (a ferramenta nem entra no schema) e mais claro para o modelo do que oferecer e recusar |

## Consequências

**Ganhamos:** as nove ferramentas da Fase 1 seguem exatamente a mesma regra de
combate-bloqueia-mutação que a Fase 0 já tinha; um checklist explícito (dois conjuntos,
não convenção implícita) para a próxima fase que adicionar ferramentas mutantes; clareza
documentada de que o teto local não é uma promessa de nunca estourar o teto real — quem
lê `settings.py` não deveria concluir isso sozinho.

**Pagamos:** nada em runtime — as mudanças desta rodada são estritamente mais
restritivas (menos ferramentas visíveis em combate, mensagens de erro genéricas em vez
do texto cru da exceção) ou neutras em comportamento (schema mais enxuto, mesmos
resultados). O custo é de processo: toda fase futura que adiciona ferramentas ao Mundo
Vivo precisa repetir o checklist do item 1 e a revisão de `_CAMPOS_DO_SERVIDOR`/
`gatilhos` do item 2 — não há automação que force isso hoje (fica como item de backlog:
um teste que compare `GRUPOS_FERRAMENTAS` contra `_SO_FORA_DE_COMBATE`/
`_NUNCA_PARA_O_NARRADOR` e falhe se uma ferramenta mutante ficar de fora dos dois).

**Fica em aberto:** a medição real contra a API da Groq (não a estimativa offline) para
o cenário multi-`gatilho` desta auditoria ainda não foi refeita ao vivo — custa cota
real, e o diário 0038 explica por que a estimativa offline já dá confiança suficiente
para não bloquear esta rodada nisso.

## Como saber que erramos

- Se uma ferramenta nova do Mundo Vivo aparecer disponível durante combate numa sessão
  real (não só em teste), o checklist do item 1 não está sendo seguido — vale automatizar
  a checagem em vez de confiar em revisão manual.
- Se a Groq continuar devolvendo 429 num turno que passou pelo guard-rail local mesmo
  depois desta rodada, o item 2 está errado: a régua `chars/3` não é conservadora o
  suficiente para o texto real do jogo, e `agent_limite_entrada_estimado` precisa cair de
  verdade, mesmo que isso exija reescrever os testes que dependem do schema completo.

## Referências

- Diário 0026 — mundo vivo e fim dos atos (a medição original de `chars/turno` que esta
  auditoria repetiu)
- Diário 0038 — auditoria pré-lançamento (o relato desta rodada, em linguagem simples)
- `app/services/tools.py` (`_SO_FORA_DE_COMBATE`, `_NUNCA_PARA_O_NARRADOR`, `gatilhos`,
  `tools_para`)
- `app/services/orcamento_ia.py` (`OrcamentoTurno`), `app/infra/settings.py`
  (`agent_limite_entrada_estimado`, `agent_limite_turno_estimado`)
