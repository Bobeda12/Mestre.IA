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

Os 26 sprites em `Frontend/public/assets/{races,classes,monstros}/` vêm de
dois pacotes CC0 feitos para serem compatíveis entre si (mesmo estilo
16×16, mesma paleta fechada), sem geração por IA:

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
