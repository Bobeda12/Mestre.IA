# ADR-0017 — Identidade visual 8-bit: Rota 2 (sprites reais), não Rota 1 (pele sobre a arte atual)

**Data:** 23/08/2026
**Status:** Aceito
**Etapa:** 11
**Supersede:** —

---

## Contexto

`docs/backlog-pos-lancamento.md` (item B-1) recomendava a **Rota 1**: manter as 21 artes fotográficas/pintadas já existentes (`Frontend/public/assets/{races,classes}/*.jpg`, geradas por IA na Etapa 4) e aplicar um filtro de pixelização em build time — paleta fechada, fonte pixel, moldura 9-slice, sem trocar arte nenhuma. A justificativa era custo: ~12h contra ~30h+ da Rota 2, e "zero arte jogada fora".

O autor pediu a **Rota 2** — arte pixel de verdade, uma peça por raça/classe/monstro — com duas condições que restringiram bastante o espaço de busca:

1. **Sem geração por IA.** As artes atuais (pollinations.ai) já eram uma fonte de queixa antes deste ADR (ver B-3, foto do personagem) — gerar sprites pixel também por IA herdaria o mesmo problema de fidelidade E adicionaria o risco de inconsistência de estilo entre 26 gerações separadas, que o próprio backlog já apontava como o risco real da Rota 2.
2. **8-bit denso, estilo NES** — paleta fechada, poucos pixels, sem gradiente.

## Decisão

**Todos os 26 sprites (9 raças + 12 classes + 5 monstros) vêm de dois pacotes CC0 do mesmo par de autores, feitos para serem compatíveis entre si:** [Tiny Dungeon](https://opengameart.org/content/tiny-dungeon) (Kenney) e [Tiny Creatures](https://opengameart.org/content/tiny-creatures) (Clint Bellanger, com permissão da Kenney — mesma paleta, mesma densidade de 16×16, mesma espessura de contorno). Curadoria manual, peça por peça — não um script, não uma geração em lote.

**Toda a curadoria veio de uma fonte só, de propósito.** Testei três outras rotas antes de decidir isso:
- **Pollinations.ai / geração por IA** — descartada pela condição do autor.
- **LPC (Liberated Pixel Cup)** — a base aberta mais usada para RPG 2D, mas é um sistema modular (corpo + roupa + arma em camadas separadas); virar um retrato por raça/classe exigiria montar um pipeline de composição (Pillow, múltiplas camadas PNG) em vez de usar arte pronta. O gerador oficial que faria isso visualmente (`liberatedpixelcup.github.io/Universal-LPC-Spritesheet-Character-Generator`) não carregou no navegador sandboxed usado para a pesquisa.
- **itch.io** — bloqueado por verificação anti-bot; não deu para navegar o catálogo.
- **Pacotes "portrait" (ex. RPG Icons, DitzyDM)** — têm exatamente os retratos que faltavam (Clérigo, por exemplo), mas num estilo pintado/sombreado (~32×32, mais cores) claramente diferente da densidade do Tiny Dungeon/Tiny Creatures. Descartado explicitamente para não repetir o "risco real" que o próprio backlog nomeou: consistência de estilo entre peças de fontes diferentes.

**Substituições sem correspondência direta no D&D 5e** — nenhum pacote gratuito tem draconato/tiefling/meio-orco prontos:

| Raça pedida | Sprite usado | Por quê |
|---|---|---|
| Draconato | "dragonkin" (Tiny Creatures) | humanoide com cabeça de dragão — o mais literal possível |
| Tiefling | "devil" (Tiny Creatures) | chifres + pele vermelha, a codificação visual clássica do arquétipo |
| Meio-Orc | "orc" (Tiny Creatures) | pele verde + presas |
| Halfling | "leprechaun" (Tiny Creatures) | povo pequeno, estatura baixa |
| Gnomo | "pixie" (Tiny Creatures) | diminuto, traços simples |

**Três encaixes fracos, aceitos conscientemente:** Elfo, Clérigo e Monge usam sprites de aldeão genérico do Tiny Dungeon — nenhum dos dois pacotes tem orelha pontuda, símbolo sagrado ou traje de monge visível a 16px. Pesquisei fontes alternativas especificamente para esses três (incluindo um sprite de "dark elf" de verdade) e todas quebravam a consistência de estilo mais do que valiam — o autor confirmou aceitar o encaixe genérico em vez disso. Lista completa, com fonte e licença de cada peça, em `docs/CREDITOS.md`.

Junto com os sprites: `image-rendering: pixelated` (seletor por caminho `/assets/{races,classes,monstros}/`, sem precisar de classe em cada `<img>`), `object-fit: contain` com respiro (16×16 esticado por `object-cover` em um painel de 560px vira um borrão de blocos gigantes), fonte Press Start 2P só em títulos curtos e grandes (VT323 no resto — Press Start 2P quebra layout em texto longo), classe utilitária `.pixel-frame` (borda dupla, cantos retos, sem `border-radius`) e `PixelBar` (barra de vida/XP em blocos discretos, no lugar do `<Progress>` com preenchimento suave).

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Rota 1 (recomendação original do backlog) | ~12h, zero arte jogada fora, sem risco de sourcing | o autor já tinha decidido reverter essa recomendação antes deste ADR — não é mais uma opção viva, só o ponto de partida do backlog | decisão de produto do autor, não técnica |
| Gerar os 26 sprites por IA (pollinations, mesmo método do B-3) | rápido, sem sourcing manual, controle total sobre pose/ângulo | reintroduz o problema de fidelidade que motivou o B-3 pra foto do personagem, e soma o risco de inconsistência de estilo entre 26 gerações separadas | condição explícita do autor: "sem IA" |
| Misturar pacotes por encaixe individual (ex. RPG Icons pro Clérigo, Tiny Dungeon pro resto) | resolveria os 3 encaixes fracos com sprites mais fiéis ao tipo | quebra a consistência visual entre os 26 — exatamente o risco que o backlog nomeou como o problema real da Rota 2 | consistência > perfeição individual, e foi confirmado com o autor depois de mostrar a comparação lado a lado |
| LPC com pipeline de composição próprio | arte modular "de verdade" (corpo+roupa+arma), mais fiel à tradição de RPG sprite sheets | pipeline de composição (múltiplas camadas, Pillow) é trabalho de engenharia bem maior do que integrar sprites prontos — o gerador oficial que faria isso visualmente não funcionou no ambiente de pesquisa disponível | descartado por custo, não por qualidade — fica registrado como opção real se o Nível 2 de fidelidade visual algum dia justificar o investimento |

## Consequências

**Ganhamos:**
- 26 sprites reais (não gerados), de dois pacotes desenhados para serem compatíveis entre si — zero mistura de densidade de pixel ou paleta entre eles.
- Licença CC0 nos dois pacotes — nenhuma atribuição obrigatória, mas creditada em `docs/CREDITOS.md` por educação e rastreabilidade.
- `image-rendering: pixelated` e `object-fit: contain` aplicados por seletor de caminho (`img[src^="/assets/races/"]` etc.) — qualquer sprite novo adicionado nesses diretórios já herda o tratamento certo, sem precisar lembrar de adicionar uma classe.
- `PixelBar` e `.pixel-frame` são reutilizáveis — qualquer barra ou moldura nova no resto do app pode usar o mesmo padrão sem duplicar CSS.

**Pagamos:**
- **Elfo, Clérigo e Monge são visualmente genéricos** — um jogador que conhece D&D pode notar que esses três não têm o marcador visual esperado (orelha pontuda, símbolo sagrado, traje de monge). Documentado, não escondido.
- **Draconato, Tiefling, Meio-Orc, Halfling e Gnomo são aproximações**, não sprites desenhados para o arquétipo exato do 5e — usam o humanoide mais próximo disponível nos dois pacotes.
- Sprites de 16×16 não escalam bem para um retrato grande (ex. painel de ~560px da Ficha Final) — mesmo com `object-fit: contain`, o sprite renderizado fica pequeno e cercado de espaço vazio, porque o alternativa (esticar) fica pior ainda. É uma limitação inerente ao tamanho de origem, não um bug.

**Fica em aberto:**
- Os 5 sprites de monstro só aparecem hoje no card de inimigo em combate (ícone pequeno, `w-4 h-4`) — comportamento de monstro (D-4) e retratos maiores de monstro (D-5), ambos da Etapa 13, ainda não usam esses sprites em nenhum outro lugar.
- Paleta fechada e substituição de gradientes por blocos foi aplicada aos elementos tocados nesta etapa (PixelBar, `.pixel-frame`, títulos) — uma varredura completa de todo gradiente/sombra suave do app inteiro não foi feita, e não estava no escopo aprovado.

## Como saber que erramos

Se, ao testar com amigos, a reação mais comum for confusão sobre qual raça/classe é qual (em vez de "os sprites são simples, mas dá pra saber o que é") — especialmente nos três encaixes fracos — é sinal de que a consistência de estilo não estava valendo o preço da fidelidade individual, e vale reconsiderar a mistura de pacotes descartada acima, pelo menos para Elfo/Clérigo/Monge.

## Referências

- `docs/backlog-pos-lancamento.md` — item B-1, a recomendação original (Rota 1) e o "risco real" de consistência de estilo que motivou a fonte única aqui.
- `docs/CREDITOS.md` — autor, licença e fonte de cada um dos 26 sprites.
- [Tiny Dungeon](https://opengameart.org/content/tiny-dungeon) e [Tiny Creatures](https://opengameart.org/content/tiny-creatures) — os dois pacotes-fonte.
