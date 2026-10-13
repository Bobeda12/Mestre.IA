# Texto livre confiável, Fase 3.5: inimigos com jeito de lutar

**Período:** 07/10/2026 · continuação do diário 0057 · ADR-0046

## A sua ideia, e o que o código já tinha

Você pediu que cada inimigo tivesse um jeito de combater, em arquétipos, e que a história
só colocasse o nome por cima: chegar para lutar com o Rei Ruan, o servidor pegar a ficha de
um "rei medroso" do nível certo, e o Mestre receber a personalidade dele.

O jogo já tinha metade disso: o nome de história virava uma "pele" sobre uma ficha. Mas a
ficha era **sorteada**, sem relação com quem a pessoa era. O Rei Ruan podia nascer como um
lobo. E a personalidade escrita nas fichas nunca chegava a nenhuma IA.

## O que mudou

1. **19 fichas novas de pessoas**, do nível 1 ao 8: o Saqueador Medroso, o Valentão de
   Taverna, o Guarda Corrupto, o Assassino de Aluguel, o Rei Medroso, o Mago Renegado, o
   Rei Tirano, o General Implacável e outros. Cada uma tem um papel (rei, assassino, mago…),
   um temperamento (medroso, orgulhoso, fanático…) e duas frases de personalidade.
2. **O Mestre diz quem é o inimigo, o servidor escolhe a ficha.** Ao abrir uma luta o
   narrador pode informar o papel e o temperamento ("Rei Ruan: rei, medroso"). O servidor
   traduz as palavras, olha só as fichas do nível e escolhe a que melhor combina. Se nada
   combina, o sorteio de antes.
3. **A personalidade chega às IAs do combate.** A narração da rodada ganha o jeito de cada
   inimigo, só para o tom. O juiz de improviso sabe o temperamento: assustar um medroso é
   mais fácil, e um fanático não recua.
4. **Fichas de pessoa não aparecem por acaso.** Um lobo não vira "Rei Medroso" no sorteio comum.

## Medido

- 9 testes novos (`tests/test_arquetipos.py`): todo nível de 1 a 10 tem arquétipo; o
  Rei Ruan de nível 4 vira o Rei Medroso mantendo o nome; papel pesa mais que temperamento;
  sem afinidade cai no sorteio; mesma semente, mesma escolha; a personalidade aparece nos
  prompts. Os 19 monstros também passam no teste de ficha tática que já existia.
- Backend completo: 963 passando. Frontend: 84 e tipos limpos.
- **Balanceamento** (duelos simulados, 3 classes): as fichas ficaram na faixa dos monstros
  comuns de cada banda (65% a 98%). O Saqueador Medroso, o Guarda Corrupto e o Nobre Duelista
  vencem em quase 100% no nível exato deles; deixei assim por ser a faixa de entrada.

## Ainda não resolvido

- **Sem arte própria.** Cada ficha empresta o sprite de uma criatura (o Rei Medroso usa o
  do Cavaleiro Negro, o Mago Renegado o do Lich Menor). Para arte nova basta criar o
  arquivo e trocar o campo `sprite` na ficha.
- **Os chefes de arco** ainda usam a ficha reservada, sem papel nem temperamento.
- **Rendição e súplica por temperamento** continuam por conta da narração; o motor só
  entende a fuga a partir de uma fração de vida.
- **Teste ao vivo:** falta ver se o Gemini passa `perfis` por conta própria. Se não passar,
  a luta cai no sorteio de antes, sem erro.

## Um tropeço no caminho

O mesmo problema de barra invertida da Fase 1 voltou: uma quebra de linha de verdade foi
parar dentro de uma string de `combate_ia.py` e quebrou o arquivo. Achei ao reler o trecho
e consertei com a ferramenta de edição direta, que não passa por esse escape.
