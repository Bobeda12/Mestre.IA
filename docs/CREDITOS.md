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

## Efeitos sonoros (Fase 4 do remaster UX, PLANO_REMASTER_UX.md)

Quatro efeitos curtos em `Frontend/public/assets/audio/sfx/` (`useSfx.ts`),
mesma fonte das trilhas acima:

| Efeito | Arquivo | Autor | Licença | Fonte |
|---|---|---|---|---|
| Dado rolando | `dado.flac` | Wuzzy | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/wooden-dice-on-wodden-table-roll](https://opengameart.org/content/wooden-dice-on-wodden-table-roll) |
| Item recebido | `item.wav` | Fupi | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/plingy-coin](https://opengameart.org/content/plingy-coin) |
| Subir de nível | `levelup.wav` | Haley Halcyon | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/8bit-fanfare-jingle-the-lick](https://opengameart.org/content/8bit-fanfare-jingle-the-lick) |
| Golpe de espada | `golpe.ogg` (recorte `sword.1.ogg` do pacote) | StarNinjas | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/20-sword-sound-effects-attacks-and-clashes](https://opengameart.org/content/20-sword-sound-effects-attacks-and-clashes) |

Nenhuma licença exige atribuição — está aqui pela mesma razão de sempre.
`dado.flac`/`item.wav`/`levelup.wav` ficaram no formato original do
download (FLAC/WAV, não OGG como a trilha) porque não havia `ffmpeg`
disponível pra converter — funcionam normalmente no `<audio>` dos
navegadores que o projeto já alveja, só quebra a convenção de extensão das
trilhas.

## Sprites de raça/classe/monstro (Etapa 11, B-1)

> **Atualizado na revisão da Etapa 14 ([ADR-0025](adr/0025-retratos-por-ia-pixelizados-por-script.md)):**
> raça e classe passaram a ter DUAS fontes de arte, uma por tamanho — não uma
> substituindo a outra. O ícone pequeno da lista de seleção (`races/`,
> `classes/`) vem do **Dungeon Crawl Stone Soup** (tabela abaixo). O painel
> grande da criação e o retrato do herói na ficha (`retratos/races/`,
> `retratos/classes/`) usam arte gerada por IA e pixelizada por script — a
> **única** exceção no projeto à regra "sem geração por IA" do ADR-0017,
> registrada porque colide com ela, não porque a substitui. Os sprites Kenney
> descritos aqui continuam sendo a fonte dos **5 monstros** (`monstros/`), dos
> ícones e das molduras.

## Ícone pequeno de raça e classe (revisão da Etapa 14)

| Pacote | Autor | Licença | Fonte |
|---|---|---|---|
| Dungeon Crawl 32x32 tiles | equipe do Dungeon Crawl Stone Soup | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/dungeon-crawl-32x32-tiles](https://opengameart.org/content/dungeon-crawl-32x32-tiles) |

São personagens de fantasia completos (com equipamento e silhueta própria)
em 32×32, o dobro da resolução dos sprites de 16×16 — legíveis e distintos
entre si num ícone de 48px, que era o problema do pacote anterior.

O catálogo cobre justamente os arquétipos que faltavam nele: draconiano
alado para o Draconato, *demonspawn* com chifres para o Tiefling e orc
armado para o Meio-Orc — os três "encaixes forçados" que o ADR-0017
registrava. Para as classes há mago, necromante, arqueiro élfico, ladrão
encapuzado e sacerdote, entre outros.

## Retrato grande de raça/classe e retrato do herói

Gerado por IA (image.pollinations.ai) e pixelizado por script/no navegador
(`getRetrato` em `Frontend/src/lib/utils.ts`; `RetratoPixelado.tsx` para o
retrato do herói, que muda a cada personagem). **Não é CC0** — é a única arte
do projeto que não é. O ADR-0025 explica por que essa exceção existe (o
sprite de 32×32 ampliado num painel de ~400px é pequeno demais pra ocupar o
espaço) e por que ela não se estendeu ao ícone pequeno.

Os 5 sprites de monstro em `Frontend/public/assets/monstros/` vêm de dois
pacotes CC0 feitos para serem compatíveis entre si (mesmo estilo 16×16, mesma
paleta fechada), sem geração por IA:

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

## Marcas de ferimento no retrato (rodada de polish pós-remaster, item 9)

Splats em `Frontend/public/assets/effects/` (`ferimento-leve.png`,
`ferimento-medio.png`, `ferimento-grave.png`), sobrepostos ao retrato do
herói e tingidos de vermelho via `mask-image` (`HudPersonagem.tsx`) conforme
a vida cai — sem geração por IA, mesmo pacote Kenney já usado pra outros
sprites/molduras do projeto:

| Pacote | Autor | Licença | Fonte |
|---|---|---|---|
| Splat Pack | Kenney | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [kenney.nl/assets/splat-pack](https://kenney.nl/assets/splat-pack) |

Três arquivos do pacote (`splat05`, `splat14`, `splat26` do conjunto
"Default (256px)") renomeados por tier de gravidade — a forma exata do splat
não tem significado além de "mais ou menos marcado"; a cor vem inteira do
`mask-image`, não do PNG original (que é uma silhueta preta/cinza).

## Ícones de jogo, painéis e botões (Etapa 14, C-1)

`Frontend/public/assets/icons/` e `Frontend/public/assets/ui/` — mesma
regra do B-1: sem geração por IA, pacotes CC0 escolhidos por serem
compatíveis em estilo (16×16, contorno grosso) com o que já estava no repo.

| Pacote | Autor | Licença | Fonte | Usado para |
|---|---|---|---|---|
| Tiny Dungeon | Kenney | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [kenney.nl/assets/tiny-dungeon](https://kenney.nl/assets/tiny-dungeon) | adaga, machado, maça, escudo, 4 poções, baú (já usado no B-1, mesmo arquivo-fonte) |
| Roguelike/RPG Pack | Kenney | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [kenney.nl/assets/roguelike-rpg-pack](https://kenney.nl/assets/roguelike-rpg-pack) | pergaminho (missão), mochila (inventário), moeda (ouro), e os tiles de terreno do mapa de fundo (`backgrounds/mapa-mundo.png`) |
| UI Pack - Pixel Adventure | Kenney | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [kenney.nl/assets/ui-pack-pixel-adventure](https://kenney.nl/assets/ui-pack-pixel-adventure) | moldura 9-slice (`PanelFrame`) e botões (`PixelButton`) |

Nenhuma licença exige atribuição (todas CC0) — está aqui por educação e
para rastrear a origem de cada arquivo.

**Cenário da tela inicial e do login** (`backgrounds/cidade-fundo.png` e
`cidade-frente.png`):

| Pacote | Autor | Licença | Fonte |
|---|---|---|---|
| GothicVania Town | ansimuz | [CC0](https://creativecommons.org/publicdomain/zero/1.0/) | [opengameart.org/content/gothicvania-town](https://opengameart.org/content/gothicvania-town) |

São as camadas `background` e `middleground` do pacote, usadas em parallax
(ver `MapaDeFundo.tsx`). Duas edições foram feitas: a saturação do céu baixou
(o original é bem rosa e o app é ouro/couro), e a camada da frente virou a
original seguida da própria imagem espelhada, porque sozinha ela não ladrilhava
— espelhar faz a borda direita virar cópia da esquerda e a costura fecha por
construção.

Antes disto o fundo era um mapa de overworld que eu montava tile a tile por
script. Passou por quatro abordagens (sorteio por tile, suavização celular,
Voronoi toroidal, marcos esparsos) e em nenhuma deixou de parecer manchado —
a mesma lição dos retratos de raça/classe: arte pronta feita à mão ganha de
arte composta por algoritmo.

**Desenhados à mão** (estrela/nível, fechar, menu, seta, som ligado/mudo,
coroa, coração, menos, mais, dado, rosto, alerta, polegar cima/baixo, enviar,
cura, caveira, espada):
nenhum pacote pesquisado (Tiny Dungeon, Roguelike/RPG Pack, UI Pack - Pixel
Adventure, Game Icons, UI Pack RPG Expansion) tinha esses num estilo
coerente com o resto — em vez de misturar um pacote genérico incompatível,
foram desenhados como pixel art simples (contorno preto + preenchimento
chapado, mesmo tratamento visual dos outros ícones) via script Python
(Pillow), não gerados por IA. Os oito últimos entraram na revisão da Etapa 14,
que tirou o `lucide-react` das telas de jogo (`GameChat`, `RollCard`,
`StatusCard`) — hoje o pacote não é mais importado em lugar nenhum do `src/`.
`espada` entrou nesta lista na rodada de polimento de UX pós-lançamento
(26/08/2026): o recorte original do Tiny Dungeon ficava com contraste baixo
e silhueta confusa em 16px. A primeira tentativa de redesenho (lâmina
vertical) não agradou — em vez de tentar de novo às cegas, foram geradas
várias variações (vertical/diagonal × paleta fria dos vizinhos Kenney/paleta
preto+dourado dos ícones à mão) e enviadas como preview antes de aplicar
qualquer uma. A escolhida foi a lâmina **diagonal**, na paleta preto+dourado
já usada por estrela/fechar/coroa/seta (contorno `#0A0806`, off-white
`#EBE8E0`, dourado `#C5A059`) — diferente da orientação vertical dos vizinhos
Kenney (adaga/machado/maça/escudo), mas consistente com a família de ícones
desenhados à mão do projeto. Ainda na mesma rodada, o traço fino ficou fraco
nos usos maiores (botão NOVO JOGO, tela de transição) — a lâmina engrossou
(~3px) e a guarda virou uma cruz perpendicular de verdade, num canvas 20×20
(os demais ícones à mão continuam 16×16; este é o único maior, por causa do
tamanho de exibição bem acima da média dos outros).
