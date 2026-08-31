# Plano de Remaster UX/UI — "Cara de Jogo"

> Baseado em `UI_UX_DESIGN.md`. Objetivo: sair de "clone de ChatGPT" para um videogame de verdade, sem perder o que já foi construído.

## 0. Princípio de adaptação

O documento de visão fala em texturas de RPG de papel (pergaminho, couro, metal). O Mestre.IA **já não é** um mockup em branco — ele já tem uma identidade Pixel Art/8-bit estabelecida (`Frontend/src/index.css`, componentes `Pixel*`). Este plano não importa as texturas do documento ao pé da letra: ele as traduz para essa linguagem já existente. Regra geral: **se já existe um jeito pixel de fazer aquilo, estender; só criar do zero o que realmente não tem equivalente hoje.**

### Tabela de adaptação (documento → pixel art)

| Ideia do documento | Leitura literal | Adaptação Pixel Art/8-bit |
|---|---|---|
| "Papel envelhecido" / pergaminho | textura de papel, sombra suave | **Pixel Frame com paleta quente**: `.pixel-frame` (borda dourada dupla, cantos retos) sobre fundo `--color-rpg-parchment`/`--color-rpg-leather` |
| "Botões metálicos/madeira" | bevel realista, gradiente | **Botões Pixelados Dourados**: bevel de 2px em degrau (sem gradiente contínuo), glow em *steps* no hover, deslocamento de 1px no clique — nunca `border-radius` |
| "Brilho (glow) suave" | `filter: blur()` largo | Glow discreto e pulsado, reaproveitando o keyframe `pulse-glow` já existente — luz que pisca como um console, não um halo de CSS moderno |
| "Ícones vetoriais brilhantes" | SVG suavizado | Sprites `PixelIcon` (16×16/32×32), `image-rendering: pixelated` |
| "Notificação flutuante (Toast)" | card flutuante com sombra soft | Toast com moldura quadrada pixelada, ícone pixel, entrada em *steps* |
| "Fundo de papel/dark mode fantasia" | textura de papel escaneado | Paleta já definida (`rpg-dark`, `rpg-darker`, `rpg-crimson`) + `MapaDeFundo.tsx` |

## 1. O que já existe (não reconstruir)

Levantamento do código atual, para as fases construírem em cima disso:

- **Tokens e fontes** (`Frontend/src/index.css`): `--font-rpg` (VT323), `--font-pixel-title` (Press Start 2P), `--color-rpg-gold/crimson/parchment/leather/dark`, paleta `gray-*` requentada (matiz 70°), `.pixel-frame`.
- **Keyframes já implementados**: `shake` (dano), `floatUp` (dano flutuante — Etapa 7), `pulse-glow` (respiração/level-up), `fadeIn`, `scaleIn`, `blocosCarregando`, `mapaDeslizando`, `balancarEspada`. Kill-switch global em `prefers-reduced-motion`.
- **Componentes pixel**: `PixelBar.tsx`, `PixelButton.tsx`, `PixelIcon.tsx`, `PanelFrame.tsx`, `RetratoPixelado.tsx` (retrato de IA pixelizado, ver ADR-0025), `MapaDeFundo.tsx`.
- **`GameChat.tsx`** (~1436 linhas): vitals bar (HP/nível/defesa), narração em bolhas, sugestões táticas (`opcoes`) como botões simples, sidebar em abas JRPG (`STATUS | ITENS | MISSÃO | RELAÇÕES | REGRAS`), `RollCard`/`StatusCard` para rolagens e eventos de regra, overlay de GAME OVER full-screen.
- **Backend** (`Backend/app/routers/game.py`, `Backend/app/domain/state.py`): estado via SSE (frames `token`/`tool_event`/`state`), modelos `WorldState`/`CombatState`/`QuestLog`. Ferramentas relevantes em `Backend/app/services/tools.py`: `dar_item`, `aplicar_dano`, `iniciar_combate`, `gastar_ouro`, `ajustar_reputacao_npc`.
- **Sem framer-motion hoje** — toda animação é CSS puro. Este plano introduz framer-motion, mas só nos pontos onde CSS puro fica frágil (ver Fase 3).

## 2. As 4 fases

---

### Fase 1 — Layout Core e Área do Chat
*(Seção 2 do documento, + parte da Seção 3 — a "Mesa do Mestre")*

**Objetivo:** a área central para de parecer WhatsApp/ChatGPT.

- Narração do Mestre deixa de ser bolha de chat e passa a fluir como parágrafos dentro de um Pixel Frame (parchment/leather), sem contorno de balão. Ajuste em `GameChat.tsx` (bloco de renderização de mensagens, atualmente ~L1277 em diante).
- Sugestões táticas (`opcoes`, hoje botões simples ~L1400) viram **Cartas de Ação Pixeladas** — novo componente `PixelActionCard.tsx`: cartão dourado/madeira, cantos retos, glow em hover (reaproveita `pulse-glow` em versão mais sutil).
- Feedback de sistema puro (ex.: "Você perdeu 3 de Ouro") sai da bolha de chat e vira **toast flutuante pixelado** no topo da tela — novo `SistemaFeedbackToast.tsx`. `RollCard` e `StatusCard` continuam exatamente como estão (já pixelizados) para rolagens e eventos de combate — só eventos de recurso puro (ouro, item recebido fora de combate) migram pro toast.
- Novos keyframes em `index.css`: entrada/saída do toast (`steps`, no espírito de `blocosCarregando`), glow de hover do `PixelActionCard`.

**Arquivos-chave:** `Frontend/src/components/GameChat.tsx`, `Frontend/src/components/PixelActionCard.tsx` (novo), `Frontend/src/components/SistemaFeedbackToast.tsx` (novo), `Frontend/src/index.css`.

**Como testar:** playtest ao vivo — disparar uma ação que gere `tool_event` de recurso (ouro/item) e confirmar o toast; confirmar que as opções táticas aparecem como cartas com glow no hover; confirmar que a narração não parece mais bolha de chat.

---

### Fase 2 — Sidebar Gamificada e Status
*(Seção 1 do documento — o Painel do Herói)*

**Objetivo:** a sidebar (que já existe e já é abas JRPG) ganha vida.

- **Barras animadas**: estender `PixelBar.tsx` — flash vermelho + tremor (`shake`) quando HP cai; glow (`pulse-glow`) na barra de XP ao subir de nível.
- **Ícones de status**: novo `StatusEffectIcons.tsx` ao lado do retrato (`RetratoPixelado`), piscando quando há efeito ativo (veneno, etc.) — depende de o backend expor status de efeito ativo; confirmar campo durante a implementação.
- **Diário de Bordo**: a aba "MISSÃO" vira um card "pergaminho" com a missão atual sempre visível + accordion "A Jornada Até Aqui", puxando o resumo rolante que o backend já gera para a memória do LLM (nome exato do campo a confirmar em `Backend/app/domain/state.py` / payload do frame `state`).
- **Mundo e clima**: card lendo `WorldState` (local/clima), com leve efeito CSS de chuva quando aplicável.
- **Cards de NPC**: hover com `translateY(-2px)` + tooltip de reputação, usando o Radix Tooltip que já é dependência do projeto (`Frontend/src/components/ui/tooltip`, já usado por `RollCard`/inventário).

**Arquivos-chave:** bloco de sidebar em `GameChat.tsx` (~L737+), `PixelBar.tsx`, `StatusEffectIcons.tsx` (novo), refino da aba MISSÃO existente, `Frontend/src/index.css`.

**Como testar:** playtest — tomar dano (barra pisca), subir de nível (glow), passar mouse num NPC (lift + tooltip), abrir/fechar o accordion da jornada.

---

### Fase 3 — Feedback Sensorial e Animações de Dano/Loot
*(Seções 3 e 4 do documento — Juice e Imersão Avançada)*

**Objetivo:** dopamina visual imediata em combate e recompensas. Esta é a fase que mais introduz componentes novos.

- **Dano Flutuante generalizado**: o keyframe `floatUp` já existe para dano; generalizar para cura (`+N` verde), ouro e XP — novo `FloatingCombatText.tsx`, acionado pelos `tool_event` de `aplicar_dano`, cura, `gastar_ouro`/ganho de ouro, XP.
- **Animação de Loot (abertura de baú)**: novo `LootRevealOverlay.tsx` — tela escurece, ícone do item aparece brilhando no centro, depois **voa até o slot de inventário na sidebar**. Este é o caso de uso principal de framer-motion neste plano (`layoutId` para a transição de posição centro → sidebar, algo frágil de coreografar só em CSS). Acionado por `dar_item` (`Backend/app/services/tools.py`).
- **Ciclo dia/noite e ambiência**: estender `MapaDeFundo.tsx` para trocar paleta/overlay por hora do dia (campo a confirmar no `WorldState` do backend — hoje expõe local/clima, hora do dia pode não existir ainda).
- **Bestiário interativo**: nova aba "BESTIÁRIO" no array `ABAS` da sidebar, `BestiarioTab.tsx` — grid de cards de monstro usando os sprites já existentes em `/assets/monstros/`, silhueta até o primeiro encontro, contagem de abates (precisa de campo novo no backend — a confirmar/dimensionar à parte, não assumir que já existe).
- **Ficha de Personagem em modal**: `FichaModal.tsx`, abre ao clicar no retrato (mesmo padrão dos modais já existentes — `retratoAberto`, `MenuConfiguracao` — em `GameChat.tsx`), ficha D&D completa em layout pergaminho full-screen.

**Arquivos-chave:** `Frontend/src/index.css`, `FloatingCombatText.tsx` (novo), `LootRevealOverlay.tsx` (novo, framer-motion), `BestiarioTab.tsx` (novo), `FichaModal.tsx` (novo), `MapaDeFundo.tsx`, wiring em `GameChat.tsx`. **Nesta fase o `framer-motion` entra como dependência nova** (`Frontend/package.json`).

**Como testar:** playtest — dano/cura/ouro/XP flutuando corretamente; pegar um item e ver a sequência completa de loot; alternar dia/noite visualmente; matar um monstro pela primeira vez e ver o card desbloquear no bestiário; abrir a ficha de personagem.

---

### Fase 4 — Áudio e Telas Modais
*(Seção 5 do documento — a fronteira final)*

**Objetivo:** cruzar de "aplicativo web" para "jogo" de verdade.

- **Curadoria de áudio real**: buscar/selecionar 2 trilhas adaptativas royalty-free (taverna/calma e combate) + efeitos sonoros (dado rolando, item, level up, golpe). Créditos documentados em `Frontend/public/audio/CREDITOS_AUDIO.md`, seguindo o padrão já usado em `docs/CREDITOS.md` para os sprites.
- **`useAdaptiveMusic.ts`**: hook que observa `combat_active` (vindo do `state` SSE) e faz crossfade entre as duas trilhas — `<audio>`/Web Audio API, sem dependência nova.
- **`useSfx.ts`**: hook para tocar efeitos por tipo de `tool_event` (rolagem → dado, `dar_item` → chime, `aplicar_dano` → impacto).
- **Controle de volume/mute**: adicionar ao modal `MenuConfiguracao.tsx` já existente.
- **Tela de Morte / Hall da Fama**: promover o overlay de GAME OVER (hoje só um `absolute inset-0` dentro de `GameChat.tsx`) para uma rota real `/heroi-caido/:sessionId` — fade-to-black, música triste, epitáfio, pontuação (XP + turnos sobrevividos + abates do bestiário), e o herói morto passa a aparecer como "lenda" no roster de `Home.tsx`. **Precisa de campos novos no backend** (marcar personagem como morto + pontuação) — a confirmar e dimensionar à parte antes de iniciar esta parte da fase.
- **Tooltips de atributos**: nos 6 atributos da aba STATUS da sidebar, usando o Radix Tooltip já disponível — "Força 16 → Modificador +3, usado em ataques corpo a corpo e atletismo".

**Arquivos-chave:** `Frontend/src/hooks/useAdaptiveMusic.ts` (novo), `useSfx.ts` (novo), `Frontend/public/audio/*` (novo), `MenuConfiguracao.tsx`, nova rota em `App.tsx` + tela de Hall da Fama (novo componente), `Home.tsx` (exibição de lendas no roster), aba STATUS da sidebar.

**Como testar:** entrar/sair de combate e ouvir o crossfade; rolar dado e ouvir o SFX; morrer e ver a sequência completa (fade, epitáfio, pontuação); conferir se o personagem morto aparece como lenda na Home.

## 3. Riscos e decisões em aberto

- Vários pontos (resumo rolante da jornada, hora do dia no `WorldState`, contagem de abates por monstro, morte/pontuação persistidas) dependem de campos que podem não existir ainda no backend hoje — cada fase que depende de um desses deve confirmar o campo real antes de implementar, e dimensionar a extensão de backend separadamente se faltar.
- `framer-motion` é escopo restrito: só entra na Fase 3 (loot voando) e pontualmente na Fase 4 (sequência de morte). Tudo que já funciona bem em CSS puro (hover, glow, barras, shake) continua em CSS — não trocar padrão que já funciona.

## 4. Ordem de execução

Fase 1 → Fase 2 → Fase 3 → Fase 4. Cada fase termina com playtest manual ao vivo antes de avançar para a próxima — nada de validar só por leitura de código.

## 5. Status de execução (31/08/2026)

As 4 fases foram implementadas e testadas ao vivo (backend + frontend reais, não só leitura de código). Duas correções ficaram registradas durante o trabalho:

- **Fase 4 começou com uma descoberta**: a trilha sonora adaptativa (`useTrilha`/`calcularTema`, crossfade por tema, mute/volume) **já existia inteira** antes deste plano — não precisou ser construída, só os efeitos sonoros (`useSfx.ts`) eram novos de fato.
- **Bug real corrigido de passagem**: o glow (e agora o som) de "subir de nível" disparava sozinho ao carregar um personagem já acima do nível 1 — a referência de "nível anterior" nascia em 1 em vez do valor carregado. Corrigido junto da Fase 4.

### Pendências — resolvidas em 31/08/2026

As quatro pendências abaixo (registradas no fim da Fase 4) foram resolvidas na mesma data, com o `Pré-requisito de backend` de cada uma implementado de verdade — migration `0014_bestiario_e_morte`, testes (`464 passed`) e verificação direta contra `ToolExecutor` (a fila de IA compartilhada estava esgotada no dia, então a verificação ao vivo via navegador cobriu o que dava — hora do dia/período visíveis na sidebar — e o resto foi confirmado chamando os métodos do backend diretamente, sem mock de LLM onde não precisava).

1. **Ícones de status** — as três flags de `CombatState` (`heroi_escondido`, `heroi_bonus_ca`, `heroi_vantagem_inimiga`) agora saem em todo frame `state` (`routers/game.py:_resposta`) e viram ícone piscando ao lado do retrato (`StatusEffectIcons.tsx`).

2. **Hora do dia e ambiência** — `WorldState.hora_do_dia` (0-23) avança por ação lógica de verdade: `mover` +2h, `descansar("curto")` +1h, `descansar("longo")` +8h (`services/tools.py`); `rules_engine.periodo_do_dia` traduz pra madrugada/manhã/tarde/noite, injetado no prompt do narrador (`[CENA]`) e mostrado na sidebar. **Ainda em aberto, por decisão de escopo, não por falta de tempo:** arte de cenário por bioma/hora — o jogo não tem nenhum fundo de cena hoje (só `MapaDeFundo.tsx`, exclusivo da tela inicial), e produzir isso é trabalho de asset, não de código; a ambiência reage à hora com um véu de cor sutil (`.periodo-*` em `index.css`) em vez de arte nova.

3. **Bestiário persistente** — `Personagem.monstros_derrotados: dict[str, int]`, incrementado só em `ToolExecutor._conceder_xp` (o único lugar que sabe "este combate acabou, estes morreram"). Testado diretamente contra o `ToolExecutor` (fora do navegador, pela fila de IA esgotada): duas rodadas de vitória incrementaram corretamente (`{"Goblin": 1}` → `{"Goblin": 2, "Kobold": 1}`).

4. **Hall da Fama** — `Personagem.morto_em`/`pontuacao_final`, preenchidos no mesmo commit que confirma a morte (`_persistir_epitafio_se_confirmado`). Pontuação = XP + turnos sobrevividos + 10 por abate no bestiário (testado diretamente: XP 350 + turno 42 + 3 abates×10 = 422, bateu). A Home ganhou uma seção "Salão dos Heróis Mortos" com a pontuação de cada lenda; a tela de morte (`GameChat.tsx`, `gameOver`) já mostra tudo isso ao carregar um herói morto — **não foi criada uma rota `/heroi-caido/:sessionId` separada**, por ser redundante: `/jogar/:sessionId` já cobre o caso (decisão consciente, registrada aqui em vez de simplesmente ignorada).
