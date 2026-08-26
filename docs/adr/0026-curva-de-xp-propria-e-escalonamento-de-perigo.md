# ADR-0026 — Curva de XP própria, XP fora de combate e escalonamento de perigo pelo servidor

**Data:** 25/08/2026
**Status:** Aceito
**Etapa:** Revisão de gameplay (Fase 0 de 9 — ver `docs/backlog-pos-lancamento.md`, Etapa 12/13)
**Supersede:** —

---

## Contexto

Três lacunas do motor de regras (`Backend/app/services/rules_engine.py`), levantadas ao
reconciliar `gameplay_v2.md` (documento trazido pelo usuário) com o backlog já existente:

1. **A curva de XP diverge do SRD 5e** desde antes deste ADR — `XP_POR_NIVEL = {1:0,
   2:300, 3:900, 4:2700, 5:6500}` e `NIVEL_MAXIMO=5` (a tabela real do livro vai até o
   nível 20, com limiares muito mais altos). A divergência já existia no código (comentário
   em `rules_engine.py:27-30` citando "D&D 5e enxuto", `PLANO_MESTRE.md §9.2`), mas nunca
   tinha um ADR próprio — é uma dívida que este documento cobre retroativamente.
2. **XP só vem de abater inimigo.** `ToolExecutor._conceder_xp` (`tools.py`) é a única
   fonte; um jogador que resolve tudo por diplomacia, furtividade ou enigma nunca sobe de
   nível, mesmo tendo "jogado bem" — pune exatamente o estilo que o narrador deste projeto
   faz melhor (theater-of-the-mind, não grind de combate).
3. **Nada impede o modelo de propor um encontro descalibrado.** `narrator.montar_contexto`
   nunca disse ao LLM que bandas de `data/monsters.json` cabem no nível do herói — o
   bestiário (5 monstros em 2 categorias antes desta etapa) também não tinha graduação
   suficiente para a pergunta fazer sentido.

## Decisão

- **Curva de XP própria fica como está, formalizada por este ADR** (não é reescrita — só
  passa a ter registro formal do porquê).
- **Nova ferramenta `concluir_objetivo(objetivo)`** concede um XP fixo do servidor (50,
  igual ao XP de um monstro de Nível 1 — `ToolExecutor.XP_OBJETIVO_NAO_COMBATE`) quando o
  modelo sinaliza que um objetivo narrativo foi cumprido sem combate. O **valor não é
  proposto pelo modelo** — ele só decide o "quando" (chamar a ferramenta), nunca o
  "quanto" — mesmo princípio de fronteira de confiança do ADR-0006.
- **Bestiário expandido para 5 bandas** (`Nivel_1` a `Nivel_4`, mais `Chefe`), ~13
  monstros no total (`data/monsters.json`).
- **Nova função `rules_engine.desafio_sugerido(nivel_heroi)`**, injetada no prompt como
  `[DESAFIO SUGERIDO]` (`narrator.montar_contexto`): o servidor decide quais bandas do
  bestiário são compatíveis com o nível atual do herói; o modelo continua só propondo
  nomes de monstro dentro delas. `iniciar_combate` (`services/combat.py`) já descartava
  nomes fora do bestiário desde a Etapa 3 — isto é orientação prévia, não a única
  barreira, e não substitui essa validação.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| XP não-combate proposto pelo modelo (`concluir_objetivo(objetivo, xp)`) | Flexível, o modelo calibra pelo peso da cena | Reabre a porta que o ADR-0006 fechou — dificuldade/recompensa vira decisão do LLM, não do servidor | O valor fixo é menos expressivo, mas mantém a garantia central do projeto: o motor decide números |
| Voltar à tabela cheia do SRD (20 níveis) | Fidelidade ao livro | A campanha é curta (poucas sessões, teste com amigos) — nunca chegaria nem perto do nível 20; a Etapa 12 antiga (backlog) já tinha decidido o oposto | Curva enxuta já é a decisão vigente, só faltava o ADR |
| Escalonamento de perigo como regra rígida (`iniciar_combate` rejeita monstro fora da banda) | Impossível o jogador enfrentar algo descalibrado | Cenas legítimas de fuga/observação de um perigo acima do nível ficariam impossíveis de narrar | `[DESAFIO SUGERIDO]` é orientação no prompt, não trava dura — a trava dura já existe (nome fora do bestiário) e continua |

## Consequências

**Ganhamos:**
- Progressão possível fora de combate — resolve a metade "P-1" do problema documentado no
  backlog antigo (a outra metade, o próprio encurtamento da curva, já estava resolvida).
- Um vocabulário (`[DESAFIO SUGERIDO]`) que a Fase 1 (verbos táticos) e a Fase 6 (encontros
  aleatórios de viagem) do plano de gameplay reaproveitam sem reinventar a lógica de banda.

**Pagamos:**
- `XP_OBJETIVO_NAO_COMBATE = 50` é um chute informado, não um valor balanceado por
  simulação — `evals/simulador.py` (Etapa 12a antiga, ainda não escrito) é quem vai
  confirmar ou corrigir esse número.
- O bestiário novo (Orc, Aranha Gigante, Capitão Bandido, Ogro, Harpia, Múmia, Troll,
  Espectro, Dragão Jovem) tem estatísticas de primeira passada, não simuladas — mesma
  ressalva.

**Fica em aberto:**
- Rodar `evals/simulador.py` contra o bestiário novo e gerar
  `docs/relatorios/0002-balanceamento.md` (a etapa de "fundações do motor" do plano de
  gameplay pede isso explicitamente, ainda pendente).

## Como saber que erramos

- Se o XP fixo de `concluir_objetivo` fizer o jogador subir de nível muito mais rápido
  narrando do que lutando (ou o oposto), o valor precisa mudar — o simulador mostra isso
  comparando turnos-até-nível-2 pelos dois caminhos.
- Se `[DESAFIO SUGERIDO]` for ignorado pelo modelo com frequência (ele propõe monstro fora
  da banda sugerida, mesmo dentro do bestiário), isso é sinal de que a orientação por
  prompt não é suficiente e a trava precisa virar regra rígida em `iniciar_combate`.

## Referências

- ADR-0006 — LLM não é motor de regras (base de toda a fronteira "modelo propõe, servidor decide" reaplicada aqui)
- `docs/backlog-pos-lancamento.md`, itens C-1/C-2 (bestiário por banda, economia de XP — antecessores nunca executados deste ADR)
- `PLANO_MESTRE.md §9.2` — decisão de escopo "D&D 5e enxuto"
