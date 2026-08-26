# ADR-0029 — Pele e ficha separadas: monstros e o local inicial deixam de ser fixos

**Data:** 26/08/2026
**Status:** Aceito
**Etapa:** Rodada de conserto pós-revisão de gameplay (Parte 2, item J — "chega de goblins")
**Supersede:** revisa o comportamento de `services/combat.py:iniciar_combate`/`_criar_inimigo`
desde a Etapa 3, e complementa o ADR-0028 (`narrator.gerar_prologo_missao`)

---

## Contexto

O primeiro teste real do jogo (feedback do jogador, 26/08/2026) apontou que toda partida
se parecia com a anterior: todo herói de nível 1 enfrentava um dos mesmos 4 monstros
(Goblin, Esqueleto, Lobo, Kobold — `data/monsters.json`, banda `Nivel_1`) e quase sempre
começava na Vila de Phandalin. A causa é estrutural, não falta de conteúdo: `_criar_inimigo`
sempre usava o nome do bestiário como nome exibido, e `iniciar_combate` **descartava** em
silêncio qualquer nome proposto que não batesse exato com o catálogo — o mesmo padrão
estrito que o ADR-0028 já tinha resolvido para locais, mas nunca chegou aos monstros nem
ao local inicial do prólogo.

Aumentar o bestiário (mais entradas em `monsters.json`) ataca o sintoma errado: o problema
não é a variedade de fichas, é que o **nome e a ficha estão amarrados** — não dá pra ter
mais nomes sem também balancear mais números, e o ADR-0006 (LLM não é motor de regras)
proíbe deixar o modelo inventar HP/CA/dano.

## Decisão

**O nome que o jogador vê e a ficha que o motor usa deixam de ser a mesma coisa.** Os 13
monstros de `data/monsters.json` continuam sendo as únicas fichas que existem — o juiz
nunca decide número nenhum fora delas. O que passa a variar é a **pele**: o nome e (na
crônica) a descrição.

1. `combat._criar_inimigo(nome, nome_exibicao=None)` ganha um segundo parâmetro opcional:
   a ficha (HP/CA/dano/comportamento) sempre vem de `nome` (a chave real do bestiário);
   `nome_exibicao`, quando presente, é só o que aparece pro jogador.
2. `combat.iniciar_combate(nomes_propostos, ..., nivel_heroi=1)`: um nome que bate exato
   no catálogo funciona como sempre. Um nome que **não** bate deixa de ser descartado —
   vira a pele de um arquétipo sorteado da banda de nível do herói
   (`rules_engine.desafio_sugerido`), a mesma escala de perigo que a Fase 0 já usa pra
   sugerir encontros. A rolagem de iniciativa (que precisa da destreza do monstro de
   verdade) passa a indexar pelo nome do ARQUÉTIPO, não pelo nome exibido — sem isso, um
   monstro "pelado" reverteria pra destreza 10 por não achar a si mesmo no catálogo.
3. `narrator.gerar_prologo_missao`: o prólogo pode propor um `local_inicial` fora do
   catálogo se também vier com `local_inicial_descricao` — mesmo padrão do ADR-0028
   (`mover(descricao_proposta)`), só que o registro em `WorldState.locais_descobertos`
   acontece em `routers/character.py`, no momento da criação, antes de qualquer turno
   existir.

Em nenhum dos dois casos o modelo ganha um poder que não tinha: ele continua só
**propondo** um nome/descrição; o servidor decide se vira um arquétipo real (ponto 2) ou
um local reconhecido (ponto 3) — mesmo padrão do ADR-0002 e do ADR-0028, agora aplicado a
"quem é esse inimigo" em vez de só "onde fica esse lugar".

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Aumentar `monsters.json` para 30-40 entradas | Mais variedade real, sem mudar código | Cada entrada nova precisa de HP/CA/dano balanceados à mão (ou via `evals/simulador.py`) — trabalho contínuo, e ainda assim toda campanha de nível 1 continuaria vendo o mesmo subconjunto pequeno | Ataca sintoma (poucos nomes), não causa (nome preso à ficha) |
| Deixar o modelo inventar HP/CA/dano do monstro novo | Variedade "infinita" de verdade | Contraria o ADR-0006 na cara — é exatamente o "juiz" que a Etapa 3 tirou do LLM | Não negociável neste projeto |
| `iniciar_combate(inimigos: list[dict])` — o modelo manda `{"arquetipo": ..., "nome_exibicao": ...}` explicitamente | Mais explícito sobre a intenção do modelo | Quebra a assinatura de toda chamada existente (evals/golden, testes, a ferramenta em si) por um ganho pequeno — o servidor já consegue inferir a mesma coisa checando se o nome bate no catálogo | Custo de migração não compensa; o comportamento observável é idêntico |
| Pele sorteada de QUALQUER banda, não só a do nível do herói | Mais surpresa | Uma "pele" de Dragão Jovem com ficha de Goblin (ou o contrário) quebra a legibilidade do perigo — o jogador vê um nome assustador com números de nível 1, ou o oposto | `desafio_sugerido(nivel_heroi)` já existe e resolve exatamente essa faixa |

## Consequências

**Ganhamos:**
- Uma campanha de nível 1 pode ter dezenas de nomes/descrições diferentes de monstro sem
  precisar de uma linha nova em `monsters.json` — a variedade escala com a criatividade do
  narrador, não com o tamanho do catálogo.
- O ponto de partida deixa de ser quase sempre Phandalin, sem abrir mão da garantia do
  ADR-0028 (o motor nunca referencia um lugar que não registrou).
- Zero mudança de assinatura pública: `iniciar_combate(inimigos: list[str])` continua
  aceitando a mesma lista de strings de sempre — só o que acontece com um nome
  desconhecido mudou (de "descartado" para "vira pele").

**Pagamos:**
- `combat.py` ganhou uma lista de pares `(Inimigo, nome_do_arquétipo)` interna só para a
  iniciativa não se perder — mais um detalhe de implementação a manter, embora não vaze
  pra fora da função.
- Um teste antigo (`test_nome_desconhecido_cai_para_monstro_de_nivel_1_sorteado`) mudou de
  sentido: antes provava que um nome ruim era descartado; agora prova o oposto (vira
  pele). Reescrito, não deletado — o comportamento antigo não existe mais.
- O bestiário "visto" pelo jogador (nomes) e o bestiário real (fichas) podem divergir o
  suficiente para confundir quem lê `docs/backlog-pos-lancamento.md`/ADRs antigos citando
  "os 13 monstros" como se fossem também os únicos nomes possíveis em cena.

**Fica em aberto:**
- O sprite do monstro (Etapa 11, B-1) segue o **arquétipo**, não o nome inventado — um
  "Batedor Rasgacouro" com ficha de Goblin mostra o sprite de Goblin. Não é dissonância
  grave (o `onError` já degrada bem quando não acha imagem nenhuma), mas é um ponto de
  atrito estético que uma geração de sprite por descrição resolveria, se algum dia valer o
  custo.
- Nenhuma cota impede o modelo de propor um nome novo em TODO combate — se isso se provar
  cansativo (nomes demais, nunca repetindo um "personagem" de vilão reconhecível), é um
  ajuste de prompt, não deste ADR.

## Como saber que erramos

- Se o jogador achar os nomes inventados genéricos ou incoerentes com a cena (o problema
  original era "sempre Goblin"; o oposto — "nunca duas vezes o mesmo nome, mesmo quando
  devia ser o mesmo vilão recorrente" — é uma falha diferente, não coberta aqui).
- Se a rolagem de iniciativa de um inimigo "pelado" divergir da ficha do arquétipo em
  produção (sinal de que o lookup por `arquetipo_nome` quebrou em algum caminho não
  coberto pelos testes de `test_combat.py`).

## Referências

- ADR-0002 — revalidação de regras no servidor (mesmo padrão "propõe/decide")
- ADR-0006 — LLM não é motor de regras
- ADR-0028 — locais inventados (o mesmo padrão, aplicado antes a `mover`)
- `docs/backlog-pos-lancamento.md` — C-1/C-2 (bestiário por banda, Fase 0 da revisão de
  gameplay), origem de `rules_engine.desafio_sugerido`
