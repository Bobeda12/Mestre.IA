# ADR-0030 — Excluir personagem apaga a linha de verdade, não só marca `arquivado`

**Data:** 26/08/2026
**Status:** Aceito
**Etapa:** Polimento de UX pós-lançamento (Home/Login)
**Supersede:** não substitui `PATCH /personagens/{id}/arquivar` (Etapa 8) — os dois endpoints coexistem

---

## Contexto

O botão de descartar um herói na Home (`Home.tsx`) chamava
`PATCH /personagens/{id}/arquivar`, que só marca `Personagem.arquivado = True`
(`routers/personagens.py`, endpoint existente desde a Etapa 8). A linha
continua no banco, junto com qualquer `EventoMemoria`, `EventoTelemetria` e
`FeedbackNarracao` associado — só some da lista porque
`listar_personagens` filtra `arquivado.is_(False)`.

Feedback direto do usuário ao revisar a UX da Home: o botão precisa dizer
"excluir" e a ação precisa **excluir de fato** — arquivar sem oferecer uma
tela de "lixeira"/restauração é só esconder o dado, ocupando espaço à toa
sem entregar a garantia que a palavra "excluir" promete.

O obstáculo técnico é que `Personagem` tem três tabelas filhas com
`ForeignKey("personagens.id")` sem `ON DELETE CASCADE`
(`infra/db.py:126,150,168`): `EventoMemoria`, `EventoTelemetria` (nullable)
e `FeedbackNarracao`. Um `DELETE` direto na linha do personagem viola essas
constraints assim que a campanha tiver qualquer evento de memória,
telemetria ou feedback registrado — ou seja, em qualquer campanha jogada
por mais de alguns turnos.

## Decisão

Criar `DELETE /personagens/{session_id}` como um endpoint novo,
**ao lado** de `PATCH /personagens/{id}/arquivar` (que continua existindo,
testado, só deixou de ser chamado pelo botão da Home). O novo endpoint apaga
explicitamente as três tabelas filhas pelo `personagem_id` antes de apagar
o personagem, tudo num único `db.commit()` — sem migration nova, sem
`ON DELETE CASCADE` no schema. O evento de telemetria da própria exclusão
(`personagem_excluido`) é registrado **depois**, sem `personagem_id` (o
personagem já não existe mais para referenciar).

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Reescrever `arquivar_personagem` para apagar de verdade | Um endpoint só, sem duplicação | Muda o contrato de um endpoint já testado (`test_arquivar_personagem_registra_evento`) e ninguém pediu para "arquivar" parar de existir como conceito — pode servir outro fluxo no futuro (ex.: painel admin) | Quebra semântica existente por um ganho só cosmético |
| Adicionar `ON DELETE CASCADE` nas 3 FKs via migration Alembic | Delete vira uma linha só (`db.delete(personagem)`), sem lista manual de tabelas filhas | Uma migration nova para um botão de UX é desproporcional, e cascade automático no schema apaga em qualquer `DELETE` futuro sem o app decidir — perde o controle explícito sobre o que é apagado | Custo/risco não compensa para o problema atual |
| Soft-delete com job de limpeza periódico (apaga de verdade depois de N dias) | Dá margem para desfazer um clique errado | Ninguém pediu essa rede de segurança, e adicionar um job assíncrono só para isso é infraestrutura nova sem uso comprovado | Seria resolver um problema hipotético, não o que foi pedido |

## Consequências

**Ganhamos:**
- "Excluir" na UI agora significa exatamente isso — a linha e os dados
  associados (memória, telemetria, feedback daquele personagem) saem do
  banco, não só da lista visível.
- `arquivar_personagem` continua intacto e testado, disponível se algum
  fluxo futuro precisar de descarte reversível (ex.: um painel de suporte).
- Nenhuma migration — o schema não muda, só o endpoint novo decide a ordem
  de apagar.

**Pagamos:**
- `excluir_personagem` precisa conhecer as três tabelas filhas
  explicitamente; uma quarta tabela com FK para `personagens.id` no futuro
  vai quebrar essa exclusão com um erro de constraint se alguém esquecer de
  atualizar este endpoint também.
- Duas rotas com propósitos parecidos (`arquivar` x `excluir`) no mesmo
  router — quem ler o código pela primeira vez precisa entender que uma é
  reversível e a outra não.
- Exclusão é permanente e imediata, sem `confirm` de duas etapas nem prazo
  de carência — o único freio é o `window.confirm` do navegador antes de
  disparar a chamada.

**Fica em aberto:**
- Se algum dia existir um painel de suporte/admin, ele provavelmente vai
  querer o `arquivar` de volta como "soft delete com possibilidade de
  restaurar" — hoje nenhum dos dois fluxos oferece restauração.

## Como saber que erramos

- Se uma tabela nova ganhar `ForeignKey("personagens.id")` e ninguém
  atualizar `excluir_personagem`: o sintoma é um erro 500 de violação de
  constraint ao excluir qualquer personagem com esse dado novo associado —
  sinal de que a lista de tabelas filhas devia ter sido gerada a partir do
  schema (ou virado `ON DELETE CASCADE` de verdade), não mantida à mão.
- Se usuários reclamarem de ter excluído um herói por engano e quererem
  restaurar: sinal de que falta um "desfazer" ou uma confirmação mais forte
  do que `window.confirm`.

## Referências

- `Backend/app/infra/db.py` — modelos `Personagem`, `EventoMemoria`,
  `EventoTelemetria`, `FeedbackNarracao`
- `Backend/app/routers/personagens.py` — `arquivar_personagem` (existente)
  e `excluir_personagem` (novo)
- `Backend/tests/test_telemetria_e_feedback.py` —
  `test_excluir_personagem_remove_e_registra_evento`
