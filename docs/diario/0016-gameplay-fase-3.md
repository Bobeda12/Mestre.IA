# Revisão de gameplay — Fase 3 (aliados mecânicos)

**Período:** 25/08/2026 · uma sessão com o Claude Code · **estimado no plano:** 14h (Fase
3 de 9, `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`)

## O que eu queria com essa fase

A Fase 2 deu ao motor a capacidade de mirar num segundo alvo amigo, mas nada ainda usava
isso — não existia forma nenhuma de um companheiro aparecer em jogo. Esta fase é onde o
jogador deixa de andar sozinho pra valer: recrutar alguém na estrada, ele acompanhar a
jornada, lutar ao lado do herói, e sobreviver (ou não) de um combate pro outro.

## O que mudou

- **`Personagem.aliados`** (migration `0011_aliados.py`): roster persistente — nome,
  classe, HP atual, HP máximo, lealdade, inventário (ainda sem uso). É o que sobrevive
  entre turnos e sessões; o `Aliado` da Fase 2 (`CombatState.aliados`) é só o "agora" de
  um combate específico.
- **`recrutar_aliado(nome, classe, hp)`**: grava no roster; se já há combate ativo,
  também entra na luta atual. HP proposto pelo modelo é clampado (4 a 20) — mesmo
  princípio de `ajustar_reputacao_npc`: o modelo decide o "quê", o servidor decide o
  "quanto". Estatísticas de combate (CA 12, +2 de ataque, 1d6 de dano) são fixas, não
  inventadas pelo modelo — primeira passada, como quase todo número novo desta revisão.
- **`atacar_com_aliado(aliado, alvo)`**: resolve pelo motor generalizado da Fase 2/3
  (`combat.turno_aliado`, mesma forma de `turno_jogador`, só sem escolha de arma).
- **`iniciar_combate`** agora povoa `c_state.aliados` a partir do roster vivo — um
  companheiro recrutado ontem aparece na luta de hoje; um que morreu (HP 0) não volta.
- **`sincronizar_aliados`**: o HP mudado em combate (`c_state.aliados`) é copiado de
  volta pro roster persistente uma vez por turno, em `routers/game.py`, logo antes de
  gravar o `combat_state` — sem isso, dano recebido pelo aliado "sumiria" assim que o
  turno terminasse.
- **`[ALIADOS PRESENTES]`** no contexto do narrador — companheiros são parte da cena o
  tempo todo, não só durante combate.
- **Uma decisão deliberada, não descuido**: `atacar_com_aliado` NÃO aciona a resposta dos
  inimigos sozinho. Cogitei fazer isso (mesmo padrão de `esquivar`/`defender`/`atacar`),
  mas percebi que se o modelo chamar `atacar_com_aliado` E `atacar` na mesma mensagem
  (cenário natural: "você e Bob atacam"), os inimigos reagiriam DUAS vezes numa rodada só
  — um bug de dano dobrado, não um recurso. A ação do aliado é "de graça"; é a ação do
  próprio herói que fecha a rodada. Documentado no ADR e nos comentários do código, não
  escondido.

## Como testei

**353 testes de backend** (eram 335 no fim da Fase 2) — 18 novos cobrindo
`combat.turno_aliado` (acerto, erro, morte do inimigo, sem inimigo vivo),
`recrutar_aliado` (grava no roster, clampa HP, rejeita nome duplicado, entra ou não em
`c_state` dependendo de estar em combate), `atacar_com_aliado` (erro sem combate, erro com
aliado morto/inexistente, resolve o ataque, NÃO aciona reação dos inimigos, concede XP na
vitória) e `sincronizar_aliados` (copia HP de combate pro roster, ignora aliados que não
estavam na luta).

**Ao vivo, contra a Groq de verdade** (via `fetch()` direto na sessão do navegador,
sessão autenticada, sem passar pela UI de criação de personagem): criei um personagem,
pedi pra recrutar um NPC — o modelo chamou `recrutar_aliado` sozinho, e por conta própria
também chamou `gastar_ouro` pra "pagar" pelo serviço, sem eu ter pedido isso
explicitamente. `aliados` voltou certinho na resposta: `Finn, Batedor, HP 10/10`. Depois
provoquei um combate, e `iniciar_combate` levou Finn pra dentro da luta corretamente.

**O que NÃO confirmei ao vivo**: se o modelo chama `atacar_com_aliado` de forma
consistente quando o jogador dirige a ação do companheiro. Consegui uma tentativa onde o
modelo resolveu tudo só com `atacar` (ignorando a instrução "Finn ataca..."), e as
tentativas seguintes bateram em rate limit da Groq (429 repetido, provavelmente
consequência do teste rápido consumindo a cota compartilhada) antes de eu conseguir
confirmar um `atacar_com_aliado` disparado pelo modelo. A ferramenta em si está
exaustivamente testada por pytest — o que falta é a mesma lição da Etapa 6/da lição
"testar LLM cedo": só o teste ao vivo pega "o modelo não chama a ferramenta", e este
ainda não fechou o ciclo completo. Fica registrado como pendência, não como confirmado.

## Decisões tomadas

- Sem ADR novo nesta fase — usa o ADR-0027 (Fase 2), que já cobria a revisão de escopo
  necessária pra companheiros mecânicos existirem.
- CA/bônus de ataque/dano do aliado são fixos (não propostos pelo modelo) — mesmo
  princípio de todo número novo desta revisão de gameplay.

## Números

- 353 testes de backend passando (+18), `ruff check` e `tsc --noEmit` limpos.
- Migration `0011` aplicada com sucesso no banco de desenvolvimento real.
- 1 fluxo completo verificado ao vivo (recrutar → aliado aparece no roster → entra em
  combate); `atacar_com_aliado` via modelo real ainda pendente de confirmação.

## Próximo passo

Um golden case em `evals/golden/` pra fechar a pendência acima seria o ideal antes de
seguir — mas as próximas fases do plano (4: esqueleto de Atos, 5: locais inventados) não
dependem da 3 e podem vir primeiro. Decisão de ordem fica para a próxima conversa.
