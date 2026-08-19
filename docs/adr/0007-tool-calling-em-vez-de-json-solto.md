# ADR-0007 — Trocar `comando_combate`/`spawn_battle` em JSON solto por tool calling nativo

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 4
**Supersede:** —

---

## Contexto

Desde a Etapa 3 (ADR-0006), o modelo continuava escrevendo a intenção do jogador dentro do mesmo JSON da narrativa — `comando_combate: {"tipo": "atacar", "arma": "...", "alvo": "..."}` para combate, `spawn_battle`/`inimigos_sugeridos` para iniciar um confronto. O próprio ADR-0006 já registrava isso como provisório: "dois juízes convivem por uma etapa" — o schema era confiado por convenção de nome de campo (`services/narrator.py:34`, `response_format={"type": "json_object"}`), nunca validado contra um schema de verdade, e `services/combat.py` confirmava a proposta do modelo por comparação de string (`escolher_arma`, seleção de alvo em `turno_jogador`).

Esse desenho não escalava: cada ação nova (mover, usar item, gastar ouro, testar um atributo) exigiria inflar o mesmo JSON ad-hoc com mais um campo opcional, e o servidor continuaria só adivinhando quais campos o modelo decidiu preencher naquele turno. O SDK da Groq já instalado (`groq==0.37.1`) suporta tool calling nativo (`tools=`, `tool_choice`, `message.tool_calls`) sem exigir dependência nova — os tipos já vêm no pacote (`chat_completion_tool_param.py` etc., confirmado em `.venv`).

## Decisão

O modelo para de escrever qualquer campo de estado dentro da narrativa. Em vez disso, chama ferramentas tipadas (`services/tools.py`, schema JSON em `TOOLS_SCHEMA`) — `rolar_teste`, `atacar`, `aplicar_dano`, `mover`, `consultar_regra`, `usar_item`, `dar_item`, `gastar_ouro`, e uma nona, `iniciar_combate` (substitui `spawn_battle`+`inimigos_sugeridos`, adicionada porque um campo solto sobrevivendo ao lado de ferramentas de verdade contradiria o próprio objetivo da etapa). Um loop de agente com limite de passos (`services/agent_loop.py`, `executar_turno`) despacha cada chamada para `ToolExecutor`, que por sua vez chama `services/combat.py`/`services/rules_engine.py` — exatamente as mesmas funções determinísticas da Etapa 3, só que acionadas por uma chamada de função validada pela API em vez de um dicionário solto lido com `.get()`.

A resposta final do modelo deixa de ser JSON: depois de chamar as ferramentas que a cena pedir, ele devolve só o texto da narrativa em prosa. `narrator.chamar_mestre` (modo JSON) continua existindo, mas só para `gerar_prologo_missao` — o prólogo é uma chamada única sem estado de jogo para mudar, não precisa de ferramenta nenhuma.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Manter o JSON solto, mas validar contra um schema (Pydantic/`jsonschema`) antes de aceitar | menor mudança de código | ainda é o modelo escrevendo texto que *parece* estruturado, sem a garantia de schema que a própria API já oferece de graça; continuaria escalando mal a cada ação nova | resolve só metade do problema (validação), não o design (um campo por ação, JSON crescendo) |
| Usar um framework de agente (LangChain, LlamaIndex, um agent SDK) para o loop e o parsing | menos código próprio para manter | esconderia exatamente o mecanismo que este projeto existe para demonstrar (ver `docs/adr/README.md`, "decisões já tomadas sem ADR" — não usar LangChain/LlamaIndex já era princípio do projeto antes desta etapa) | contraria a tese do portfólio: o valor está em entender e mostrar o loop, não em importar um |
| Forçar `tool_choice` obrigatório (nunca "auto") em todo turno | eliminaria o caso de o modelo responder só texto quando devia agir | quebraria turnos legitimamente sem ação de estado (diálogo puro, descrição de cena) — forçaria uma chamada de ferramenta artificial | `tool_choice="auto"` é o comportamento correto; a métrica de tool-call accuracy existe justamente para medir quando o "auto" erra |

## Consequências

**Ganhamos:**
- Todo argumento de ferramenta é validado pela própria API da Groq contra o JSON Schema declarado (`TOOLS_SCHEMA`) antes de chegar ao servidor — não é mais `.get("comando_combate") or {}` esperando que a forma esteja certa.
- `ToolExecutor.executar` nunca deixa uma ferramenta malformada (nome inexistente, JSON quebrado, argumento faltando) derrubar o turno: vira uma mensagem de erro que volta pro modelo como resultado da ferramenta, e ele tem o próximo passo do loop para se corrigir — um retry de structured output no nível do schema, sem `tenacity` nem chamada de API extra.
- Tool-call accuracy agora é uma métrica medível de verdade (`scripts/tool_call_accuracy.py`): 70% → 80% de acerto completo (ferramenta certa + argumentos certos) só de reescrever as `description` das ferramentas — o mesmo tipo de ganho que ADR-0006 previa precisar de tool calling nativo para sequer medir.

**Pagamos:**
- Testado ao vivo contra o servidor de verdade (Groq, `openai/gpt-oss-120b`): o modelo continua, em boa parte dos turnos, narrando "role um teste de Investigação (CD 12)" e pedindo o resultado ao jogador **em vez de chamar `rolar_teste` ele mesmo** — mesmo com a ferramenta disponível e uma instrução explícita no prompt de sistema para nunca fazer isso. É o mesmo comportamento que o ADR-0006 já flagrara na Etapa 3 (o modelo pedindo dado ao jogador), só que sobrevivendo à troca de mecanismo: ter a ferramenta certa não garante que o modelo a use no momento certo.
- Também ao vivo: numa cena de saque, o modelo narrou "Kaelen guarda os itens no seu inventário" sem chamar `dar_item` — o inventário real não mudou. Um reprompt no system prompt ("chame dar_item ANTES de narrar a posse") foi adicionado durante esta mesma etapa, mas não foi medido se elimina o problema — só reduz, por analogia com o comportamento de "pedir rolagem" que a Etapa 3 já documentou como resistente a ajuste de prompt.
- E um terceiro caso ao vivo: `mover` narrou uma viagem completa até "Vila de Phandalin" sem chamar a ferramenta — `world_state.local` no banco continuou "Ruínas de Thornmar". O guardrail (ver PLANO_MESTRE.md, Etapa 4) não pegou porque o texto nunca repetia o nome exato do local depois da primeira menção — limitação de um guardrail por palavra-chave, não um bug de lógica.

**Fica em aberto:**
- Os três casos acima (pedir rolagem, narrar item sem `dar_item`, narrar movimento sem `mover`) são a mesma categoria de problema: o modelo narra uma mudança de estado sem chamar a ferramenta correspondente. Um guardrail mais forte (comparar toda entidade nomeada na narrativa contra o estado, não só substring de nome conhecido) é candidato a revisão quando a Etapa 6 trouxer LLM-as-judge — hoje seria caro demais (uma chamada de LLM extra por turno) para o ganho.
- `tool_choice="auto"` permite o modelo responder só texto mesmo quando uma ferramenta seria esperada — é o comportamento certo (nem toda ação muda estado), mas é também a raiz dos três casos acima. Forçar `tool_choice` melhoraria a taxa de chamada às custas de forçar ferramenta em turnos que não precisam — não foi testado.

## Como saber que erramos

Se a tool-call accuracy medida (`scripts/tool_call_accuracy.py`) não melhorar de forma consistente ao reescrever `description`s em etapas futuras — ou se o guardrail continuar sistematicamente perdendo os mesmos três tipos de caso acima depois de tentativas de ajuste de prompt — é sinal de que o problema não é de *redação* de ferramenta, e sim de o modelo escolhido (`openai/gpt-oss-120b` via Groq) ter um viés de treino forte demais para narrar em vez de agir; nesse caso, `tool_choice` obrigatório em contextos específicos (ex: sempre que há combate ativo) vira candidato real, não só nota de rodapé.

## Referências

- `PLANO_MESTRE.md`, Etapa 3 ("O juiz") e Etapa 4 ("O narrador") — a fronteira que este ADR formaliza, já prevista no ADR-0006.
- [`ADR-0006`](0006-llm-nao-e-motor-de-regras.md) — o degrau anterior: LLM propõe, servidor decide. Este ADR troca só *como* o modelo propõe.
- [Groq — Tool use](https://console.groq.com/docs/tool-use) — documentação oficial de tool calling usada como referência de schema e de `tool_choice`.
