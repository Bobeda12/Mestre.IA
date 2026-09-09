# ADR-0036 — Uma tela, um palco, um dock

**Data:** 08–09/09/2026
**Status:** Aceito
**Etapa:** Plano "jogo completo" (Fase 6 — "uma tela só"; ver diário 0032)

---

## Contexto

As Fases 0–5 do plano "jogo completo" entregaram camadas de jogo reais (Mundo Vivo,
economia, aliados, level-up, arcos, bestiário), cada uma pousando o seu próprio pedaço de
tela sem que ninguém parasse para olhar o conjunto. O resultado, visto pelo jogador:

- **Três regiões que rolavam separadamente**: o palco de combate/exploração e o console de
  comandos dentro dele (`AdventureStage.tsx`), o painel "Mundo Vivo" logo abaixo
  (`LivingWorld.tsx`, dentro de um container de altura fixa em `min(48vh,560px)`), e o log
  de narrativa por baixo dos dois, cada um com a sua própria barra de rolagem.
- **Três sistemas de abas independentes**: a ficha lateral (STATUS/ITENS/MISSÃO/
  RELAÇÕES/BESTIÁRIO), "Comandos/Jornada" dentro do palco, e `<details>` no Mundo Vivo.
- **A mesma intenção, três lugares diferentes**: "falar com Olma" podia sair do console do
  palco (se ela fosse alvo de combate — não era), do painel Mundo Vivo (clicar nela,
  escolher "Conversar" num `<select>`), ou digitando no chat.
- **Duas paletas hardcoded**: `.adventure-*` em verde-marrom, `.living-world` em azul,
  nenhuma das duas usando os tokens Tailwind `rpg-*` do resto do app.
- **Três fontes**: Geist (sans moderna, corpo do app) na narrativa, VT323 (pixel largo) no
  HUD e nos rótulos, Press Start 2P só em títulos — sem critério visível de quando cada
  uma entrava.

Nada disso quebrava o jogo (a suíte de testes e o uso ao vivo confirmavam cada fase
isoladamente); era a composição das fases que lia como colagem.

## Decisão

1. **Uma coluna, sem rolagem de página**: `h-dvh` na raiz da tela; a coluna central vira
   uma grade de quatro linhas — HUD (44px), palco (altura fixa, `clamp(240px,34vh,360px)`),
   narrativa (`flex-1`, único container que rola) e dock de ações. `h-dvh` em vez de
   `h-screen` porque no mobile a barra de endereço/teclado muda a altura visível de
   verdade sem redimensionar um `vh` fixo.
2. **O Mundo Vivo vira parte do palco**: pessoas (`mundo.pessoas`) são atores clicáveis
   como o herói e os inimigos, com sprite por raça; objetos e saídas (`mundo.entidades`)
   viram uma prateleira na base do palco. Uma **seleção única** (`{tipo, id}`, guardada em
   `GameChat`) substitui os dois estados de seleção que existiam (alvo de combate no
   console, entidade selecionada no Mundo Vivo). O painel separado deixa de existir; arco,
   conflitos, objetivo e fatos migram para a aba JORNADA da ficha (consulta, não ação); o
   balcão do mercador vira modal.
3. **Uma barra de ação só, colada ao campo de texto**: o dock lê a seleção e o estado de
   combate e decide os botões — em combate, Atacar/Defender/Técnicas/Táticas/Cena/Itens
   (popovers, um por vez); com alguém ou algo selecionado, os verbos daquele alvo; sem
   seleção, as sugestões do narrador (`[OPCOES]`) mais Descansar. O texto livre continua
   sempre disponível — os botões são atalho, não substituição.
4. **Verbos sociais usam o próprio campo de texto como proposta**: negociar, ajudar,
   intimidar, distrair e acalmar hoje exigiam um `<input>` de "proposta" dentro do painel
   Mundo Vivo. Clicar o verbo entra em "modo proposta" (placeholder muda, um chip mostra o
   verbo ativo); Enter ou o botão de enviar chama `agir_no_mundo` com o texto digitado como
   `proposta`, sem abrir um formulário à parte.
5. **Tipografia com papel definido**: Press Start 2P só para títulos e rótulos curtos sem
   acento (a fonte não tem glifos acentuados); Alegreya (serifa de livro, auto-hospedada
   via `@fontsource`) para narrativa e todo texto corrido — no lugar de Geist e VT323.
   `font-rpg` (o token usado em ~190 lugares) passa a resolver para Alegreya, então a
   mudança não pede editar cada call site; só os rótulos que carregavam conteúdo dinâmico
   com acento (classe do herói, intenção do inimigo, nome de NPC, nome de técnica/item)
   precisaram trocar explicitamente de `font-pixel-title` para `font-rpg`.
6. **Mobile é parte da entrega, não um "depois"**: alvos de toque ≥44px (prateleira,
   verbos, chips), a barra de verbos e a prateleira rolam na horizontal com
   `scroll-snap`, popovers viram folha inferior (`position:fixed; bottom:0`) abaixo da
   gaveta da ficha, `overscroll-contain` na raiz.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Visual novel de tela cheia (palco de fundo, caixa de diálogo por cima) | Mais imersivo, referência clara (Disco Elysium, Fire Emblem) | Esconde texto longo atrás de uma caixa pequena; ficha/inventário viram gavetas por ícone, mais um nível de indireção | O jogo já depende de ler parágrafos inteiros do mestre; a caixa de diálogo compete por espaço com o próprio motivo de existir |
| Duas colunas: palco+comandos à esquerda, narrativa como pergaminho rolável à direita (estilo Baldur's Gate) | Palco e comandos sempre visíveis, sem competir com a leitura | Precisa de tela larga; no celular vira abas de novo — o problema volta pela porta dos fundos | O público-alvo joga em janela estreita com frequência (ver Etapa 7); duas colunas fixas não sobrevive a 375px sem reintroduzir abas |
| Menu radial ao clicar no ator (verbos aparecem grudados nele) | Mais "jogo", descoberta no próprio palco | Sem barra de ação persistente, quem não clica no ator não descobre os verbos; pior para acessibilidade e teclado | O dock persistente é mais previsível e mais fácil de testar (aria-label estável, foco de teclado) |
| Manter VT323 na narrativa (só trocar o resto) | Menor churn, uma fonte a menos para revisar | VT323 é uma fonte de terminal/8-bit; em parágrafos longos ela é a fonte mais difícil de ler das três que existiam | A narrativa é o produto — vale a única troca de fonte que exige revisar tamanhos em toda a tela |

## Consequências

**Ganhamos:** uma intenção, um lugar para executá-la; menos estados duplicados (uma
seleção, não duas); paleta e tipografia com regra (`font-pixel-title` só sem acento,
`font-rpg`/Alegreya para tudo que se lê); mobile testado como parte da entrega, não como
dívida.

**Pagamos:** o palco tem menos altura de tela em monitores baixos (a narrativa nunca
encolhe o palco, e vice-versa — nenhum dos dois é redimensionável); `GameChat.tsx`
continua grande porque continua sendo o único dono do estado — a Fase 6 mudou a
*apresentação*, não a arquitetura de estado; `cena.interacoes` (interações táticas de
combate) e `mundo.entidades` (objetos do lugar) são conjuntos diferentes que o palco e o
dock tratam separadamente — juntar os dois numa lista só teria sido mais simples de
programar e mais confuso de jogar.

**Fica em aberto:** o e2e (`e2e/jogar-um-turno.spec.ts`) está quebrado desde antes desta
fase por um motivo não relacionado (o fluxo de login mudou; login de convidado agora é uma
etapa própria antes da criação de personagem) — sinalizado à parte, não corrigido aqui;
`opcoes_padrao` (Backend) ainda sugere "Verificar o inventário" mesmo com a ficha sempre
visível, o que pode não fazer mais sentido.

## Como saber que erramos

- Se o palco de altura fixa cortar informação importante em telas de notebook baixas
  (13"), a decisão de "sem recolher" precisa ser revisitada.
- Se jogadores continuarem digitando "conversar com Olma" em texto livre em vez de usar o
  dock depois de selecioná-la, os verbos do dock não estão descobríveis o suficiente.
- Se surgirem novos rótulos com acento em `font-pixel-title`, a regra "estático e curto =
  pixel-title, dinâmico ou frase = font-rpg" precisa de reforço (lint automático, talvez).

## Referências

- ADR-0032 — mundo emergente puro (o Mundo Vivo que esta fase reorganiza)
- ADR-0033 — catálogo de itens (o balcão do mercador que virou modal)
- ADR-0035 — arcos verificáveis pelo servidor (o painel de capítulo que virou aba JORNADA)
- Plano "jogo completo", Fase 6; diário 0032
