# Revisão de gameplay — Fase 1 (núcleo tático de combate)

**Período:** 25/08/2026 · uma sessão com o Claude Code · **estimado no plano:** 30h (Fase
1 de 9, `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`)

## O que eu queria com essa fase

A Fase 0 destravou o motor (bestiário por banda, vantagem/desvantagem, `comportamento`
guardado no `Inimigo`), mas nada ainda usava essas peças. O combate continuava sendo
"atacar ou nada" — sem fugir, sem recuar, sem o bestiário cumprir o que promete
(`monsters.json` diz que o Kobold foge sozinho e o Goblin ataca e foge; nada disso
rodava). Esta fase é onde essas peças viram jogo de verdade.

## O que mudou

- **Cinco ferramentas novas de combate** (`tools.py`): `esquivar` (desvantagem pros
  inimigos até a próxima rodada), `defender` (+2 CA), `investir` (-2 no acerto, +50% no
  dano — o botão de risco), `esconder_se` (teste de Destreza; sucesso impede o inimigo de
  te achar) e `fugir` (teste de Destreza; sucesso encerra o combate, falha custa uma
  rodada de ataque livre). Cada uma resolve no servidor sem depender do modelo interpretar
  a intenção — mesmo princípio do `atacar` que já existia.
- **`usar_item` passou a gastar a ação do herói em combate** — antes disso, beber uma
  poção no meio de uma luta era de graça, os inimigos nunca reagiam.
- **IA de inimigo de verdade**: `combat.turno_inimigos` agora lê `Inimigo.comportamento`
  por palavra-chave (não é geração, são `if`s) — foge se sozinho, recua abaixo de 30% de
  HP, ganha vantagem em matilha se há aliado vivo. Vantagem e desvantagem de fontes
  diferentes (uma ação tática do herói × o comportamento do próprio inimigo) se cancelam,
  seguindo a regra real do 5e.
- **Tag `[OPCOES]`**: o narrador termina toda narração com `[OPCOES]: opt1|opt2|opt3`; o
  servidor extrai a tag antes de persistir (`guardrail.extrair_opcoes`) e o frontend
  esconde a cauda dela ao vivo enquanto ainda está chegando (`esconderTagOpcoes`),
  transformando em três botões que preenchem a caixa de texto — nunca enviam sozinhos.
- **Testes de morte visíveis**: `sucessos_morte`/`falhas_morte` (já calculados desde a
  Etapa 7) agora saem no frame `state`; o HUD desenha escudos/caveiras enquanto o herói
  está caído.
- **Um bug encontrado testando ao vivo, não pelos testes**: o frontend tratava *qualquer*
  `hp_atual <= 0` como fim de jogo, cobrindo a tela com "GAME OVER" no instante em que o
  herói caía — antes mesmo do primeiro teste de morte rodar. `c_state.resultado` nunca
  saía do backend; adicionei `resultado_combate` na resposta e troquei o gatilho da tela
  de "hp ≤ 0" para "resultado_combate === 'morte'". Sem isso, os testes de morte visíveis
  que acabei de construir nunca apareceriam — a tela cobriria tudo antes.

## O que achei no caminho

**Um bug de duplicação de texto que só apareceu jogando de verdade.** Ao mover a limpeza
da tag `[OPCOES]` para dentro do fluxo de streaming, guardei o texto cru acumulado numa
`ref` mutada *dentro* do updater de `setMessages`. Isso parece inofensivo, mas o
StrictMode do React invoca updaters de estado duas vezes de propósito (para achar efeitos
colaterais escondidos) — e mutar uma ref é exatamente esse tipo de efeito colateral. O
resultado: cada pedaço de texto entrava duas vezes, e a narrativa saía com cada sílaba
repetida ("A voz voz tro trovej..."). `tsc` e os testes de backend não pegam isso — só
apareceu ao testar no navegador de verdade, exatamente como a lição da Etapa 10 já tinha
registrado sobre RNG fixo não pegar "o modelo não chama a ferramenta". A correção: o texto
cru precisa viver *na mensagem* (um campo `raw` no estado do React), não numa ref — assim
o updater volta a ser puro, e chamá-lo duas vezes não muda o resultado.

**O combate ao vivo confirmou o resto funcionando de primeira**: o modelo chamou
`atacar` corretamente, terminou a narração com `[OPCOES]` no formato certo, e os três
botões apareceram na tela ("Procurar mais inimigos", "Dizimar o corpo", "Voltar para a
taverna") sem a tag crua vazar pro jogador. O herói caiu a 0 PV, `resultado_combate` ficou
`null` por duas rodadas de teste de morte (2 falhas, depois 1 sucesso) sem disparar GAME
OVER — o comportamento que a correção do bug acima deveria produzir.

## Decisões tomadas

- Sem ADR nesta fase — é trabalho aditivo (ferramentas novas, leitura de um campo que já
  existia, um bug corrigido), não uma divergência de decisão registrada em lugar nenhum.
- CD 12 para `esconder_se`/`fugir` é valor de primeira passada, como o XP de
  `concluir_objetivo` na Fase 0 — ajustar depois com `evals/simulador.py`, não chutar de
  novo.

## Números

- 329 testes de backend passando (eram 306 no fim da Fase 0) — 23 testes novos: 5 para
  IA de inimigo por comportamento, 12 para as ferramentas táticas, 4 para `extrair_opcoes`,
  mais os que já existiam ajustados.
- `ruff check` limpo, `tsc --noEmit` limpo.
- Um combate real jogado do início à queda do herói, ao vivo contra a Groq — não só
  cenário roteirizado.

## Próximo passo

Fase 2 (refactor do motor para múltiplos alvos amigos) — pré-requisito estrutural pra
Fase 3 (aliados mecânicos). É o item de maior risco do plano inteiro e precisa de um ADR
revisando a decisão de escopo §9.3.
