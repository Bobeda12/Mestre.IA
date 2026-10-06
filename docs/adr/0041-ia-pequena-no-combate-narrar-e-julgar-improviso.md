# ADR-0041 — No combate, a IA só narra o que já foi resolvido e julga improvisos numa lista fechada

**Data:** 06/10/2026
**Status:** Aceito
**Etapa:** Plano "Trilha do capítulo + Combate v2" (Fase 6)
**Supersede:** — (revisa o ADR-0007 para o combate: aqui não há tool calling; e o ADR-0012: a prosa da rodada não vem por streaming)

---

## Contexto

Com o combate por fila de turnos (ADR-0040), cada clique é resolvido pelo servidor sem IA.
Sobravam dois papéis para ela:

- **Dar voz à luta.** O clique devolvia só as linhas do juiz ("d20(15)+5=20 vs CA 13").
- **Ação criativa.** "Derrubo o lustre em cima dele" só existia pelo chat, que em combate
  manda ao modelo o prompt inteiro e 15 ferramentas. Medido antes deste plano: 7,4 a 7,8
  mil tokens na primeira chamada, colado no teto de 8 mil por minuto do provedor gratuito,
  e 2,7 chamadas por turno em média.

O dono do produto quer narração em toda rodada e quer manter a ação criativa.

## Decisão

Duas chamadas pequenas, sem ferramentas, em `services/combate_ia.py`.

**1. Narrar a rodada** (`POST /game/narrar_rodada`).

- A tela pede a prosa depois que o turno do herói fechou. Os cards do juiz já estão
  visíveis; a prosa chega depois e não bloqueia nada.
- O pedido leva só **fatos sem número**, montados pelo servidor a partir dos eventos de
  cada jogada e gravados no histórico (`fatos_da_jogada`): "Você ataca Orc com Espada Longa
  e acerta." O cliente manda apenas o índice da mensagem; nunca os fatos.
- A resposta é validada sem IA: de 20 a 600 caracteres e **nenhum dígito**. Reprovou,
  descarta. Não há chamada de correção.
- A prosa é gravada na mensagem do histórico; pedir de novo devolve a gravada.

**2. Julgar o improviso** (ação `improvisar` em `POST /game/action`).

- O jogador escreve até 200 caracteres. A IA devolve
  `{atributo, dificuldade, efeito, alvo}`, cada campo de uma lista fechada, validada por
  Pydantic. Dez efeitos, descritos sem número no pedido.
- O servidor converte a dificuldade em CD (10, 13 ou 16), rola `d20 + atributo +
  proficiência` e aplica o efeito com os próprios números. Gasta a ação do turno.
- Travas do servidor, valham o que a IA julgar: chefe não é derrubado nem intimidado; os
  dois efeitos mais fortes (derrubar, dano em área) nunca saem por dificuldade "fácil";
  dano em área vale uma vez por luta; repetir o mesmo efeito em seguida custa +3 na CD.

**Nenhuma das duas trava a luta.** Sem provedor, com erro, com resposta inválida ou acima
do teto, a narração devolve `prosa: null` com um aviso e o improviso é julgado pelo
servidor (atributo por palavras do texto, dificuldade média, efeito "abrir a guarda").

**Cota própria.** As duas contam em `chamada_combate`, teto de 60 por dia por conta
(`teto_chamadas_combate`), separado do teto de turnos. Quem traz a própria chave não conta.

## Alternativas consideradas

- **IA narra só nos momentos-chave** (abertura, crítico, queda, fim). Era a recomendação;
  o dono do produto preferiu toda rodada.
- **Narração por streaming, como o turno de exploração.** Rejeitada: são duas ou três
  frases, e a rota em JSON é mais simples de gravar, repetir e testar.
- **O cliente manda os eventos para narrar.** Rejeitada: a IA narraria qualquer coisa que
  o cliente inventasse, e a prosa ficaria gravada no histórico.
- **Corrigir a prosa reprovada com uma segunda chamada.** Rejeitada: dobra o custo do pior
  caso; o texto do juiz já é um resultado aceitável.
- **Improviso com efeito e número livres, limitados por teto** (como `aplicar_dano`, até
  4d12+10). É o que existia. Rejeitada: a IA decidia o tamanho do efeito.

## Consequências

- **Melhor, medido ao vivo** (Gemini 3.5 Flash Lite, três execuções de 7 chamadas): narração com cerca de
  200 a 220 tokens de entrada e 55 a 85 de saída; improviso com cerca de 480 de entrada e
  30 a 45 de saída. Contra os 7,4 mil do caminho antigo.
- **Melhor:** a IA não tem como alterar número nem resultado em combate.
- **Pior:** a prosa pode enfeitar além dos fatos. Visto ao vivo: um escudo que o herói não
  tinha, um veneno "paralisante", um herói tratado no feminino. O pedido foi apertado
  depois disso (proíbe equipamento e efeito fora da lista, pede "você" e nenhum adjetivo
  com gênero), mas a única garantia automática é a ausência de números.
- **Pior:** uma luta de 6 rodadas gasta 6 das 60 chamadas do dia, mais uma por improviso.
- **Pior:** o julgamento sem IA é pobre: quase sempre Força e "abrir a guarda".
- **Ainda por fazer:** o chat continua aceitando texto livre em combate. Fecha quando a
  tela tiver o botão Improvisar (Fase 7), junto com a retirada das ferramentas de combate
  do narrador.

## Como saber que erramos

- Jogadores relatam prosa contando algo que não aconteceu (um golpe, uma morte).
- A fração de narrações devolvidas como `null` em produção passa de uma em cada cinco.
- O improviso vira a jogada dominante: no simulador ou no uso, rende mais que atacar.

## Referências

- `Backend/app/services/combate_ia.py`, `Backend/tests/test_combate_ia.py`
- Diário 0051; ADR-0006, ADR-0038, ADR-0040
