# Fase 3 do plano "jogo completo": level-up com escolha

**Período:** 08/09/2026 · mesma sessão das Fases 0 a 2

## O que aconteceu

Subir de nível era invisível: PV aumentava, uma técnica aparecia em 3 e 7, o Foco crescia
em 4 e 8, e o jogador não decidia nada. A única decisão de progressão que existia (a
especialização explorador/diplomata/combatente dos marcos 3 e 7) ficava escondida num
canto do painel do mundo — e o narrador tinha uma ferramenta para escolher no lugar do
jogador. Esta fase transforma cada subida de nível num momento com decisão. A regra está
no [ADR-0034](../adr/0034-progressao-com-escolha-do-jogador.md).

## O que o jogador sente

- **Ao subir de nível, um modal abre** (fora de combate) com as opções daquele nível: +1
  num atributo (mostra "Força 15 → 16") ou um talento; nos níveis 3 e 7, a especialização.
  Uma escolha por nível. "Decidir depois" fecha o modal até a próxima subida; a pendência
  fica registrada e o narrador lembra com uma frase, sem decidir.
- **Talentos são números que aparecem na hora.** "Couro duro" soma 1 na Defesa do HUD
  assim que é escolhido; "Mestre de armas" soma 1 em todo dano; "Robusto" dá 1 PV por
  nível, contando os que já passaram; "Sortudo" dá vantagem em testes de Destreza (o card
  mostra os dois d20); "Olho de mercador" barateia a compra em 15%.
- **Subir Constituição** o bastante para mudar o modificador dá PV retroativo, como no 5e.

## O que mudou por baixo

- `services/talents.py`: 7 talentos comuns e 1 por classe, com nível mínimo em alguns.
  Cada efeito é um número num canal que o motor já tinha: dano vai para
  `bonus_especializacao`, Defesa para `calcular_defesa(bonus_extra)`, vantagem para
  `rolar_teste`, desconto para `preco_compra`.
- `WorldState.niveis_pendentes` e `talentos` (JSON, sem migration). `_aplicar_xp` deixa a
  escolha pendente; `ToolExecutor.escolher_nivel` aplica e recalcula Defesa e dano.
- `escolher_nivel` existe só na rota `/game/action`, nunca como ferramenta do narrador
  (mesma regra de `escolher_especializacao` desde a Fase 0).
- `painel_progressao` passa a mandar pendências, talentos e especializações; o prompt
  ganha `[PROGRESSÃO]` só quando há algo a dizer.

## Como testei

- 12 testes novos (`tests/test_talents.py`) e um de rota: pendência ao subir, opções por
  nível (teto 20, nível mínimo, marcos de especialização), atributo com CON retroativa,
  Defesa com talento sobrevivendo ao equipar, dano com talento igual ao sem talento mais
  um, vantagem e Robusto, escolha inválida ou em combate, a rota resolvendo e limpando a
  pendência. Suíte: 524 verdes; ruff, mypy e typecheck limpos.
- No navegador: herói colocado no nível 2 com escolha pendente, modal aberto ao carregar
  com os seis atributos e os talentos, clique em "Couro duro" → Defesa 16 → 17 no HUD,
  evento "⭐ Nível 2: talento Couro duro" no chat, modal fechado.

## O que ficou registrado para depois

- A vitrine do painel do mundo mostra o preço sem o desconto de talento; a compra real
  (`comerciar`) aplica. Ajustar quando o painel receber o executor.
- Balancear os talentos por simulação junto com o bestiário alto (Fase 5).

## Próximo passo

Fase 4: arcos com final (`abrir_arco`/`encerrar_arco` verificáveis pelo servidor, desfecho
gerado por IA, recompensa e capítulo na crônica).
