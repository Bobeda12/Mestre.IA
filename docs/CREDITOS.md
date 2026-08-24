# Créditos

Recursos de terceiros usados no projeto, com licença e atribuição — a regra é
simples: se a licença pede crédito, ele está aqui; se não pede (CC0), ainda
assim credito por educação.

## Trilha sonora (Etapa 11, B-4)

Quatro faixas em loop, uma por tema (`Frontend/src/lib/trilha.ts`), baixadas
do [OpenGameArt.org](https://opengameart.org):

| Tema | Faixa | Autor | Licença | Fonte |
|---|---|---|---|---|
| `aventura` | Dungeon 05 | Beau Buckley (Fantasy Musica) | [CC-BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) | [opengameart.org/content/dungeon-05](https://opengameart.org/content/dungeon-05) |
| `combate` | Basilisk Boss Battle Loop | beardalaxy | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/basilisk-boss-battle-loop](https://opengameart.org/content/basilisk-boss-battle-loop) |
| `suspense` | Dungeon Ambience | yd | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/dungeon-ambience](https://opengameart.org/content/dungeon-ambience) |
| `tristeza` | Small Loss | HorrorPen | [CC-BY 3.0](https://creativecommons.org/licenses/by/3.0/) | [opengameart.org/content/small-loss](https://opengameart.org/content/small-loss) |

**Nota sobre "Dungeon 05" (CC-BY-SA 4.0):** compartilhar-igual se aplica a
*adaptações* do arquivo — ele é usado aqui sem edição, só com atribuição.

## Sprites de raça/classe/monstro (Etapa 11, B-1)

> **Atualizado na revisão da Etapa 14 ([ADR-0025](adr/0025-retratos-por-ia-pixelizados-por-script.md)):**
> os **21 retratos de raça e classe** passaram a vir do **Dungeon Crawl Stone
> Soup** (tabela abaixo). Os sprites Kenney descritos aqui continuam sendo a
> fonte dos **5 monstros** (`monstros/`), dos ícones e das molduras.

## Retratos de raça e classe (revisão da Etapa 14)

| Pacote | Autor | Licença | Fonte |
|---|---|---|---|
| Dungeon Crawl 32x32 tiles | equipe do Dungeon Crawl Stone Soup | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/dungeon-crawl-32x32-tiles](https://opengameart.org/content/dungeon-crawl-32x32-tiles) |

São personagens de fantasia completos (com equipamento e silhueta própria)
em 32×32, o dobro da resolução dos sprites de 16×16 — é isso que permite o
MESMO arquivo servir ao ícone de 48px da lista e ao painel grande, sem os dois
conjuntos de arte que existiram na fase intermediária.

O catálogo cobre justamente os arquétipos que faltavam no pacote anterior:
draconiano alado para o Draconato, *demonspawn* com chifres para o Tiefling e
orc armado para o Meio-Orc — os três "encaixes forçados" que o ADR-0017
registrava. Para as classes há mago, necromante, arqueiro élfico, ladrão
encapuzado e sacerdote, entre outros.

Os 5 sprites de monstro em `Frontend/public/assets/monstros/` (e,
historicamente, os 21 retratos) vêm de dois pacotes CC0 feitos para serem
compatíveis entre si (mesmo estilo 16×16, mesma paleta fechada), sem geração
por IA:

| Pacote | Autor | Licença | Fonte |
|---|---|---|---|
| Tiny Dungeon | Kenney | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/tiny-dungeon](https://opengameart.org/content/tiny-dungeon) |
| Tiny Creatures | Clint Bellanger (com permissão da Kenney) | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/tiny-creatures](https://opengameart.org/content/tiny-creatures) |

Nenhuma das duas licenças exige atribuição — está aqui por educação, e para
rastrear de onde cada sprite veio caso precise trocar depois.

**Substituições sem correspondência direta no D&D 5e** (nenhum pacote
gratuito tem draconato/tiefling/meio-orco prontos — mais próximo disponível,
mantendo o mesmo estilo em vez de misturar fontes):

| Precisa de | Usei o sprite de | Por quê |
|---|---|---|
| Draconato | "dragonkin" (Tiny Creatures) | humanoide com cabeça de dragão — o mais literal possível |
| Tiefling | "devil" (Tiny Creatures) | chifres + pele vermelha, a codificação visual clássica |
| Meio-Orc | "orc" (Tiny Creatures) | pele verde + presas |
| Halfling | "leprechaun" (Tiny Creatures) | povo pequeno, estatura baixa |
| Gnomo | "pixie" (Tiny Creatures) | diminuto, traços simples |

**Encaixes fracos, aceitos por falta de opção melhor no mesmo estilo**
(Elfo, Clérigo, Monge usam sprites de aldeão genérico do Tiny Dungeon — sem
orelha pontuda, símbolo sagrado ou traje de monge visível a 16px; nenhuma
fonte CC0/CC-BY encontrada tinha esses três SEM quebrar a consistência
visual com o resto do conjunto).

## Ícones de jogo, painéis e botões (Etapa 14, C-1)

`Frontend/public/assets/icons/` e `Frontend/public/assets/ui/` — mesma
regra do B-1: sem geração por IA, pacotes CC0 escolhidos por serem
compatíveis em estilo (16×16, contorno grosso) com o que já estava no repo.

| Pacote | Autor | Licença | Fonte | Usado para |
|---|---|---|---|---|
| Tiny Dungeon | Kenney | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [kenney.nl/assets/tiny-dungeon](https://kenney.nl/assets/tiny-dungeon) | espada, adaga, machado, maça, escudo, 4 poções, baú (já usado no B-1, mesmo arquivo-fonte) |
| Roguelike/RPG Pack | Kenney | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [kenney.nl/assets/roguelike-rpg-pack](https://kenney.nl/assets/roguelike-rpg-pack) | pergaminho (missão), mochila (inventário), moeda (ouro), e os tiles de terreno do mapa de fundo (`backgrounds/mapa-mundo.png`) |
| UI Pack - Pixel Adventure | Kenney | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [kenney.nl/assets/ui-pack-pixel-adventure](https://kenney.nl/assets/ui-pack-pixel-adventure) | moldura 9-slice (`PanelFrame`) e botões (`PixelButton`) |

Nenhuma licença exige atribuição (todas CC0) — está aqui por educação e
para rastrear a origem de cada arquivo.

**Composto a partir de tiles CC0**: `backgrounds/mapa-mundo.png` é um mapa de
overworld montado tile a tile a partir do Roguelike/RPG Pack (grama, água,
terra, árvores), numa grade toroidal pra ladrilhar sem emenda nos dois eixos —
ver `MapaDeFundo.tsx`. Não é arte gerada, é composição de tiles existentes.

**Desenhados à mão** (estrela/nível, fechar, menu, seta, som ligado/mudo,
coroa, coração, menos, mais, dado, rosto, alerta, polegar cima/baixo, enviar,
cura, caveira):
nenhum pacote pesquisado (Tiny Dungeon, Roguelike/RPG Pack, UI Pack - Pixel
Adventure, Game Icons, UI Pack RPG Expansion) tinha esses num estilo
coerente com o resto — em vez de misturar um pacote genérico incompatível,
foram desenhados como pixel art simples (contorno preto + preenchimento
chapado, mesmo tratamento visual dos outros ícones) via script Python
(Pillow), não gerados por IA. Os oito últimos entraram na revisão da Etapa 14,
que tirou o `lucide-react` das telas de jogo (`GameChat`, `RollCard`,
`StatusCard`) — hoje o pacote não é mais importado em lugar nenhum do `src/`.
