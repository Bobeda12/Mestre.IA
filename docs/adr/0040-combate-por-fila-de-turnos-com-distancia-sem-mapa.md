# ADR-0040 — Combate por fila de turnos, com ação / bônus / movimento e distância sem mapa

**Data:** 06/10/2026
**Status:** Aceito
**Etapa:** Plano "Trilha do capítulo + Combate v2" (Fases 4 e 5)
**Supersede:** — (revisa o escopo "5e enxuto, sem grid" do PLANO_MESTRE §9.2 e a decisão do ADR-0027 de que o aliado só ataca quando o herói manda)

---

## Contexto

O combate resolvia, em um clique, a ação do herói e a rodada inteira dos inimigos
(`ToolExecutor._resolver_reacao_inimiga` → `combat.turno_inimigos`).

- A iniciativa era rolada e não valia: o herói sempre agia primeiro.
- Um turno era uma decisão só. Beber poção custava o mesmo que atacar.
- Não existia distância. Arco e espada eram a mesma coisa; conjurador apanhava em corpo a
  corpo desde o início.
- A tática do monstro era lida por palavra-chave num texto livre da ficha, o que produziu
  três defeitos (brutos atacando rodada sim, rodada não; kobold fugindo na rodada 1; chefe
  se rendendo).

O dono do produto pediu "uma real batalha de RPG" e descartou mapa tático por ora.

## Decisão

1. **Fila de turnos.** Herói, inimigos e aliados rolam iniciativa e agem nessa ordem
   (`CombatState.fila`, ids estáveis `heroi`/`i1`/`a1`). Motor em `services/turnos.py`.
2. **O turno do herói tem ação, ação bônus e movimento**, em qualquer ordem
   (`ToolExecutor._custo_de`). Bônus: consumível e comandar o aliado. Movimento: aproximar,
   recuar, levantar. O resto é ação.
3. **O turno fecha por `encerrar_turno` ou sozinho** quando a ação foi usada e não sobra
   bônus nem movimento **útil** (`_turno_acabou`). Útil é uma heurística do servidor:
   poção de cura só conta com o herói ferido; comandar só conta sem alvo marcado; mover
   depois de agir só conta para quem luta de longe ou está caído.
4. **Distância é uma etiqueta por inimigo, "perto" ou "longe" do herói.** Sem coordenadas
   e sem distância entre inimigos. Corpo a corpo só atinge perto (o ataque avança sozinho
   se o movimento está livre); ataque à distância tem desvantagem com alguém colado;
   recuar provoca ataque de oportunidade, um por inimigo por rodada.
5. **Tática, alcance, limiar de fuga e habilidade são campos da ficha** do monstro
   (`data/monsters.json`). O texto `comportamento` vira descrição.
6. **Habilidades de monstro pedem teste de resistência do herói** e impõem condições com
   duração em turnos do portador. Habilidade de ação tem recarga e uma vez de aviso.
7. **Aliado age sozinho na própria vez.** "Comandar" (bônus) marca um alvo e dá vantagem
   ao primeiro golpe.
8. **Convivência.** `CombatState.versao` distingue os motores. Luta nova nasce v2 em
   `iniciar_combate`; luta em curso de save antigo é convertida ao carregar
   (`turnos.migrar_combate`). Um estado v1 montado à mão ainda segue as regras antigas: é o
   que mantém a suíte antiga válida até a remoção do motor antigo.

## Alternativas consideradas

- **Grade de casas.** Rejeitada pelo dono do produto: o palco tem 150–200 px de altura no
  celular, exige arte de cenário e posição em todo o motor.
- **Três faixas desenhadas no palco** (retaguarda, corpo a corpo, cobertura). Mais visual;
  rejeitada por ele em favor da etiqueta por inimigo, que cabe na tela atual.
- **A ação sempre encerra o turno.** Zero cliques extras, mas impede atacar e depois
  recuar. Rejeitada por ele; a heurística do item 3 tenta ficar com o melhor dos dois.
- **O jogador controla o aliado na vez dele.** Mais controle, lutas mais longas. Rejeitada.
- **Atirador que recua quando o herói cola.** Estava no plano. Trocada por desvantagem
  fixa: previsível, e já recompensa fechar a distância.

## Consequências

- **Melhor:** os três defeitos de tática saem pela raiz. Defender e Recuar passam a ter
  motivo, porque a intenção do inimigo é um aviso do que vem.
- **Melhor:** cada clique continua resolvido sem IA, e a resposta traz os eventos em ordem
  com o id de quem agiu, o que permite à tela encenar a fila.
- **Pior, medido:** o jogo ficou mais difícil antes de qualquer ajuste. No simulador, com
  o jogador que usa técnicas, a vitória em encontro comum caiu para todas as classes
  (Guerreiro 95% → 94%, Patrulheiro 96% → 86%, Mago 70% → 58%, Clérigo 77% → 50%,
  Feiticeiro 53% → 36%). Os números de ficha são um primeiro chute; o ajuste é a Fase 8.
- **Pior:** a heurística de "útil" pode fechar o turno de quem queria bater e recuar com
  uma arma de corpo a corpo. Quem quer isso precisa recuar antes de agir, o que não serve.
  Aceito por ora; a saída, se incomodar, é a tela mandar "manter o turno aberto".
- **Dívida assumida:** dois motores convivem até a Fase 9. O antigo não roda em produção,
  mas ainda tem ~150 testes.
- **Fora desta decisão, ainda por fazer:** fechar o texto livre em combate e tirar as
  ferramentas de combate do narrador dependem do "Improvisar" (Fase 6). O contador
  `revisao` separado de `turno`, previsto no plano, não foi feito: o clique continua
  comparando e incrementando `turno`. Com várias jogadas por turno, o `turno` do mundo
  sobe mais rápido em combate do que antes.

## Como saber que erramos

- Jogadores clicam "Encerrar turno" em quase todo turno (a heurística não ajuda) ou
  reclamam de turno fechado cedo demais.
- Depois da Fase 8, o simulador não consegue pôr todas as classes na faixa de 75–97% sem
  números absurdos: a distância por etiqueta não dá a quem luta de longe vantagem que
  compense a pouca vida.
- Lutas passam de 6 rodadas em média.

## Referências

- `Backend/app/services/turnos.py`, `Backend/app/services/tools.py`
- `Backend/tests/test_combate_v2.py`, `Backend/tests/test_turno_heroi.py`
- Diários 0049 e 0050; relatório 0004; ADR-0006, ADR-0027
