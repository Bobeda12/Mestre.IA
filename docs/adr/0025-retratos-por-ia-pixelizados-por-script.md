# ADR-0025 — Retratos de raça/classe: sprites CC0 do Dungeon Crawl

**Data:** 24/08/2026
**Status:** Aceito
**Etapa:** 14 (revisão)
**Supersede:** parcialmente o [ADR-0017](0017-identidade-visual-pixel-art-rota-2.md) — acrescenta uma segunda fonte de arte para raça/classe, sem remover a primeira. Os sprites CC0 do Kenney continuam em uso nos ícones pequenos; os monstros, ícones e molduras seguem inalterados.

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

**Usar o tileset do [Dungeon Crawl Stone Soup](https://opengameart.org/content/dungeon-crawl-32x32-tiles) (CC0, 32×32)** para os 21 retratos de raça e classe.

A geração por IA foi tentada e **descartada depois de aplicada e vista no lote inteiro**. O pipeline funcionava tecnicamente (o resultado ERA pixel art, com grade e paleta fechada), mas o conteúdo não servia: meia dúzia de classes saiu como a mesma mulher de cabelo escuro, halfling e gnomo não liam como halfling e gnomo — o descritor deles é sobre estatura, e estatura não aparece num busto — e o draconato virou uma estátua de pedra. Diferenciação entre opções é requisito funcional numa tela de seleção de personagem, não preferência estética.

O DCSS resolve isso porque são **personagens completos desenhados à mão**, com equipamento e silhueta própria, e o catálogo cobre exatamente os arquétipos que faltavam: draconiano alado (Draconato), *demonspawn* com chifres (Tiefling), orc armado (Meio-Orc) — os três "encaixes forçados" do ADR-0017 — além de mago, necromante, arqueiro élfico, ladrão encapuzado e sacerdote para as classes.

**Uma fonte só para os dois tamanhos.** Houve uma fase intermediária com dois conjuntos (sprite Kenney de 16×16 no ícone, retrato de IA no painel) porque nenhuma fonte servia bem aos dois. Os 32×32 do DCSS têm resolução suficiente para o painel e legibilidade suficiente para o ícone de 48px, então o segundo caminho (`getRetrato`, `assets/retratos/`) foi removido em vez de virar duas pastas para manter em sincronia.

Detalhe de aplicação que importa: o painel grande usa `object-contain`, não `object-cover`. `cover` num sprite de corpo inteiro de 32×32 recorta a figura e amplia um pedaço até virar mancha — foi o primeiro resultado, e é o oposto do que se quer.

## Alternativas consideradas

- **Manter os sprites Kenney** — coerentes e CC0, mas mantêm os encaixes fracos e o problema de escala que motivou o pedido.
- **Gerar por IA e pixelizar por script** — implementado por inteiro e revertido depois de ver o lote (motivo acima). O pipeline ficou registrado aqui porque a lição vale: quando o modelo não entrega o formato pedido por mais explícito que seja o prompt, transformar a saída com código determinístico funciona — o que falhou foi o CONTEÚDO gerado, não a conversão.
- **Usar a ilustração da IA crua** — em outra linguagem visual; brigaria com a UI 8-bit ao redor.
- **Forçar contorno escuro na pixelização** — a detecção de bordas dispara também na textura interna (barba, escamas) e empasta o rosto.

## Consequências

- **Continua tudo CC0.** A condição "sem geração por IA" do ADR-0017 acaba preservada na prática, por outro caminho: o que muda é a FONTE dos sprites, não o princípio. Some junto a dívida de licença que a arte gerada teria criado.
- Passam a ser **três** pacotes de arte no projeto (Kenney Tiny Dungeon/Tiny Creatures para monstros e ícones, Kenney UI Pack para molduras, DCSS para retratos). Todos pixel art de contorno marcado, mas o DCSS é 32×32 contra 16×16 dos outros — a diferença aparece se um sprite DCSS for usado ao lado de um Kenney no mesmo tamanho.
- Trocar um retrato é trocar um arquivo do pacote, sem regerar nada.

## Como saber que erramos

- Se os retratos pixelizados lerem como "foto borrada" em vez de sprite ao lado das molduras e ícones 8-bit, o nível de quantização está alto demais — cair para 32×32/16 cores antes de desistir da abordagem.
- Se o autor voltar a reclamar de fidelidade (o problema original da Etapa 4 que o ADR-0017 citava), o caminho é ajustar os descritores em `CharacterCreation.tsx` — eles são a fonte única, então corrigir lá conserta catálogo e retrato do herói de uma vez.

## Referências

- [ADR-0017](0017-identidade-visual-pixel-art-rota-2.md) — decisão original (sprites CC0 curados, sem IA)
- `docs/CREDITOS.md` — origem de cada arquivo de arte
- `Frontend/src/components/CharacterCreation.tsx` — `RACE_VISUAL_EN`/`CLASS_VISUAL_EN`, fonte única dos descritores
