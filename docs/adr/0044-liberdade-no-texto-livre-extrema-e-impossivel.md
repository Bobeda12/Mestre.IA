# ADR-0044 — Liberdade no texto livre: desvio aceito, dificuldade "extrema" e "impossível"

**Data:** 07/10/2026
**Status:** Aceito
**Etapa:** Plano "Texto livre confiável e progressão" (Fase 2)
**Supersede:** —

---

## Contexto

O jogador sentia o Mestre rígido: ao fazer algo que não combinava com a história (largar
o objetivo, ir nadar num lago), a narração tentava voltar ao "caminho certo". Lido no código:

- O prompt tratava o passo da trilha como rumo a conduzir ("narrar a cena na direção dele").
- Alvo não registrado voltava como erro seco; o modelo gastava os passos tentando consertar.
- A Lei da Verossimilhança (a regra que dá peso às consequências) era cortada com
  frequência pelo teto de 1800 caracteres das regras, por desempate de relevância.
- Só havia três dificuldades (CD 10, 15, 20). Algo literalmente impossível ainda tinha chance.

## Decisão

**1. Desvio é aceito.** O contrato do narrador diz que o jogador é livre, inclusive para se
desviar do objetivo; o relógio do mundo e os conflitos seguem avançando (isso já era do
Mundo Vivo) e o passo da trilha é só "um rumo": a história se adapta ao que o jogador fez.

**2. Duas dificuldades novas em `resolver_intencao`.**
- `extrema`: CD 24. Muito difícil e ainda possível; só quem tem atributo alto e sorte consegue.
- `impossivel`: sem rolagem, sem dano, sem mudança no mundo. O servidor devolve
  "tenta e não consegue" e o Mestre narra. Os efeitos de sucesso e falha deixam de ser
  obrigatórios nesse caso.

**3. Erros que orientam.** Alvo não registrado agora pede ao modelo para registrar a cena e
repetir, ou narrar a tentativa e o mundo reagindo, nunca recusar.

**4. A Lei da Verossimilhança entra sempre** nas regras (447 caracteres), e o corte por
relevância vale só para o resto. O orçamento total de regras passou de 1800 para 1500.

## Consequências

- O prompt de entrada ficou em 15436 caracteres (antes 15956): o teste de orçamento
  (`test_benchmark_nao_cresce_com_resumo_inteiro`, teto 16000) segue verde. As regras
  situacionais ganham ~300 caracteres a menos de espaço.
- "Muito difícil" e "impossível" dependem de o modelo escolher a dificuldade certa. Isso só
  se mede ao vivo.
- **Um erro de leitura meu, corrigido no meio:** a primeira versão tratou "ação absurda" como
  "impossível", com dano automático na falha. Não era o que o jogador queria; o dano saiu.

## Alternativas descartadas

- **Dano automático em tentativa absurda.** Pune quem tenta; o jogador pediu o contrário.
- **Perguntar "tem certeza?" antes de uma ação fora de contexto.** Quebra o ritmo.
