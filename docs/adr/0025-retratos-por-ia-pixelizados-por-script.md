# ADR-0025 — Retratos de raça/classe: duas fontes, cada uma no seu tamanho

**Data:** 24/08/2026
**Status:** Aceito
**Etapa:** 14 (revisão)
**Supersede:** parcialmente o [ADR-0017](0017-identidade-visual-pixel-art-rota-2.md) — troca a fonte dos retratos de raça/classe e abre exceção à regra "sem geração por IA". Monstros, ícones e molduras seguem inalterados, CC0.

---

## Contexto

O ADR-0017 decidiu que os 26 sprites viriam de pacotes CC0 curados à mão, sob duas condições do autor, sendo a primeira **"sem geração por IA"**. A justificativa era boa e continua válida no que ela cobria: as artes por IA da Etapa 4 eram uma queixa de fidelidade, e 26 gerações separadas trariam risco de inconsistência de estilo.

Na revisão visual da Etapa 14 o autor pediu o oposto para os retratos: imagens **maiores e mais detalhadas**, em estilo 16-bit, geradas por IA. O motivo é concreto e visível na tela: um sprite de 16×16 esticado num painel de ~500px vira um bloco de pixels gigantes, e o próprio ADR-0017 já registrava três "encaixes fracos" (Elfo, Clérigo, Monge) mais as substituições forçadas de Draconato, Tiefling e Meio-Orc — justamente as raças que nenhum pacote gratuito cobre.

## O que foi testado antes de decidir

Gerar "pixel art" pedindo isso ao modelo **não funciona**. Duas formulações de prompt, em três raças (Anão, Draconato, Tiefling):

- **A — vocabulário de console:** `16-bit SNES pixel art character portrait ... crisp hard pixel edges, limited color palette`
- **B — especificação técnica:** `pixel art sprite, 64x64 pixel grid ... nearest-neighbor upscale, no anti-aliasing, no blur, 32 color palette`

As duas devolveram **ilustração digital pintada**, com anti-aliasing e milhares de cores. Nenhuma grade de pixel, em nenhuma das seis saídas. Ou seja: a condição do ADR-0017 protegia contra um risco (inconsistência de estilo entre gerações), mas o risco maior aqui é outro — o gerador simplesmente não produz o formato pedido, por mais explícito que seja o prompt.

## Decisão

**Duas fontes de arte para raça/classe, cada uma no tamanho em que funciona:**

| Onde | Arte | Origem |
|---|---|---|
| Ícone da lista de seleção (48px) | sprite de 32×32 | [Dungeon Crawl Stone Soup](https://opengameart.org/content/dungeon-crawl-32x32-tiles), CC0 |
| Painel grande da criação (~400px) | retrato de 48×48 | gerado por IA e pixelizado por script |
| Retrato do herói (ficha, prólogo) | gerado em tempo real | IA, pixelizado no navegador (`RetratoPixelado`) |

Na prática são `getLocalImage` e `getRetrato` (`Frontend/src/lib/utils.ts`), com os arquivos em `assets/{races,classes}/` e `assets/retratos/{races,classes}/`.

**Por que não uma fonte só.** As duas foram tentadas sozinhas, e cada uma falha na ponta oposta:

- **Só IA.** Aplicada ao lote inteiro, a diferenciação colapsou: meia dúzia de classes saiu como a mesma mulher de cabelo escuro, halfling e gnomo não liam como halfling e gnomo (o descritor deles é sobre estatura, e estatura não aparece num busto) e o draconato virou uma estátua de pedra. Reduzidos a 48px na lista, viram um amontoado indistinguível. Diferenciar as opções é requisito funcional numa tela de seleção, não preferência estética.
- **Só DCSS.** São personagens completos desenhados à mão, com equipamento e silhueta própria — excelentes no ícone pequeno, e cobrem justamente os arquétipos que faltavam (draconiano alado, *demonspawn* com chifres, orc armado: os três "encaixes forçados" do ADR-0017). Mas num painel de ~400px um sprite de 32×32 é uma figura pequena e simples ocupando muito espaço, sem a densidade que aquele tamanho pede.

O sprite ganha onde precisa de leitura rápida; o retrato ganha onde precisa de presença.

**Sobre a pixelização da arte gerada.** O pipeline é: gerar solto, saturar, reduzir por média de área e quantizar com *median cut*. As duas primeiras tentativas erraram e vale registrar por quê — reduzir só a resolução mantém o degradê e continua lendo como foto; posterizar cada canal em N níveis fixos achata, mas quantizar R, G e B de forma independente **inventa cor** (fundo bege virando faixas verdes e rosas). *Median cut* escolhe a paleta a partir das cores que a imagem tem, então achata sem sair da identidade cromática.

## Alternativas consideradas

- **Manter só os sprites Kenney de 16×16** (ADR-0017) — mantêm os encaixes fracos e o problema de escala que motivou o pedido.
- **Uma fonte só** — tentado nas duas direções, e cada uma falha numa ponta (ver Decisão).
- **Usar a ilustração da IA crua** — em outra linguagem visual; brigaria com a UI 8-bit ao redor.
- **Forçar contorno escuro na pixelização** — a detecção de bordas dispara também na textura interna (barba, escamas) e empasta o rosto.

## Consequências

- **Nem tudo é mais CC0.** Os ícones pequenos, monstros e molduras seguem CC0; os retratos grandes são saída de modelo generativo, que não tem a mesma clareza de licença. Para um projeto de portfólio single-player é aceitável, mas esta é a primeira dívida a revisitar se o jogo virar produto distribuído — e é a razão pela qual a troca merece um ADR em vez de passar batido.
- **Duas pastas para manter em sincronia.** Acrescentar uma raça ou classe agora exige arte nos dois lugares; esquecer um deles quebra só uma das telas, o que é o tipo de falha que passa despercebida. `getLocalImage`/`getRetrato` deixam isso explícito no código.
- Passam a ser **três** pacotes de arte mais a geração (Kenney Tiny Dungeon/Tiny Creatures para monstros e ícones, Kenney UI Pack para molduras, DCSS para os ícones de raça/classe). O DCSS é 32×32 contra 16×16 dos Kenney — a diferença aparece se os dois forem usados lado a lado no mesmo tamanho.
- Trocar um ícone é trocar um arquivo do pacote; trocar um retrato é rodar o script de novo.

## Como saber que erramos

- Se os retratos pixelizados lerem como "foto borrada" em vez de sprite ao lado das molduras e ícones 8-bit, o nível de quantização está alto demais — cair para 32×32/16 cores antes de desistir da abordagem.
- Se o autor voltar a reclamar de fidelidade (o problema original da Etapa 4 que o ADR-0017 citava), o caminho é ajustar os descritores em `CharacterCreation.tsx` — eles são a fonte única, então corrigir lá conserta catálogo e retrato do herói de uma vez.

## Referências

- [ADR-0017](0017-identidade-visual-pixel-art-rota-2.md) — decisão original (sprites CC0 curados, sem IA)
- `docs/CREDITOS.md` — origem de cada arquivo de arte
- `Frontend/src/components/CharacterCreation.tsx` — `RACE_VISUAL_EN`/`CLASS_VISUAL_EN`, fonte única dos descritores
