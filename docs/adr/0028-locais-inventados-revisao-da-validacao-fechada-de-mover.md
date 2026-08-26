# ADR-0028 — Locais inventados: revisão da validação fechada de `mover`

**Data:** 25/08/2026
**Status:** Aceito
**Etapa:** Revisão de gameplay (Fase 5 de 9 — ver `docs/backlog-pos-lancamento.md`, Etapa 12/13)
**Supersede:** revisa o comportamento de `services/tools.py:mover` desde a Etapa 4

---

## Contexto

`mover()` (Etapa 4) sempre validou o destino contra `data/locations.json`: se o nome não
batia exatamente com um dos locais do catálogo, o movimento era recusado e o servidor
devolvia a lista de locais válidos. Essa validação existe por um motivo concreto,
documentado desde a Etapa 11 (B-7, resolve P-5): o prólogo já tinha inventado locais fora
do catálogo ao vivo ("Ruínas de Gralhoth", "Ruínas de Acheron"), e `mover` recusava o
próprio local onde o herói nascia. A correção da Etapa 11 foi validar o prólogo contra o
catálogo; `mover` já fazia isso desde antes.

`gameplay_v2.md` (documento trazido pelo usuário) pede o oposto para o resto do jogo: que
o narrador possa inventar locais em qualquer momento, não só nos 7 do catálogo fixo, e que
esses locais "existam de verdade" — sejam reconhecidos em turnos futuros, não apenas
narrados uma vez e esquecidos.

## Decisão

**A validação fechada não é removida — ganha uma segunda porta, controlada pelo
servidor.** `mover(destino, descricao_proposta=None)`:

1. Primeiro verifica `w_state.locais_descobertos` (por personagem — dois heróis podem
   descobrir "A Torre Caída" em cenas diferentes sem colidir), depois o catálogo global
   `data/locations.json`. Se achou em qualquer um dos dois, move — comportamento inalterado.
2. Se não achou em nenhum dos dois **e** `descricao_proposta` foi passada, o servidor
   **registra** o local em `w_state.locais_descobertos` (clima herdado da cena atual,
   descrição vinda da proposta) e só então move.
3. Se não achou **e não veio descrição**, o comportamento é exatamente o de antes: erro,
   com a lista de locais válidos (agora incluindo os já descobertos nesta sessão).

O ponto central, e por que isto não reabre o problema que a Etapa 11 fechou: **o modelo
nunca escreve em `w_state` diretamente.** Ele PROPÕE uma descrição; quem decide se ela
vira um local de verdade — e grava isso — é sempre `mover()`, no servidor. Mesmo padrão
de fronteira de confiança do ADR-0002 (revalidação de point-buy) e do ADR-0006 (LLM não é
motor de regras), aplicado agora à existência de um lugar, não a um número.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Deixar o narrador escrever `world_state.local` livremente, sem ferramenta | Zero fricção pro modelo | Reabre exatamente o buraco que a Etapa 11 fechou — o motor nunca saberia se aquele lugar existe, `mover` não teria como validar contra ele depois | Contraria o próprio motivo de `mover` existir |
| Uma ferramenta nova (`propor_local`) separada de `mover` | Separação de conceitos mais limpa | Duas ferramentas pra uma ação só ("ir a algum lugar") — o modelo precisaria decidir qual chamar, mais uma fonte de erro | `mover` com um parâmetro opcional já é a variante que o próprio plano de revisão previu |
| Local descoberto entra direto no catálogo global (`data/locations.json`) | Persistiria entre TODOS os personagens, não só um | Editar um arquivo JSON em disco a partir de uma request é um efeito colateral fora do padrão do projeto (estado de jogo vive no banco, não em arquivo) — e um lugar que um herói inventou não devia aparecer pronto na campanha de outro | `WorldState` (por personagem) é o lugar certo — mesmo raciocínio de por que `combat_state`/`quest_log` são colunas por `Personagem`, não globais |
| IA também gera o clima do local novo | Mais "criativo" | Mais um número/atributo confiado ao modelo sem necessidade — clima não muda a mecânica, mas é o tipo de decisão que a Fase 0 já reservou pro servidor | Herdar o clima da cena atual é suficiente e determinístico |

## Consequências

**Ganhamos:**
- O mundo cresce durante o jogo sem exigir edição manual de `data/locations.json` —
  atende o pedido central do `gameplay_v2.md` §2 ("Locais Abertos").
- A garantia original (motor nunca referencia lugar que não conhece) sobrevive intacta —
  só o *quando* de um local passar a existir mudou (tempo de jogo, não só arquivo).

**Pagamos:**
- `w_state.locais_descobertos` cresce sem limite ao longo de uma campanha longa — não há
  poda nem consolidação. Aceitável na escala de uma sessão de portfólio; se virar um
  volume de dado real, revisitar.
- Um local inventado numa sessão não aparece nas de outro personagem — é o comportamento
  correto (ver alternativas), mas vale deixar explícito: não existe "mundo compartilhado"
  entre heróis diferentes, e não é este ADR que muda isso.

**Fica em aberto:**
- Vilas-chave continuam hardcoded no catálogo, como o `gameplay_v2.md` pediu — este ADR
  não promove nenhum local descoberto ao catálogo global automaticamente.
- Se `descricao_proposta` virar um vetor de abuso (o modelo "descobrindo" locais
  absurdos pra contornar alguma regra) — não observado ainda, mas é o sinal de "como
  saber que erramos" abaixo.

## Como saber que erramos

- Se o modelo começar a "descobrir" locais em vez de usar os já existentes do catálogo
  quando um deles serviria (ex: inventar "Vila de Pedraverde" quando "Vila de Phandalin"
  já resolveria a cena) — sinal de que o prompt precisa deixar mais claro que o catálogo
  vem primeiro.
- Se `w_state.locais_descobertos` virar um volume de dado que pese na resposta de
  `load_game` — hora de considerar poda ou paginação.

## Referências

- ADR-0002 — revalidação de regras no servidor (mesmo padrão "propõe/decide")
- ADR-0006 — LLM não é motor de regras
- `docs/backlog-pos-lancamento.md`, P-5 e Etapa 11 (B-7) — o problema original que a validação fechada resolveu
- `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`, Fase 5
