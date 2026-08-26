# Revisão de gameplay — Fase 6 (mundo vivo)

**Período:** 25/08/2026 · uma sessão com o Claude Code · **estimado no plano:** 24h (Fase
6 de 9, `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`) — a fase com mais
peças diferentes até agora: quatro sistemas soltos, cada um pequeno, mas juntos formando
"o mundo continua acontecendo mesmo quando o jogador não está olhando".

## O que eu queria com essa fase

Até aqui o mundo só reagia — o jogador agia, o narrador respondia. Esta fase dá ao mundo
uma iniciativa própria: viajar tem risco real (não roteirizado), descansar demais custa
algo em algum lugar da história, e itens comuns ganham um uso além do óbvio.

## O que mudou

- **Relógio de facção** (`WorldState.relogios`): um contador de urgência ligado ao Ato
  atual. `descansar("longo")` avança; `atualizar_missao(avancar_ato=True)` zera (o
  próximo Ato começa com pressão zero). No máximo (4), `montar_contexto` injeta
  `[EVENTO GLOBAL]` — e fica ligado até o Ato avançar, de propósito: é pressão contínua,
  não uma linha só.
- **Encontros aleatórios de viagem**: todo `mover()` bem-sucedido rola 1d20 — natural 1
  sinaliza `"emboscada"`, natural 20 sinaliza `"achado"` no resultado que volta pro
  modelo. O servidor só gera o evento; quem narra e decide o que fazer com ele
  (`iniciar_combate`, `dar_item`...) é o modelo, como já era antes de tudo isto.
- **`descansar(tipo)`**: curto recupera parcial (dado de vida da classe + modificador de
  Constituição) em qualquer lugar; longo recupera tudo, mas só em local marcado `seguro`
  no catálogo (`data/locations.json` ganhou esse campo em todas as 7 entradas) e não pode
  se repetir antes de 8 turnos de jogo — não existe relógio de calendário no sistema, "8
  turnos desde o último" é a aproximação de "um dia narrativo".
- **Gancho de acampamento**: descanso longo bem-sucedido, com aliado vivo presente, volta
  um `gancho_acampamento` no resultado da ferramenta — uma instrução direta pro modelo
  puxar uma fala do companheiro NA MESMA resposta, sem precisar de um mecanismo de
  contexto à parte.
- **Tags de item** (`data/items.json`, catálogo novo — 5 itens): `rolar_teste` ganha
  `item_usado` opcional; se o item está no inventário e tem qualquer tag, +2 no teste.
  Armas reaproveitam as `propriedades` que já tinham (`Machado Grande` → "Pesada") como
  tag também, sem duplicar o dado em dois arquivos. Bônus é fixo — o servidor não tenta
  casar qual tag serve pra qual situação, isso é a narrativa do modelo justificando.

## Como testei

**22 testes novos** de backend: item com/sem tag no inventário, arma reaproveitando
propriedade como tag, encontro aleatório nos três casos (1, 20, nem um nem outro) e o
caso de erro não rolando encontro à toa, descanso curto/longo em cada combinação de
local seguro/inseguro/tempo insuficiente, gancho de acampamento com/sem aliado,
`avancar_ato` resetando o relógio, e `[EVENTO GLOBAL]` aparecendo/sumindo do prompt.

**Um cuidado que quase virou teste flaky**: adicionar a rolagem de encontro em `mover()`
quebrou duas asserções de igualdade exata de dict nos testes da Fase 5 (`resultado ==
{...}`), porque `resultado` agora pode ganhar uma chave `"encontro"` com ~10% de chance.
Corrigido trocando pra checar campos específicos — mais robusto de qualquer forma, e o
tipo de coisa que só aparece rodando a suíte inteira depois da mudança, não escrevendo o
teste novo isolado.

**Ao vivo, contra a Groq de verdade**: testei `descansar` numa sequência real —
personagem novo começou (pelo prólogo) num local inseguro (Forte de Dunhollow), e o
modelo, sem eu instruir nada sobre segurança, ofereceu opções em vez de forçar um
descanso ali. Depois de mover pra Vila de Phandalin (segura) e pedir descanso, o modelo
chamou `descansar("longo")` de verdade — evento "🏕️ Descanso longo: recupera totalmente
os PV" apareceu certinho. **Não confirmei ao vivo** `item_usado` nem o encontro aleatório
de viagem (1 em 20 é raro de sair em poucos turnos) — bati em rate limit dos dois
provedores (Groq E Gemini simultâneos, "429 Too Many Requests" nos dois) antes de
conseguir forçar esses casos. Ambos têm cobertura completa de pytest; fica registrado
como pendência de eval ao vivo, junto com `atacar_com_aliado` (Fase 3) e `avancar_ato`
(Fase 4).

## Decisões tomadas

- Sem ADR — trabalho aditivo, sem divergência de decisão registrada.
- Bônus de tag é fixo (+2), não varia por qual tag combina com qual situação — primeira
  passada deliberada, como o resto dos números novos desta revisão.
- "Local seguro" é um campo curado no catálogo, não inferido — locais recém-descobertos
  (Fase 5) são conservadoramente inseguros pra descanso longo até haver um jeito melhor
  de decidir isso.

## Números

- 398 testes de backend passando (eram 376 no fim da Fase 5) — 22 novos.
- `ruff check` e `tsc --noEmit` limpos (frontend não precisou de mudança nesta fase).
- 2 fluxos confirmados ao vivo (personagem recusando descanso em lugar perigoso sem ser
  instruído, `descansar("longo")` chamado e resolvido de verdade); 2 pendentes de eval
  ao vivo por causa de rate limit (`item_usado`, encontro aleatório).

## Próximo passo

Restam Fase 7 (livro da campanha: epitáfio, crônica exportável) e Fase 8 (UX híbrida:
dados visíveis, cards de NPC, inventário por injeção) — as duas últimas do plano, e
nenhuma depende da outra.
