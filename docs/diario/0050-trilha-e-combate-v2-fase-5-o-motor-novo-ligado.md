# Trilha e Combate v2, Fase 5: o motor novo ligado ao jogo

**Período:** 06/10/2026 · continuação do diário 0049 · decisão no ADR-0040

## O que mudou para quem joga

A partir desta fase, toda luta usa o motor de turnos da Fase 4. **A tela ainda é a
antiga**: ela não mostra a fila, a distância nem os botões novos. Isso é a Fase 7. Até lá,
o combate no navegador fica incompleto; os testes e o simulador são o que comprova as
regras.

### Um turno agora tem três partes

- **Ação:** atacar, investir, defender, esquivar, esconder-se, fugir, usar técnica, mexer
  no cenário.
- **Ação bônus:** beber poção (ou outro consumível) e comandar o aliado.
- **Movimento:** aproximar-se de um inimigo, recuar, levantar do chão.

Podem ser usadas em qualquer ordem, uma de cada por turno. O servidor recusa a segunda
("Você já usou sua ação neste turno.").

### Quando o turno acaba

Por um clique em "encerrar turno", ou sozinho quando a ação já foi usada e não sobra nada
que valha a pena. "Valer a pena" é decidido pelo servidor:

- a poção de cura só segura o turno se o herói está ferido;
- comandar o aliado só segura o turno se não há alvo marcado;
- depois de agir, o movimento só segura o turno para quem luta de longe (pode abrir
  distância) ou para quem está caído (pode levantar).

Na prática: um guerreiro que ataca fecha o turno no mesmo clique, como antes. Uma arqueira
com inimigo colado fica com o turno aberto para recuar.

### Distância

- Atacar com espada um inimigo que está longe faz o herói avançar sozinho, gastando o
  movimento. Se o movimento já foi, o servidor avisa que o alvo está longe.
- Atirar com alguém colado dá desvantagem.
- Recuar leva um golpe de cada inimigo perto.

### Condições no herói

| Condição | Efeito |
|---|---|
| Envenenado | 2 de dano por turno; ataca com desvantagem |
| Caído | não se desloca até levantar (gasta o movimento); ataca com desvantagem; inimigos perto atacam com vantagem |
| Amedrontado | não avança; ataca com desvantagem |
| Contido | não se desloca; inimigos perto atacam com vantagem |
| Enfraquecido | 3 a menos de dano |
| Em chamas | 2 de dano por turno |
| Atordoado | perde a vez |

O Antídoto, que não curava nada porque nada envenenava, voltou a ter uso.

### O começo da luta

Antes, um inimigo mais rápido dava um "ataque de surpresa" e depois o herói agia primeiro
para sempre. Agora ele simplesmente age antes, na ordem da fila, em todas as rodadas.

## Como ficou por dentro

`ToolExecutor.executar` (a função que resolve cada clique) ganhou três passos quando a
luta é do motor novo:

1. descobre o que a jogada gasta (`_custo_de`) e recusa se já foi gasto;
2. roda a jogada como antes;
3. marca o gasto e, se o turno acabou, chama `_passar_a_vez`: fecha o turno do herói, anda
   a fila até ele de novo e abre o turno seguinte.

A antiga "reação dos inimigos colada na ação" (`_resolver_reacao_inimiga`) virou um
não-faz-nada nas lutas novas.

Lutas em andamento em partidas salvas são convertidas ao carregar.

## O que ficou diferente do plano

- **Texto livre em combate continua aberto.** O plano fechava o chat durante a luta nesta
  fase. Sem o "Improvisar" (Fase 6), fechar agora tiraria do jogador a ação criativa sem
  dar nada no lugar. Fica para depois da Fase 6.
- **O contador `revisao` não foi feito.** Era para separar "quantas vezes o save mudou" de
  "quanto tempo de jogo passou". O clique continua usando `turno` para os dois. Efeito
  colateral: com várias jogadas por turno, o `turno` do mundo sobe mais rápido em combate.
- **O motor antigo ainda existe.** Só roda em estados montados à mão pelos testes antigos.
  Sai na Fase 9.
- **O Foco ainda volta cheio a cada luta.** Faz parte das classes (Fase 8).

## O que o simulador diz do motor novo

Mesma medição do relatório 0004, agora no motor novo, sem nenhum ajuste de número.
Vitória em encontro comum, jogador que usa técnicas:

| Classe | Antes | Agora |
|---|---|---|
| Guerreiro | 95% | 94% |
| Paladino | 94% | 92% |
| Bárbaro | 88% | 90% |
| Patrulheiro | 96% | 86% |
| Monge | 88% | 85% |
| Ladino | 72% | 79% |
| Mago | 70% | 58% |
| Bruxo | 79% | 57% |
| Druida | 76% | 52% |
| Clérigo | 77% | 50% |
| Bardo | 62% | 41% |
| Feiticeiro | 53% | 36% |

Contra chefes ficou bem mais duro: o Guerreiro tático vence o Dragão Jovem em 11% das
vezes no nível 5 (antes 53%), porque o dragão agora sopra fogo e não desiste.

Era esperado: os brutos passaram a atacar toda vez, a iniciativa vale, e os monstros
ganharam habilidades. Quem luta de armadura pesada quase não sentiu; quem tem pouca vida
sentiu muito, e a distância sozinha não compensou. Corrigir isso é o trabalho da Fase 8.
Os números não foram mexidos agora de propósito: as classes ainda vão mudar.

## Como foi verificado

- 24 testes novos em `Backend/tests/test_turno_heroi.py`, pelo caminho real do clique:
  alcance e avanço automático, desvantagens, cada condição, ação/bônus/movimento uma vez
  por turno, as três regras de "turno fica aberto", fila andando, herói atordoado, inimigo
  que foge encerrando a luta, e dois testes pela API (recuar, tentar mover de novo,
  encerrar turno, conferir o que foi gravado).
- Testes antigos: 3 apagados (ataque de surpresa e ordem antiga, cobertos pelos novos), 6
  atualizados. Suíte: 870 passando. `ruff` e `mypy` limpos.
- Simulador: as 12 classes lutam com os dois jogadores sem jogada recusada.

**Não verificado:** combate no navegador. A tela ainda não tem os botões de mover nem de
encerrar turno, então uma luta com o turno aberto fica sem saída por ela. Isso se resolve
na Fase 7; não testei no navegador porque o resultado seria só confirmar essa falta.

Um teste falhou uma vez por um motivo de fora desta mudança: dois personagens de teste
sortearam o mesmo código de sessão (o código é o nome mais quatro dígitos aleatórios).
Passou ao repetir. Vale um conserto próprio.
