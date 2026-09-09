# ADR-0035 — Arcos com final verificável pelo servidor

**Data:** 08/09/2026
**Status:** Aceito
**Etapa:** Plano "jogo completo" (Fase 4 — ver `docs/diario/0030-fase-4-arcos-com-final.md`)
**Supersede:** o esqueleto de Atos removido no ADR-0032 (este ADR é a resposta desenhada para o buraco que aquele deixou)

---

## Contexto

Com o mundo emergente (ADR-0032) a campanha perdeu os "capítulos" que os Atos davam de
graça: só a morte encerrava alguma coisa, e a Crônica não tinha marcos de fechamento. O
autor escolheu "arcos com final": um conflito grande pode ser fechado com desfecho gerado
por IA, recompensa e capítulo na crônica, e o herói segue vivo para o próximo arco.

O risco óbvio: se o narrador decidir quando o arco acaba, ele acaba quando o modelo quer
(cedo, tarde, ou nunca — exatamente o problema dos Atos).

## Decisão

1. **Um arco é um conflito central com título** (`Arco` em `MundoVivo.arcos`). A origem
   emergente abre o arco 1 a partir do conflito da origem; depois, `abrir_arco` (só sem
   arco ativo, só com conflito existente e ativo).
2. **O servidor decide quando pode encerrar** (`condicoes_arco`), sem LLM: pelo menos 8
   turnos no arco, pelo menos 2 fatos registrados desde a abertura, e o conflito central
   **resolvido** (→ `acordo`), **concretizado** (→ `consequencia`) ou o **chefe do arco
   enfrentado** (→ `vitoria_chefe`). `encerrar_arco` fora disso devolve o que falta; o
   narrador só pode tentar uma vez por turno. Abandonar é decisão do jogador, pela
   interface, sem recompensa.
3. **A recompensa é determinística**: XP `60 + 20 × nível`, ouro e itens de
   `data/loot.json["arco"]` por faixa de nível; consequência vale metade e sem item.
4. **O desfecho é narrativo e separado da recompensa**: `gerar_desfecho_arco` é uma
   chamada isolada no molde do epitáfio, só com os marcos do arco, gerada uma vez e gravada
   no arco e na memória de longo prazo (tipo `arco`), de onde a Crônica a lê como capítulo.
   Sem modelo, o desfecho é a lista de marcos.
5. **O jogador vê o checklist**: o painel do mundo mostra o arco atual, o que falta e os
   botões "Encerrar capítulo" (só quando o servidor confirma) e "Abandonar".

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| O narrador decide o fim (`encerrar_arco` sem condições) | Flexível | É o Ato de volta: fim quando o modelo quer | O servidor tem os três sinais (turnos, fatos, estado do conflito) e não custa nada checar |
| Encerrar automaticamente quando o conflito resolve | Zero atrito | Tira do jogador o momento de fechar o capítulo e pode cortar uma cena no meio | O botão existe e o narrador pode chamar quando a cena pedir |
| Recompensa proposta pelo modelo | "Justa" para a história | Número do LLM (ADR-0006) | Tabela por faixa de nível, como o saque |

## Consequências

**Ganhamos:** capítulos com começo e fim que a Crônica reconhece; a tese do projeto ("o
juiz decide, o narrador narra") aplicada à estrutura da campanha, não só ao dado.

**Pagamos:** duas tools a mais fora de combate e uma linha `[ARCO ATUAL]`; uma chamada
extra ao modelo no turno em que o arco fecha.

**Fica em aberto:** os limiares (8 turnos, 2 fatos) são chute informado; ajustar com
partidas reais. `WorldState.relogios` continua sem uso e pode sair.

## Como saber que erramos

- Se o modelo insistir em `encerrar_arco` todo turno, o prompt precisa de um "só quando a
  cena pedir" mais forte (ou o limite de uma tentativa por turno já basta — medir).
- Se arcos nunca fecharem porque `registrar_fato` raramente é chamado, a condição de
  fatos deve contar marcos de qualquer fonte, não só os do narrador.

## Referências

- ADR-0032 — mundo emergente puro; ADR-0033 — catálogo de itens (recompensa)
- Plano "jogo completo", Fase 4
