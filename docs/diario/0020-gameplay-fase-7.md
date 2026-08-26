# Revisão de gameplay — Fase 7 (livro da campanha)

**Período:** 25/08/2026 · uma sessão com o Claude Code · **estimado no plano:** 14h (Fase
7 de 9, `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`)

## O que eu queria com essa fase

Até aqui, morrer só terminava o jogo — a tela de "GAME OVER" tinha um placar e uma
promessa não cumprida ("em breve, o mestre vai contar como termina esta jornada"). Esta
fase cumpre essa promessa, e adiciona uma segunda: a campanha inteira, viva ou não, pode
virar um conto pra levar pra casa.

## O que mudou

- **`Personagem.epitafio`** (migration `0012_epitafio.py`): `{"retrospectiva",
  "epitafio_curto"}`, `None` enquanto o herói está vivo.
- **`narrator.gerar_epitafio`**: chamada isolada (mesmo padrão JSON solto de
  `gerar_prologo_missao`) usando os eventos mais marcantes
  (`memory.eventos_marcantes`, os últimos 8, sem busca híbrida — não há uma "pergunta"
  natural na hora da morte) e os fatos do resumo rolante. Instruído a não inventar
  eventos fora do que foi listado.
- **Gerado uma vez, nunca regenerado**: `_persistir_epitafio_se_confirmado`
  (`routers/game.py`) roda logo depois de `combat.turno_morte` confirmar a morte, guardado
  por `heroi.epitafio is None` — regenerar a cada visita custaria dinheiro e daria uma
  memória diferente da mesma morte a cada vez.
- **Tela de GAME OVER** agora mostra a retrospectiva e o epitáfio de verdade, no lugar do
  placeholder.
- **`GET /personagens/{session_id}/cronica`**: `memory.eventos_cronologicos` (todos os
  eventos, em ordem, sem teto) tecidos num conto de fantasia por
  `narrator.gerar_cronica` — ao contrário do epitáfio, gerado a cada pedido (a campanha
  pode ter avançado desde a última exportação). Teto de 60 eventos mais recentes por
  chamada, pra o prompt não crescer sem fim numa campanha longa.
- **Botão "Exportar Crônica"** na tela de GAME OVER, baixando um `.txt` de verdade
  (Blob + `<a download>` — este é o app real, não um Artifact publicado, o link funciona
  normal).

## Como testei

**24 testes novos** de backend: `eventos_marcantes` (ordem cronológica, teto, filtro por
personagem, lista vazia), `eventos_cronologicos` (sem teto, filtro por personagem),
`gerar_epitafio` (mantém o que o modelo manda, cai no padrão se algum campo vier vazio
ou ausente, cai no padrão sem client), e um teste de integração de ponta a ponta pra
`/cronica` via `TestClient` (404 pra sessão inexistente, sem eventos não quebra, com
eventos reais devolve o texto).

**Ao vivo, contra a Groq de verdade — o teste mais completo desta sessão inteira**:
criei um personagem, joguei um turno real (uma conversa na taverna, virou um evento de
memória), depois manipulei o banco direto (`hp_atual=0`, `falhas_morte=2`) pra forçar a
véspera da morte sem precisar de uma dezena de combates. Um turno depois, a terceira
falha aconteceu de verdade (`d20(7) → falha`), `resultado_combate` virou `"morte"`, e o
epitáfio foi gerado na mesma resposta — citando literalmente o evento da taverna que eu
tinha acabado de viver, sem inventar nada fora dele. Abri a tela do jogo no navegador: a
retrospectiva e o epitáfio apareceram certinho na tela de GAME OVER. Cliquei em
"Exportar Crônica": a chamada foi (`GET /personagens/.../cronica` → 200), e o texto
devolvido teceu os dois eventos da sessão (a taverna e a luta pela consciência) num
parágrafo só, coerente.

## Decisões tomadas

- Sem ADR — trabalho aditivo.
- Epitáfio usa os últimos 8 eventos por ordem cronológica (sem busca híbrida); Crônica
  usa até 60, também cronológicos — nenhum dos dois tenta adivinhar "relevância", porque
  não há uma pergunta natural pra guiar a busca no momento da morte ou da exportação.

## Números

- 411 testes de backend passando (eram 398 no fim da Fase 6) — 13 novos de memória
  (`eventos_marcantes`/`eventos_cronologicos`), 4 de `gerar_epitafio`, 3 de integração
  de `/cronica` via `TestClient`.
- `ruff check` e `tsc --noEmit` limpos.
- 3 fluxos confirmados ao vivo nesta fase: registro de memória → epitáfio citando o
  evento real → tela renderizando certo → crônica exportada tecendo os eventos reais.
  Nenhuma pendência de eval ao vivo fica registrada desta vez — foi a fase mais bem
  verificada até agora.

## Próximo passo

Fase 8 (UX híbrida: dados visíveis, cards de atitude de NPC, inventário por injeção) —
majoritariamente frontend, a última do plano de 9 fases.
