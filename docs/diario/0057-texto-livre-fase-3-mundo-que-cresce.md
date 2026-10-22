# Texto livre confiável, Fase 3: o mundo que cresce

**Período:** 07/10/2026 · continuação do diário 0056 · ADR-0045

## O problema, em termos simples

O mundo tinha 7 lugares, e todos serviam para qualquer momento do jogo. Ir para uma masmorra
no nível 1 ou no nível 9 dava o mesmo tipo de inimigo, porque o perigo só olhava para o
herói, nunca para o lugar. Nada "se abria" com o que você fazia, e a lista de lugares não
aparecia na tela.

## Uma escolha que segue o que você pediu

O plano original falava em "trancar" regiões até o herói ter nível. Como você pediu
liberdade com consequência, fiz o contrário: **você pode ir a qualquer lugar**, mas o perigo
é do lugar. Se um herói de nível 1 for ao Vulcão de Cinzas (nível 8), o jogo avisa
("⚠️ Lugar perigoso") e os inimigos que aparecem lá são os do Vulcão. A consequência de ir
longe demais é real, mas ninguém diz "não pode".

## O que mudou

1. **Cada lugar tem um nível de perigo**, e o combate usa o maior entre o seu nível e o do
   lugar. Lugar seguro (como a vila) não fica trivial para um herói forte.
2. **O mundo passou de 7 para 14 lugares**, indo até o nível 9. Eu escrevi os 7 novos como
   ponto de partida: Cidade de Altaluz, Minas de Cristal Sombrio, Ruínas de Karth, Torre do
   Mago Louco, Montanhas Geladas de Vael, Vulcão de Cinzas e Cidadela Esquecida. Pode
   reescrever o que quiser em `Backend/data/locations.json`.
3. **Fechar um capítulo abre o mapa.** Cada capítulo concluído revela até 2 lugares novos,
   do mais fácil para o mais difícil, até 3 níveis acima do seu. Você sente o mundo crescer
   conforme a história avança.
4. **A aba Jornada mostra os lugares conhecidos**, com o nível de perigo e onde você está.
5. **O narrador sabe dos lugares conhecidos** e pode oferecê-los na conversa.

## O que foi medido

- 6 testes novos (`tests/test_mundo_cresce.py`): catálogo com nível em todos os lugares;
  perigo nunca abaixo do herói e com teto; viajar a lugar perigoso é livre e avisa; combate
  usa a faixa do lugar; o mapa é revelado em ordem de dificuldade e respeita o limite de
  3 níveis; o painel lista os lugares.
- Backend: 935 passando. Frontend: 84 testes passando e tipos limpos.
- Tamanho do prompt: 15479 caracteres (teto 16000).

## O que ainda não foi provado

- **Não vi a tela.** A seção "Lugares conhecidos" passou nos tipos e nos testes existentes,
  mas não abri o jogo no navegador para olhar. Isso fica para o teste ao vivo.
- Fechar um capítulo ao vivo e ver os lugares aparecerem depende de um arco completo.

## Um alerta para a Fase 4

Lutar em lugar acima do seu nível rende XP maior, e a curva de XP já estava quebrada (um
encontro sobe de nível a partir do 4, relatório 0006). A Fase 4 refaz essa curva e precisa
contar com isso.
