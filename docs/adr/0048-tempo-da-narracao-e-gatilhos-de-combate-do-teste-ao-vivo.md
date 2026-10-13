# ADR-0048 — Tempo da narração, gatilhos de combate e pessoa como alternativa (achados do teste ao vivo)

**Data:** 13/10/2026
**Status:** Aceito
**Etapa:** Plano "Texto livre confiável e progressão" (pós-Fase 4)
**Supersede:** —

---

## Contexto

O teste ao vivo ([relatório 0008](../relatorios/0008-teste-ao-vivo-fases-1-a-4.md)) rodou as Fases 1 a 4 contra
o Gemini real. O que passou sem mudança (violência vira combate, o morto não fala, impossível não rola) confirma
as decisões dos ADR-0043 e 0044. Três falhas apareceram, nenhuma delas visível em teste automático.

## Decisão

**1. Gatilhos de combate mais amplos.** O grupo de ferramentas de combate abre com as raízes `atac`, `lut`,
`combat`, `agredir`, `duel`, `batalh`, `enfrent` e `brig` (antes: `atac`, `lutar`, `combate`, `agredir`). A
detecção de violência por verbo (ADR-0043) continua valendo à parte.

**2. Narração também gasta tempo.** `_tempo_da_narracao` (em `routers/game.py`, chamado em `/chat` e
`/chat/stream`) avança 10 minutos quando o turno não consumiu a ação por ferramenta e não há combate. Reaproveita
`avancar_tempo`, o mesmo caminho de toda ação, então conflitos, consequências e remessas andam.

**3. Papel de pessoa sem ficha no nível cai em outra pessoa.** `arquetipos.escolher` devolve uma ficha de papel
qualquer do nível quando o papel pedido é reconhecido mas não existe ali, em vez de deixar o sorteio de criaturas
escolher. Papel que não é de pessoa (dragão, lobo) continua no sorteio comum.

## Consequências

- Um turno de conversa sem ferramenta agora cobra 10 minutos. Conflitos com `intervalo` curto avançam um pouco
  mais rápido em jogo de muita conversa. O ritmo é o mesmo de uma ação comum.
- O nível 1 só tem ladino, bruto e mago; um "guarda" ou "nobre" de nível 1 vira um desses três. Uma ficha de guarda
  no nível 1 resolveria melhor; fica como decisão de conteúdo.
- O roteiro `scripts/teste_ao_vivo.py` passa a existir como ferramenta repetível, com teto de requisições, banco
  descartável e embeddings falsos.

## Alternativas descartadas

- **Cobrar tempo só quando o modelo chamar `descansar`.** Dependeria de o modelo lembrar, o mesmo problema que o
  ADR-0043 resolveu para a morte.
- **Avançar mais que 10 minutos por turno de narração.** O servidor não sabe se foi um aceno ou uma tarde; 10
  minutos é o piso seguro. Para "a tarde toda" o modelo usa `descansar` ou `mover`.
