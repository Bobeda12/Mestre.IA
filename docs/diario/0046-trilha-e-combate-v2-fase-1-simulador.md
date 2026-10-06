# Trilha e Combate v2, Fase 1: um simulador para medir antes de mexer

**Período:** 06/10/2026 · continuação do diário 0045

## O problema

As próximas fases mudam as regras do combate de uma vez. Sem um jeito de medir, cada
ajuste de número seria um palpite. O código já citava um `evals/simulador.py` em sete
comentários ("ajustar depois com o simulador"), mas o arquivo nunca existiu: as medições
anteriores foram feitas com um laço escrito à mão e descrito num diário.

## O que foi feito

`Backend/evals/simulador.py` simula lutas inteiras sem IA e sem banco de dados.

- **Usa o juiz de verdade.** Cada jogada passa por `ToolExecutor.executar`, a mesma função
  que roda quando o jogador clica num botão. Se uma regra mudar no jogo, muda na
  simulação junto.
- **É reprodutível.** Os dados vêm de um gerador com "semente" (um número inicial que
  faz o gerador produzir sempre a mesma sequência). Mesma semente, mesmas lutas.
- **Tem dois jogadores simulados.** O "básico" só ataca e bebe poção com pouca vida. O
  "tático" também usa as técnicas da classe. A distância entre os dois mostra quanto vale
  aprender o sistema.
- **O herói nasce como no jogo.** Ele veste o equipamento inicial da classe pela mesma
  função da criação de personagem.

Uso:

```bash
uv run python -m evals.simulador --n 200 --classes todas --bot tatico
```

## Um erro meu pelo caminho

Na primeira versão eu tinha escrito uma tabela com a Defesa "típica" de cada classe
(Bárbaro 16, Clérigo 16, Mago 12). Era suposição. Ao trocar pela função real, o Bárbaro
caiu de 16 para 11 e o Mago para 11: várias classes começam sem armadura nenhuma. Os
números do relatório são os medidos com o equipamento real.

Também apareceu que Clérigo e Paladino começam com uma armadura que exige Força 13 e 15.
Quem não põe pontos em Força fica com ela na mochila. O herói de referência recebe essa
Força; o jogo deveria avisar isso na criação (anotado para a Fase 8).

## O que a medição mostrou

Está no relatório `docs/relatorios/0004-referencia-antes-do-combate-v2.md`. Resumo:

- As classes estão muito desiguais: de 53% a 96% de vitória em encontro comum.
- O relatório 0002 dizia 53–57% contra o chefe de elite. Esse número contava com o chefe
  desistindo aos 30% de vida, defeito consertado na Fase 0. O número real, para quem só
  ataca, é 30–39%.
- O Dragão Jovem pode ser sorteado como chefe de um herói de nível 1, que vence 1% das
  vezes.

Nenhum número de monstro ou técnica foi alterado nesta fase. O ajuste é na Fase 8, depois
que as regras novas existirem; ajustar agora seria ajustar duas vezes.

## Como foi verificado

- 29 testes em `Backend/tests/test_simulador.py`: mesma semente dá o mesmo resultado;
  todas as 12 classes lutam com os dois jogadores sem o juiz recusar nenhuma jogada; o
  chefe entra com a própria ficha.
- A explicação dos chefes foi conferida, não deduzida: religando a rendição só dentro do
  simulador, a vitória volta de 30–37% para 52–62%.
