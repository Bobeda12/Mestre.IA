# ADR-0042 — Identidade de classe por traço e ação bônus; Foco como recurso da jornada

**Data:** 07/10/2026
**Status:** Aceito
**Etapa:** Plano "Trilha do capítulo + Combate v2" (Fase 8)
**Supersede:** — (revisa o ADR-0026 no que toca recursos: o Foco deixa de reiniciar a cada combate)

---

## Contexto

As doze classes tinham três técnicas cada, e fora isso jogavam igual: mesma fórmula de
ataque, mesmo Foco, técnicas que acertavam sempre. O Foco voltava cheio no início de toda
luta e ainda subia a cada ataque, então nunca faltava. O descanso curto era ilimitado.

Medido no relatório 0004, o resultado era desigual: 53% a 96% de vitória em encontro comum
conforme a classe. Com o combate novo (ADR-0040) piorou para as classes de pouca vida
(Feiticeiro 36%, Bardo 41%), porque os monstros passaram a agir toda vez.

## Decisão

**1. Cada classe tem um traço sempre ligado** (`PASSIVAS`, em `services/class_abilities.py`),
escrito na ficha. Exemplos: o Bárbaro recupera Foco ao ser ferido; o Ladino soma 1d6 contra
alvo abalado e recua sem levar golpe; o Feiticeiro rola o dano das técnicas duas vezes; o
Bruxo recupera todo o Foco no descanso curto.

**2. Dez classes têm uma técnica de ação bônus** (`TECNICAS_BONUS`). É o que dá duas
decisões por turno: o Guerreiro dá dois golpes, o Clérigo cura e ainda age, o Patrulheiro
marca e ainda atira. Mago e Feiticeiro não têm; a força deles está no dano e no recuo livre.

**3. Técnica tem alcance e, se controla, pede resistência.**
- Técnicas das classes de corpo a corpo exigem chegar perto (o herói avança sozinho se o
  movimento está livre). As demais alcançam de longe.
- O dano entra sempre. Atordoar, enfraquecer, queimar e abrir a guarda só entram se o alvo
  falhar num teste contra CD 8 + proficiência + atributo da classe. Marcar não pede teste.

**4. O Foco é da jornada, não da luta.**
- Começa cheio antes da primeira luta; depois, cada luta começa com o que sobrou.
- Atacar não devolve Foco. Defender devolve 1.
- Descanso curto devolve metade (arredondada para cima), no máximo duas vezes entre
  descansos longos. O longo devolve tudo.
- Conjurador tem 2 de Foco máximo a mais.

**5. Compensações para quem tem pouca vida** (números calibrados no simulador): ataque
básico de conjurador mais forte, Defesa extra que cresce com o nível para Mago, Feiticeiro
e Bruxo, recuo livre para Mago e Feiticeiro, e cura que soma o nível.

**6. O chefe do capítulo é sorteado por degrau de nível** (`nivel_min` na ficha): Bugbear
do 1 ao 4, Dragão Jovem do 5 ao 7, os de elite a partir do 8.

## Alternativas consideradas

- **Só rebalancear as 36 técnicas.** Menos trabalho. Rejeitada pelo dono do produto: as
  classes continuariam parecidas.
- **Cinco técnicas por classe, com escolha ao subir de nível.** Mais variedade, mais difícil
  de balancear. Rejeitada por ele.
- **Técnica com rolagem de ataque** (pode errar o dano). Rejeitada: gastar um recurso que
  acaba e não causar nada é frustrante com 3 a 7 de Foco. Ficou a resistência só no efeito.
- **Dar mais vida aos conjuradores.** Resolveria direto, mas apaga a diferença entre as
  classes. Preferidas compensações que mudam o jeito de jogar (lutar de longe, recuar).
- **Subir a vida dos monstros para alongar as lutas.** Não feito; ver consequências.

## Consequências

- **Melhor, medido** (relatório 0005): com o jogador que usa o que a classe oferece, a
  vitória em encontro comum foi de 53–96% para 83–98% entre as classes.
- **Pior: quem só clica em Atacar com um conjurador perde quase metade das lutas** (Mago
  47%, Feiticeiro 46%). A diferença entre jogar bem e jogar no automático chega a 39 pontos;
  a meta era 10 a 15. A tela precisa ensinar o traço e a ação bônus, ou o jogador novo de
  Mago vai achar o jogo injusto.
- **Pior: as lutas ficaram curtas**, 3,4 rodadas em média, e 2,0 a 2,4 para Bruxo e Bárbaro.
  A ação bônus dobrou o dano de várias classes e a vida dos monstros não acompanhou.
- **Pior: a meta de 75–97% não foi cumprida em todos os níveis.** O nível 4 é um vale geral
  (Mago 66%); Clérigo e Druida caem para 66–70% nos níveis 8 e 9; Bárbaro fica em 98%.
- **Pior: chefes são muito difíceis no primeiro nível de cada degrau**, sobretudo dragões
  contra Mago e Feiticeiro (14–17% no nível 5).
- **Custo de uso:** com ação bônus disponível, o turno não fecha sozinho depois do ataque.
  Para dez classes, isso é um clique em "Encerrar turno" em quase todo turno em que o
  jogador não quer usar a bônus.
- **Compatibilidade:** personagem existente começa a próxima luta com o Foco cheio. Nenhum
  campo de save muda de formato; `WorldState.descansos_curtos` nasce em 0.

## Como saber que erramos

- Jogadores de Mago, Feiticeiro ou Ladino desistem nas primeiras lutas ou no primeiro chefe.
- Ninguém usa descanso curto, ou todos descansam antes de cada luta: o Foco finito não
  está criando decisão.
- A maioria das lutas acaba em duas rodadas: a fila, a distância e as condições não chegam
  a importar.

## Referências

- `Backend/app/services/class_abilities.py`, `Backend/tests/test_classes.py`
- Relatórios 0004 e 0005; diário 0053; ADR-0026, ADR-0040
