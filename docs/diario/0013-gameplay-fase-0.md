# Revisão de gameplay — Fase 0 (fundações do motor)

**Período:** 25/08/2026 · uma sessão com o Claude Code · **estimado no plano:** 34h (Fase
0 de 9, `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`)

## O que eu queria com essa fase

Recebi um documento novo (`gameplay_v2.md`) com 9 ideias de gameplay. Antes de codar
qualquer coisa, precisava saber se isso era território novo ou se já tinha sido planejado
— e era: `docs/backlog-pos-lancamento.md` já tinha quase tudo isso como Etapa 12/13, só
que nenhuma das duas rodou (o projeto foi direto pra Etapa 14, de visual). Então a fase 0
não é "greenfield": é destravar o resto do plano com o que o combate e a economia de XP
precisam antes de qualquer verbo tático ou aliado existir.

## O que mudou

- **Bestiário por banda**: `data/monsters.json` foi de 5 monstros em 2 categorias
  (`Nivel_1`, `Chefe`) pra 5 bandas (`Nivel_1` a `Nivel_4`, `Chefe`), ~13 monstros.
  `data_manager.get_monstros_por_banda(banda)` é a nova função que lê isso.
- **Escalonamento de perigo**: `rules_engine.desafio_sugerido(nivel_heroi)` devolve quais
  bandas cabem no nível do herói; `narrator.montar_contexto` injeta isso como
  `[DESAFIO SUGERIDO]` quando não há combate ativo, pro modelo nunca propor um Dragão
  Jovem pra um herói nível 1.
- **XP fora de combate**: ferramenta nova `concluir_objetivo(objetivo)` — XP fixo (50, o
  valor de um monstro Nível 1), não proposto pelo modelo. Antes disso, um jogador que
  resolve tudo conversando nunca subia de nível.
- **Vantagem e desvantagem**: `resolver_ataque`/`resolver_teste_atributo` agora aceitam
  `vantagem: bool | None` e rolam dois d20 quando ela não é `None`. `DadosRolagem` e o
  `RollCard` já sabem mostrar os dois dados — mas nada ainda os aciona (isso é ferramenta
  de combate, Fase 1).
- **`Inimigo.comportamento`**: campo que já existia em `data/monsters.json` e era lido e
  descartado por `combat._criar_inimigo` — agora sobrevive até o `Inimigo`. A IA de
  inimigo que efetivamente usa isso pra recuar/ganhar vantagem também é Fase 1.
- `ADR-0026`, este diário, e uma passada em `docs/backlog-pos-lancamento.md` marcando
  C-1, C-2, C-3, C-7, D-1 a D-4 e D-6 como superados por este plano (com ponteiro pra
  fase certa), e corrigindo o P-4 (já estava resolvido, o documento é que estava
  desatualizado).

## O que achei no caminho

**Um WIP não commitado já era, sem querer, o começo da Fase 4.** Antes de mexer em
`narrator.py`/`tools.py`, `git diff` mostrou mudanças não commitadas: `atualizar_missao`
já ligado ao `QuestLog`, e um `[PASSADO]` já injetado no contexto com o `historia_texto`
do herói. Não era trabalho perdido nem divergente — era exatamente o alicerce que a Fase
4 (esqueleto de Atos) vai precisar. Preservei em vez de descartar.

**A curva de XP encurtada e a persistência de `historia_texto` já estavam prontas.** O
backlog antigo listava as duas como problema aberto (P-1 parcial, P-4 inteiro). Rodar uma
investigação no código antes de planejar (em vez de confiar no documento) achou as duas
já resolvidas — só faltava o ADR de uma, e a correção da linha do backlog na outra.

## Decisões tomadas

- [ADR-0026](../adr/0026-curva-de-xp-propria-e-escalonamento-de-perigo.md) — curva de XP
  própria (retroativo), XP fora de combate, e por que o valor é fixo e não proposto pelo
  modelo.
- Lição ainda não escrita — a fase é mecânica (motor puro, sem I/O, sem surpresa de
  produção); a lição real desta revisão de gameplay deve esperar a Fase 1 ou 2, onde tem
  mais chance de aparecer algo que valha ensinar.

## Números

- 306 testes de backend passando no fim da fase (mesma suíte + 15 testes novos: vantagem/
  desvantagem em ataque e teste de atributo, escalonamento de perigo, `comportamento`
  copiado pro `Inimigo`, `concluir_objetivo`).
- `tsc --noEmit` limpo no frontend (mudança em `RollCard.tsx` é aditiva — nenhum caminho
  existente muda de comportamento até a Fase 1 acionar `vantagem`).

## Próximo passo

Fase 1 (núcleo tático de combate): ferramentas `esquivar`/`defender`/`investir`/
`esconder_se`/`fugir`, a tag `[OPCOES]` com botões no frontend, e a IA de inimigo lendo
`comportamento` de verdade em `combat.turno_inimigos`.
