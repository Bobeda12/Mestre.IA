# ADR-0021 — Sistema de componentes pixel (PanelFrame, PixelButton, PixelIcon)

**Data:** 24/08/2026
**Status:** Aceito
**Etapa:** 14 (nova — fora da numeração 10-13 do backlog)
**Supersede:** —
**Estende:** ADR-0017

---

## Contexto

O ADR-0017 (Etapa 11, B-1) trocou os retratos de raça/classe/monstro por
sprites reais e criou uma base mínima de identidade visual: tokens de fonte,
`PixelBar` e a classe `.pixel-frame` (moldura via `box-shadow`, cantos
retos, sem 9-slice de verdade). Essa base só foi aplicada em alguns pontos
— o resto da interface (Home, Criação de Personagem, corpo do chat, barra
de vida do inimigo em combate, inventário) continuava com o visual
anterior: cantos arredondados, gradientes, sombras suaves, ícones
`lucide-react` de traço fino, e a Home usava um fundo gerado por IA
(pollinations.ai).

O autor pediu para refazer a parte visual inteira do jogo com o mesmo
padrão 8-bit, incluindo um sistema de componentes completo (não só ajustar
tokens) e ícones pixelizados em toda parte, inclusive interface pura
(fechar, menu, som) — não só ícones de jogo (vida, ouro, itens).

## Decisão

**Três componentes novos** (`Frontend/src/components/`):

- **`PixelIcon`** — wrapper de `<img>` com um mapa `nome → arquivo`,
  substituindo ícones `lucide-react` um por um onde existe sprite
  equivalente.
- **`PanelFrame`** — moldura 9-slice de verdade via CSS `border-image`
  (`border-image-slice` com `fill`, `border-image-repeat: round`), no
  lugar do truque de `box-shadow` do `.pixel-frame`. Usado em caixas
  grandes onde cantos desenhados se notam (card de personagem, sidebar,
  modais, slots de inventário). `.pixel-frame` continua existindo para
  bordas retas simples.
- **`PixelButton`** — botão com moldura 9-slice em 3 variantes de cor
  (vermelho/azul/dourado), substituindo botões `rounded-lg
  bg-gradient-to-r`. Sem sprite de "pressionado" separado — o clique usa
  `transform` + `brightness`, recurso que o app já usava antes.

**Fontes dos assets, mesma regra do B-1 (sem geração por IA):**

| Pacote | Licença | Usado para |
|---|---|---|
| Tiny Dungeon (Kenney) — já em uso desde o B-1 | CC0 | espada, adaga, machado, maça, escudo, 4 poções, baú |
| Roguelike/RPG Pack (Kenney) | CC0 | pergaminho, mochila, moeda |
| UI Pack - Pixel Adventure (Kenney) | CC0 | textura de `PanelFrame` e das 3 variantes de `PixelButton` |

**Seis ícones não existem em nenhum pacote pesquisado** (estrela/nível,
fechar, menu, seta, som ligado, som mudo) **e foram desenhados à mão** —
script Python (Pillow): forma desenhada numa grade supersample, contorno
preto de 1px por dilatação de 4-vizinhos, preenchimento chapado — mesmo
tratamento visual dos sprites dos pacotes, sem depender de um quarto/quinto
pacote incompatível em estilo só por causa de meia dúzia de glyphs.

**Aplicado em 6 itens** (C-1 a C-6): fundação (ícones/painéis/botões) →
fundo pixel art da Home (composto a partir de tiles do Tiny Dungeon,
trocando a foto gerada por IA) → Home → Criação de Personagem → Chat e
barra lateral (incluindo a barra de vida do inimigo em combate, que virou
`PixelBar` real em vez da barra suave antiga) → inventário em grade de
slots (`InventoryGrid`, novo componente) no lugar da lista de texto com
ícone pequeno.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Lib de UI pixel pronta (ex. NES.css) | zero trabalho de sourcing/componentização | paleta e proporções fixas da lib, não dos tokens `rpg-*` já existentes; reintroduziria uma segunda linguagem visual em cima da primeira (Etapa 11) | o objetivo era estender o que já existe, não substituir |
| Pixelizar ícones de interface pura com um pacote genérico (Kenney "Game Icons") | cobre fechar/menu/som/setas prontos | é um pacote flat/vetorial (linhas finas e suaves), não pixel-art — quebraria a mesma consistência de densidade de pixel que o ADR-0017 já havia protegido para os sprites | desenhar à mão manteve o mesmo contorno/densidade dos outros ícones |
| `PanelFrame`/`PixelButton` com sprite de "pressionado" dedicado | feedback de clique mais autêntico ao pixel art | exigiria um segundo estado de sprite por variante de botão (6 arquivos a mais) sem um pacote que já tivesse isso pronto no mesmo estilo | `transform`+`brightness` já era o padrão de feedback de clique usado no resto do app antes desta etapa |

## Consequências

**Ganhamos:**
- Três componentes reutilizáveis (`PixelIcon`, `PanelFrame`, `PixelButton`)
  que qualquer tela nova do jogo pode usar sem reinventar a moldura/botão.
- 19 ícones de jogo + 6 desenhados à mão, todos no mesmo tratamento visual
  (contorno preto, preenchimento chapado, 16×16).
- `PanelFrame` aceita `title`/`aria-label`/`tabIndex` (`...rest` repassado
  pro `<div>`) — usado pelos slots de inventário pra dar tooltip e foco por
  teclado sem outro wrapper.
- A barra de vida do inimigo em combate usa o mesmo `PixelBar` do herói —
  antes eram dois tratamentos visuais diferentes pro mesmo tipo de dado.
- Corrigiu de passagem um bug preexistente: `CharacterCreation.tsx`
  referenciava `/assets/background-default.jpg`, um arquivo que não existe
  mais desde a reorganização de assets do B-1 — o fallback caía num
  placeholder externo (`via.placeholder.com`) que também falha offline.

**Pagamos:**
- Ícones sem sprite equivalente (`User`, `Sparkles`, `Zap`, `Dices`,
  `AlertTriangle`, `ThumbsUp`/`ThumbsDown`, `Send`, `Map`, `Loader2`,
  `Edit2`) continuam `lucide-react` — mistura de traço fino com pixel art
  nesses pontos específicos, aceita conscientemente em vez de forçar um
  ícone hand-drawn de qualidade duvidosa só por consistência total.
- `PanelFrame`/`PixelButton` usam `border-image`, que não tem um
  equivalente direto de "sprite pressionado" — o feedback de clique é
  aproximado (transform+brightness), não um frame de sprite dedicado.

**Fica em aberto:**
- Bolhas de mensagem do chat, caixa de input e modais usam apenas bordas
  quadradas (sem `PanelFrame`) por design — o plano explicitamente evitou
  moldura pesada em elementos que rolam a tela inteira. Se o efeito visual
  ficar fraco demais comparado ao resto, vale reconsiderar uma versão mais
  leve de `PanelFrame` (borda mais fina) para esses casos.
- Nenhum teste automatizado cobre os novos componentes (são puramente
  visuais); a verificação desta etapa foi manual, no navegador.

## Como saber que erramos

Se ao testar em tela pequena (375px) os ícones de 12-14px ficarem
ilegíveis, ou se o `border-image` de `PanelFrame`/`PixelButton` esticar
de forma visivelmente distorcida em algum tamanho de botão específico —
verificado no C-1 nos tamanhos usados até agora (botões grandes, sidebar,
inventário), mas não em toda combinação futura possível.

## Referências

- `docs/adr/0017-identidade-visual-pixel-art-rota-2.md` — decisão original que este ADR estende.
- `docs/CREDITOS.md` — fonte, licença e lista completa dos ícones novos.
- [Tiny Dungeon](https://kenney.nl/assets/tiny-dungeon), [Roguelike/RPG Pack](https://kenney.nl/assets/roguelike-rpg-pack), [UI Pack - Pixel Adventure](https://kenney.nl/assets/ui-pack-pixel-adventure) — os três pacotes-fonte (Kenney, CC0).
