# Trilha e Combate v2, Fase 8: classes diferentes e Foco que acaba

**Período:** 06 e 07/10/2026 · continuação do diário 0052 · decisão no ADR-0042 · números no relatório 0005

## O problema

Depois da Fase 5 o combate tinha regras de verdade, mas duas coisas estavam erradas:

- **As classes jogavam igual.** Três técnicas cada, e fora isso a mesma coisa.
- **O jogo estava injusto com quem tem pouca vida.** No simulador, o Feiticeiro vencia 36%
  dos encontros comuns e o Guerreiro 94%.

Além disso o Foco (o recurso das técnicas) voltava cheio a cada luta e ainda subia a cada
ataque. Nunca faltava, então nunca era uma decisão.

## O que mudou

### Cada classe tem um traço

Um efeito sempre ligado, escrito na aba Poderes da ficha:

| Classe | Traço |
|---|---|
| Bárbaro | Recupera 1 de Foco ao ser ferido |
| Guerreiro | Golpe tático é ação bônus: dois golpes por turno |
| Ladino | +1d6 de dano com vantagem ou contra alvo abalado; recua sem levar golpe |
| Monge | Recua sem levar golpe; rajada de punhos é ação bônus |
| Patrulheiro | Vantagem ao atirar de longe num alvo marcado |
| Paladino | +2 em testes de resistência |
| Bardo | Palavra cortante é ação bônus |
| Clérigo | Santuário é ação bônus: cura e ainda age |
| Druida | Forma de urso é ação bônus |
| Feiticeiro | Dano das técnicas rolado duas vezes, vale o maior; recua sem levar golpe |
| Bruxo | O descanso curto devolve todo o Foco |
| Mago | Defesa extra que cresce com o nível; técnicas mais difíceis de resistir; recua sem levar golpe |

### Técnicas

- **Ação bônus:** dez classes têm uma técnica que gasta a ação bônus em vez da ação. Na
  lista de técnicas ela aparece marcada "Bônus".
- **Alcance:** técnica de classe de corpo a corpo exige chegar perto. O herói avança
  sozinho se ainda tem o movimento.
- **Resistência:** o dano entra sempre. Atordoar, enfraquecer, queimar e abrir a guarda só
  entram se o alvo falhar num teste. Aparece um card: "Orc resiste a Palma atordoante?".

### Foco

- Começa cheio. Depois, cada luta começa com o que sobrou da anterior.
- Atacar não devolve Foco. Defender devolve 1.
- Descanso curto devolve metade, e só dá para fazer dois entre um descanso longo e outro.
  Antes era ilimitado.
- Descanso longo devolve tudo.

### Chefes

O capítulo sorteava o chefe entre Bugbear e Dragão Jovem até o nível 5. Um herói de nível 1
podia pegar o dragão e vencia 1% das vezes. Agora é por degrau: Bugbear do 1 ao 4, Dragão
Jovem do 5 ao 7, os de elite a partir do 8. Três chefes ficaram mais fracos.

### Pequenos consertos que entraram junto

- **Aprendizados voltaram a ter botão**, na aba Poderes. Tinham ficado sem tela quando o
  painel antigo da Jornada saiu.
- **Código de sessão.** Cada personagem recebia "nome + quatro dígitos". Dois personagens
  com o mesmo nome podiam sortear os mesmos dígitos, e a criação falhava. Um teste caiu
  nisso duas vezes nesta semana. O sufixo agora é bem maior.

## Como os números foram acertados

Sem simulador, isto seria palpite. O ciclo foi: mudar uma coisa, rodar 100 a 150 lutas por
combinação, olhar a tabela.

1. **Primeira medição com os traços:** marciais em 85–99%, conjuradores despencando nos
   níveis altos (Mago 13% no nível 9).
2. **Conjuradores ganharam** 2 de Foco, ataque básico mais forte e Defesa que cresce com o
   nível. Subiram, mas Mago e Feiticeiro seguiam perto de 50%.
3. **Descobri que duas quedas eram do simulador, não do jogo.** Ele gastava a cura com a
   vida cheia e nunca usava magia de área contra um inimigo só. Corrigido, Mago e
   Feiticeiro subiram uns 10 pontos sem mexer em regra.
4. **Mago e Feiticeiro passaram a recuar sem levar golpe**, e a cura passou a somar o
   nível. Aí todos entraram, na média, na faixa de 83–98%.
5. **Chefes:** três ajustes de ficha.

## O que não ficou bom

Está tudo no relatório 0005. O que mais importa:

- **Quem joga de Mago só clicando em Atacar vence 47%.** Usando o que a classe tem, 83%. A
  tela precisa ensinar isso.
- **As lutas estão curtas:** 3,4 rodadas em média, 2 para o Bruxo.
- **O nível 4 é um vale** para quase todo mundo (Mago 66%).
- **Chefe no primeiro nível do degrau é muito duro**, principalmente dragão contra Mago e
  Feiticeiro (14–17% no nível 5).
- **Bárbaro está forte demais** (98%).
- **"Encerrar turno" ficou mais frequente.** Com ação bônus disponível, o turno não fecha
  sozinho depois do ataque.

Parei de ajustar aqui de propósito. Cada rodada de ajuste custa uns minutos de simulação e
os problemas que sobraram pedem decisão de desenho (alongar as lutas? facilitar o chefe?),
não mais um número.

## Como foi verificado

- 45 testes em `Backend/tests/test_classes.py`: o catálogo das doze classes, ação bônus,
  alcance, resistência, cada traço com dado fixo, o Foco entre lutas e nos dois descansos,
  os degraus dos chefes.
- 15 testes antigos atualizados para as regras novas (desvantagem ao avançar, sopro mais
  fraco, turno que fica aberto com técnica bônus disponível).
- Suíte: 946 no backend, 84 no frontend. `ruff`, `mypy` e tipos do frontend limpos.
- Simulador: relatório 0005.

**Não verificado:** o traço de classe e a marca "Bônus" na tela, no navegador. Foram
conferidos por tipos e testes, não vistos.
