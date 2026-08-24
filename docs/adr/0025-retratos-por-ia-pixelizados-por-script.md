# ADR-0025 — Retratos de raça/classe: geração por IA pixelizada por script

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

**Gerar solto e pixelizar por script**, em vez de tentar arrancar pixel art do prompt — e usar o resultado APENAS nos painéis grandes.

**Dois conjuntos de arte, cada um no tamanho em que funciona.** Ver os 21 aplicados de uma vez mostrou que substituir tudo era errado: reduzidos a 48px na lista de seleção, os retratos de IA viram um amontoado ilegível, e várias classes ficaram parecidas entre si (meia dúzia delas saiu como a mesma mulher de cabelo escuro). Os sprites de 16×16 do Kenney são o inverso — toscos, porém identificáveis num relance, que é exatamente o trabalho de um ícone de lista. Então:

| Onde | Arte | Por quê |
|---|---|---|
| Ícone da lista de seleção (48px) | sprite Kenney 16×16, CC0 | legível e distinto em tamanho pequeno |
| Painel grande (~400px) | retrato gerado, pixelizado 48×48 | detalhe e presença que o sprite não tem nessa escala |

Na prática são `getLocalImage` e `getRetrato` (`Frontend/src/lib/utils.ts`), e os arquivos vivem em `assets/{races,classes}/` e `assets/retratos/{races,classes}/`.

O pipeline (`gerar_21.py`) é determinístico e reproduzível:

1. **Gera** em 512×512 pelo mesmo provedor que o app já usa pro retrato do herói (image.pollinations.ai), com os **mesmos descritores em inglês** que `CharacterCreation.tsx` já mantinha (`RACE_VISUAL_EN`/`CLASS_VISUAL_EN`) — arte de catálogo e retrato do jogador descrevem a mesma coisa, de uma fonte só.
2. **Satura** (+25%) antes de reduzir: paleta fechada lava a cor, e sprite de console é saturado de propósito.
3. **Reduz para 48×48 com `BOX`** (média da área), não `LANCZOS` — reamostragem com lóbulo negativo deixa halo nas bordas, que é exatamente o que faz "pixel art falsa" parecer suja.
4. **Quantiza para 24 cores com dither desligado** — dither espalha ruído de meio-tom, que em 48×48 lê como sujeira, não como sombreado.

O enquadramento é fixo no prompt (busto, centralizado, de frente, fundo escuro) porque sem isso cada retrato volta num plano diferente e a tela de seleção fica desalinhada.

**Nível 48px/24 cores** escolhido comparando três (48/24, 64/32, 96/48) lado a lado com o sprite Kenney: 96px lê mais como foto reduzida que como sprite; 48px é o mais próximo de arte de console.

## Alternativas consideradas

- **Manter os sprites Kenney** — coerentes e CC0, mas mantêm os encaixes fracos e o problema de escala que motivou o pedido.
- **Usar a ilustração da IA crua** — mais bonita e detalhada, mas em outra linguagem visual; brigaria com a UI 8-bit ao redor (molduras 9-slice, fonte pixel, barras em blocos).
- **Forçar contorno escuro na pixelização** — tentado e descartado: a detecção de bordas dispara também na textura interna (barba, escamas) e empasta o rosto. O resultado sem esse passo é melhor.

## Consequências

- Os 21 retratos passam a ser **arte gerada**, o que o ADR-0017 excluía. Registrado aqui como reversão consciente, não como esquecimento.
- **Não são CC0.** Saída de modelo generativo não tem a mesma clareza de licença dos pacotes Kenney. Para um projeto de portfólio single-player isso é aceitável; se o jogo virar produto distribuído, esta é a primeira dívida a revisitar.
- Os sprites de monstro, ícones e moldura continuam CC0 e curados — a mistura é deliberada, não acidental.
- O pipeline é **determinístico** (`seed=11` fixo): rodar de novo dá o mesmo resultado, e trocar um retrato isolado é regerar um arquivo, não refazer o lote.

## Como saber que erramos

- Se os retratos pixelizados lerem como "foto borrada" em vez de sprite ao lado das molduras e ícones 8-bit, o nível de quantização está alto demais — cair para 32×32/16 cores antes de desistir da abordagem.
- Se o autor voltar a reclamar de fidelidade (o problema original da Etapa 4 que o ADR-0017 citava), o caminho é ajustar os descritores em `CharacterCreation.tsx` — eles são a fonte única, então corrigir lá conserta catálogo e retrato do herói de uma vez.

## Referências

- [ADR-0017](0017-identidade-visual-pixel-art-rota-2.md) — decisão original (sprites CC0 curados, sem IA)
- `docs/CREDITOS.md` — origem de cada arquivo de arte
- `Frontend/src/components/CharacterCreation.tsx` — `RACE_VISUAL_EN`/`CLASS_VISUAL_EN`, fonte única dos descritores
