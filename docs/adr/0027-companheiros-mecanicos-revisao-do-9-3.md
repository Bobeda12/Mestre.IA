# ADR-0027 — Companheiros mecânicos: revisão parcial do §9.3 (single-player)

**Data:** 25/08/2026
**Status:** Aceito
**Etapa:** Revisão de gameplay (Fase 2 de 9 — ver `docs/backlog-pos-lancamento.md`, Etapa 12/13)
**Supersede:** revisa parcialmente `PLANO_MESTRE.md §9.3`

---

## Contexto

`PLANO_MESTRE.md §9.3` ("Single-player ✅", 18/08/2026) registrou: *"O motor de regras da
Etapa 3 é escrito para **um** herói contra N inimigos, e não paga o custo de abstração de
mesa com múltiplos jogadores."* Na prática isso queria dizer: `CombatState` só sabe
resolver ataques contra um único alvo amigo (o herói, `-1` fixo em `ordem_iniciativa`), e
`combat.turno_inimigos` sempre mirava nele.

`gameplay_v2.md` (documento trazido pelo usuário) pediu companheiros que lutam de verdade
— HP próprio, participam do combate. O backlog antigo (`docs/backlog-pos-lancamento.md`,
item C-7) já tinha identificado essa tensão e recomendava um "Nível 1" só narrativo
primeiro, evoluindo para combate "se o feedback dos amigos pedir, com um ADR emendando o
§9.3". Essa etapa nunca rodou — e desta vez o usuário decidiu, de forma explícita e
consciente da troca, pular direto para a versão mecânica.

## Decisão

**O §9.3 é revisado, não revogado.** A leitura original — nunca pagar o custo de uma
abstração de mesa *multiplayer* (vários jogadores humanos, sincronização de turno,
presença, resolução de conflito de ação entre eles) — continua valendo integralmente e
sem prazo. O que muda é mais estreito: o motor de combate passa a suportar um **segundo
tipo de combatente amigo controlado pelo próprio jogador** (aliados recrutados,
implementados na Fase 3 deste plano), não um segundo jogador humano.

Concretamente (`domain/state.py`, `services/combat.py`):

- `CombatState` ganha `aliados: list[Aliado]` — mesma forma de `Inimigo` (hp, max_hp, ca,
  bônus de ataque, dado de dano), porque é isso que permite ao motor tratar herói,
  aliado e inimigo pela mesma lógica de acerto/dano/morte já existente.
- `combat.turno_inimigos` (Fase 1) parou de mirar sempre no herói: `_escolher_alvo`
  sorteia entre o herói e os aliados vivos, peso igual entre todos (regra de primeira
  passada — ver "Como saber que erramos").
- **Nenhuma mudança em `ordem_iniciativa`.** Cogitei mudar seu formato (de `list[int]`
  para tuplas `("heroi"|"aliado"|"inimigo", idx)`) — descartado: essa lista só ordena o
  turno dos INIMIGOS (o herói entra como `-1` só pra desempate/exibição), e aliados ainda
  não agem por conta própria nesta fase (isso é Fase 3). Mudar o formato quebraria
  qualquer `combat_state` já salvo no banco com combate em andamento, por um ganho que
  ainda não existe. Fica registrado como possível trabalho futuro, não como dívida.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Manter §9.3 como está (companheiro só narrativo, "Nível 1" do backlog antigo) | Zero risco de engine, ADR desnecessário | É o que o backlog antigo recomendava, mas o usuário pediu explicitamente a versão mecânica desta vez | Decisão explícita do usuário, registrada aqui para não parecer descuido |
| `ordem_iniciativa` com tuplas tipadas, aliados com turno próprio já nesta fase | Mais "completo", writes-once | Maior risco (todo `CombatState` salvo com combate ativo quebraria ao carregar), sem nenhum recurso que use isso ainda | Adiado até a Fase 3 realmente precisar — não implementar antes de ter uso |
| Reaproveitar `Inimigo` para representar aliados (sem classe `Aliado` nova) | Menos código | Um "Inimigo" sendo aliado do herói é uma mentira semântica que confunde o próximo leitor do código | `Aliado` é uma classe de uma dúzia de linhas — o custo de clareza vale mais que a duplicação |

## Consequências

**Ganhamos:**
- O motor sabe resolver ataque/dano/morte contra um segundo alvo amigo — pré-requisito
  direto da Fase 3 (aliados mecânicos de verdade: recrutar, atacar_com_aliado).
- Zero regressão: a suíte de combate inteira (`test_combat.py`) passa sem alteração
  nenhuma — `_escolher_alvo` sem aliados vivos devolve sempre "heroi" sem consumir rng,
  então o comportamento é idêntico, byte a byte, a antes desta fase.

**Pagamos:**
- Regra de alvo é "peso aleatório entre quem está vivo" — não é tática nenhuma (um
  inimigo pode ignorar o herói baleado pra bater no aliado saudável, ou o oposto). É
  primeira passada, deliberadamente simples.
- `EventoStatus.tipo` ganhou `"morte_aliado"`, mas o frontend (`StatusCard.tsx`) ainda
  trata igual a `"morte_inimigo"` — o dado já é honesto, a tela ainda não diferencia.

**Fica em aberto:**
- Regra de alvo por prioridade (ex: focar o mais ferido, ou o que fez mais dano) —
  cogitada, adiada para não gastar esforço numa lógica que ninguém vai sentir enquanto
  não existir nenhum aliado de verdade em jogo (Fase 3 ainda não escrita).
- `ordem_iniciativa` com turno próprio pro aliado, se e quando ele precisar agir sem ser
  dirigido explicitamente pelo jogador.

## Como saber que erramos

- Se o feedback de quem testar companheiros (depois da Fase 3) disser que o alvo
  aleatório "não faz sentido" — ex: um goblin ignorando um aliado caído para bater no
  herói saudável — a regra vira prioridade por menor HP%, e este ADR ganha uma nota.
- Se `ordem_iniciativa` continuar bare `list[int]` até a Fase 3 e ela precisar mesmo de
  turno próprio pro aliado, decidir ali (não aqui) entre migrar o formato ou dar ao
  aliado uma resolução simplificada (ex: sempre ataca junto do herói, sem iniciativa
  própria) — as duas são mais baratas que reabrir este ADR agora sem necessidade.

## Referências

- `PLANO_MESTRE.md §9.3` — decisão original revisada aqui
- ADR-0006 — LLM não é motor de regras (mesma fronteira de confiança aplicada ao alvo do ataque)
- `docs/backlog-pos-lancamento.md`, item C-7 — recomendação original de "Nível 1 primeiro", não seguida por decisão explícita do usuário nesta rodada
