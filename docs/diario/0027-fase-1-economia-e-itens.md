# Fase 1 do plano "jogo completo": economia e itens

**Período:** 08/09/2026 · continuação da mesma sessão da Fase 0

## O que aconteceu

Até aqui a mochila do herói era uma lista de nomes. Só a Poção de Cura fazia alguma coisa;
o ouro só saía e nunca entrava; não existia armadura, equipar, loja nem saque. O narrador
podia entregar qualquer item por nome, e o jogo não sabia se aquilo era uma espada ou uma
poção — o frontend adivinhava pela palavra.

Esta fase deu peso mecânico aos itens sem tirar a liberdade do narrador. A decisão de
desenho está no [ADR-0033](../adr/0033-catalogo-de-itens-com-tags-fechadas.md); aqui vai
o que mudou na prática.

## O que o jogador sente

- **O herói nasce vestido.** O equipamento inicial da classe já vem equipado: um Guerreiro
  começa com Cota de Malha, Espada Longa e Escudo e Defesa 18, não 12. A aba ITENS mostra
  o que está em cada slot, e cada item tem tipo, tags, descrição e preço de venda.
- **Equipar e guardar têm botão.** Clicar em "Guardar" no escudo tira 2 da Defesa na hora,
  sem passar pelo narrador (é o juiz resolvendo, pela rota `/game/action`). "Equipar" faz o
  caminho de volta. O servidor decide o slot pela ficha e recusa o que não cabe: armadura
  pesada sem Força, escudo com arma de duas mãos.
- **Consumíveis fazem coisas diferentes.** Poção de Cura e Maior, Poção de Foco (devolve
  Foco em combate), Antídoto (limpa veneno), Óleo de Lâmina (+2 de dano por 3 rodadas),
  Frasco de Óleo e Água Benta (dano em todos os inimigos), Bomba de Fumaça (some da vista).
  Cada um tem botão "Usar" na mochila.
- **Vencer rende ouro.** O saque é decidido pelo servidor por banda do bestiário
  (`data/loot.json`): um kobold rendeu 5 de ouro no teste ao vivo. Inimigo que fugiu não
  deixa nada. O ouro que entra tem um único outro canal: a recompensa de arco da Fase 4.
- **Mercador com balcão.** Um NPC pode ter mercadoria (só nomes do catálogo). O painel
  "Ao seu redor" mostra o balcão dele com preço já calculado: a confiança que o herói
  conquistou dá desconto (25% no máximo), vender rende metade. Comprar e vender são
  botões; o narrador tem a mesma ferramenta (`comerciar`) e nunca escreve preço.
- **O narrador ainda inventa itens** — mas com regra: fora do catálogo, `dar_item` exige
  uma descrição e até três tags de um vocabulário fechado (Fogo, Sagrado, Utilidade...).
  Um "Amuleto de Osso [Sagrado]" existe de verdade na mochila e ajuda num teste onde a tag
  se aplica; nunca cura, nunca dá Defesa, e vale 1 de ouro na venda.

## O que mudou por baixo

- `data/items.json` reescrito com números e validado no boot: JSON torto derruba o servidor
  na subida, não no meio de um combate. Armas ganharam preço (e Arco Curto e Lança, que as
  classes citavam e o catálogo não tinha).
- Nova coluna `equipamento` em `personagens` (migration 0016). Saves antigos são vestidos
  na primeira carga com o que já estava na mochila.
- `rules_engine.calcular_defesa` virou a única fonte da Defesa (sem armadura 10+DES; leve
  soma DES; média limita DES a 2; pesada ignora; escudo +2).
- A arma equipada é a preferida no ataque, atrás só do que o jogador pediu explicitamente.
- Ferramentas novas do narrador: `equipar`, `desequipar`, `comerciar` (as duas últimas só
  fora de combate; `equipar` em combate custa a ação). O turno continua dentro do teto de
  tokens da Fase 0.
- Achado ao vivo: o modelo quis fazer de uma NPC já conhecida a mercadora da cena, e o
  registro de pessoa existente ignorava tudo. Agora um recadastro pode atualizar só a
  mercadoria — relações, memória e segredo continuam intocados.

## Como testei

- 28 testes novos em `tests/test_items.py` (defesa por armadura, força mínima, escudo ×
  duas mãos, item inventado com e sem tags, cada consumível, saque determinístico,
  mercador com desconto, venda de item equipado, ferramentas por estado). Suíte inteira:
  508 verdes; ruff, mypy e typecheck do frontend limpos.
- Ao vivo contra a API: Guerreiro criado com Defesa 18 e os três slots preenchidos;
  guardar e re-equipar o escudo pelo `/game/action` (16 → 18); vitória contra um kobold
  com "💰 Saque: 5 de ouro".
- No navegador: aba ITENS com a linha "Equipado", cards com tipo/tags/preço, botão
  "Guardar" no escudo mudando a Defesa do HUD de 18 para 16 e virando "Equipar".
- Mercador via narrador: em três tentativas ao vivo, o modelo (1) narrou que a NPC não tinha
  estoque, (2) recadastrou uma NPC conhecida como mercadora (o registro ignorava — corrigido:
  recadastro pode atualizar só a mercadoria) e (3) registrou um lojista com mercadoria e local
  "Loja de Suprimentos", recusado por não ser o local atual (corrigido: sublocal é assimilado à
  vila). Na quarta tentativa a cota dos provedores acabou (429 já na primeira chamada). A
  compra e a venda pelo balcão foram confirmadas pela API sem LLM; a chamada `comerciar` pelo
  narrador fica confirmada só por teste automatizado — abrir a Fase 2 repetindo esse turno.

## O que ficou registrado para depois

- O equipamento inicial de algumas classes tem nomes fora do catálogo ("Adagas (2)",
  "Foco Arcano", "Grimório"): ficam na mochila como itens sem ficha. Normalizar
  `classes.json` é trabalho de dados, não desta fase.
- Proficiência de arma por classe continua sem efeito no ataque (adiado desde a rodada de
  conserto).

## Próximo passo

Fase 2: aliados no palco (companheiros com PV e botão de ataque). Antes, fechar o bug de
`_aliados_acionados` por request, que deixaria um aliado atacar sem limite via clique.
