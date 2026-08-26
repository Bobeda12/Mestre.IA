# Revisão de gameplay — Fase 2 (motor para múltiplos alvos amigos)

**Período:** 25/08/2026 · uma sessão com o Claude Code · **estimado no plano:** 16h (Fase
2 de 9, `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`) — maior risco do
plano inteiro, por isso ganhou o cuidado extra abaixo.

## O que eu queria com essa fase

A Fase 3 (aliados que lutam de verdade) não tem onde nascer sem isso: hoje o motor de
combate só sabe mirar em UM alvo amigo, o herói, hardcoded como `-1` em
`CombatState.ordem_iniciativa`. Esta fase é puramente estrutural — nenhuma feature nova
que o jogador veja, porque ainda não existe nenhuma forma de recrutar ninguém (isso é
Fase 3). O objetivo era só: o motor consegue mirar num segundo alvo amigo, sem quebrar
nada do que já existe.

## O que mudou

- **`Aliado`** (`domain/state.py`): mesma forma de `Inimigo` (hp, max_hp, ca, bônus de
  ataque, dado de dano) — de propósito, é o que deixa o motor tratar herói/aliado/inimigo
  pela mesma lógica de acerto e dano que já existia.
- **`CombatState.aliados: list[Aliado] = []`** — lista nova, vazia por padrão.
- **`combat._escolher_alvo`**: quando há aliado vivo, sorteia entre ele e o herói (peso
  igual); sem aliado vivo (o caso comum hoje — Fase 3 ainda não deu um jeito de recrutar),
  o alvo é sempre o herói, **sem consumir nenhum rng** — é isso que garante que o
  comportamento de antes desta fase continua idêntico.
- **`combat.turno_inimigos`** agora aplica dano num aliado escolhido direto no
  `c_state.aliados[i].hp`, gera um evento de morte próprio (`EventoStatus` tipo
  `"morte_aliado"`) quando ele cai, e as táticas do herói (esquivar/investir, Fase 1) só
  protegem o HERÓI — um ataque mirado no aliado usa só o comportamento do próprio inimigo.
- **Decisão que não virou código**: cogitei mudar `ordem_iniciativa` de `list[int]` para
  tuplas tipadas (`("heroi"|"aliado"|"inimigo", idx)`), mas recuei — essa lista só ordena
  o turno dos INIMIGOS, aliados ainda não agem por conta própria nesta fase, e mudar o
  formato quebraria qualquer combate salvo no banco por um ganho que ainda não existe.
  Registrado no ADR, não escondido.

## Como testei sem quebrar o que já existia

A suíte de combate inteira (`test_combat.py`, `test_tools.py`) passou **sem alterar uma
linha** depois do refactor — era o critério de aceite da fase, não um bônus. Isso só é
possível porque `_escolher_alvo` devolve "heroi" sem tocar no gerador aleatório quando
`aliados` está vazio; qualquer `RngFixo` de teste antigo continua vendo exatamente a
mesma sequência de dados que via antes.

Pra testar o caminho NOVO (ataque mirando um aliado), o `RngFixo` existente não servia —
seu `choice()` sempre devolve o primeiro item da lista, e o herói é sempre o primeiro
candidato em `_escolher_alvo`. Escrevi um `_RngAlvo` local em `test_combat.py` (herda de
`RngFixo`, só sobrescreve `choice()` para devolver uma escolha fixada) — pequeno, mas
sem ele seria impossível forçar o motor a mirar no aliado num teste determinístico.

## Decisões tomadas

- [ADR-0027](../adr/0027-companheiros-mecanicos-revisao-do-9-3.md) — revisão parcial do
  §9.3 (`PLANO_MESTRE.md`): a leitura original (nunca pagar custo de abstração
  multiplayer) continua valendo; o que muda é mais estreito — um segundo combatente amigo
  controlado pelo próprio jogador, não um segundo jogador humano.
- Regra de alvo é peso aleatório, não tática (não prioriza o mais ferido) — primeira
  passada deliberada, documentada no ADR como algo a revisar se o feedback pedir.

## Números

- 335 testes de backend passando (eram 329 no fim da Fase 1) — 6 testes novos:
  `_escolher_alvo` (3) e `turno_inimigos` mirando aliado (3). Nenhum teste existente
  mudou.
- `ruff check` e `tsc --noEmit` limpos.
- Sem verificação ao vivo no navegador nesta fase — não há nada novo pra jogar ainda
  (`aliados` fica vazio até a Fase 3 dar um jeito de recrutar); a garantia aqui é a suíte
  de regressão intacta, não uma tela nova.

## Próximo passo

Fase 3 (aliados mecânicos): coluna `aliados` em `Personagem`, ferramentas
`recrutar_aliado`/`atacar_com_aliado`, e a seção `[ALIADOS PRESENTES]` no contexto do
narrador — é onde o motor construído aqui finalmente aparece pro jogador.
