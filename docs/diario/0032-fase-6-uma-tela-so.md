# Fase 6 do plano "jogo completo": uma tela só

**Período:** 08–09/09/2026 · sessão seguinte às Fases 0 a 5

## O que aconteceu

As cinco fases anteriores entregaram camadas de jogo de verdade — Mundo Vivo, itens,
aliados, level-up, arcos, bestiário — mas cada uma pousou o seu pedaço de tela sem que
ninguém parasse para olhar o conjunto. O jogador via a tela como um Frankenstein: um
palco de combate com o seu próprio console de comandos, um painel "Mundo Vivo" separado
logo abaixo, o chat de narrativa por baixo dos dois, cada bloco rolando por conta própria,
e três lugares diferentes para fazer a mesma coisa ("falar com Olma" podia vir do console,
do painel Mundo Vivo, ou do texto livre). Esta fase reorganiza a apresentação inteira, sem
mudar o motor por baixo. A decisão está no
[ADR-0036](../adr/0036-uma-tela-um-palco-um-dock.md).

## O que o jogador sente

- **Uma tela, sem rolar a página.** O topo mostra vida, foco e nível numa linha só; o
  palco fica logo abaixo, sempre do mesmo tamanho; só o texto do mestre rola; embaixo, uma
  barra de ação e o campo de texto. Nada mais empurra a tela pra baixo.
- **O Mundo Vivo virou parte do palco.** As pessoas do lugar (NPCs) aparecem ao lado do
  herói, com retrato da raça, e dá pra clicar nelas direto na cena. Objetos e saídas
  formam uma prateleira na base do palco. O painel separado, com seus `<select>` de ação,
  não existe mais.
- **Uma barra de ação só.** Selecionou alguém ou algo, os verbos daquela pessoa/objeto
  aparecem ali (Examinar, Conversar, Negociar...); em combate, é Atacar, Defender,
  Técnicas, Táticas e Itens; sem nada selecionado, as sugestões de sempre mais Descansar.
  Negociar, ajudar, intimidar, distrair e acalmar usam o próprio campo de texto como
  proposta — sem abrir uma caixa à parte.
- **Capítulo, conflitos e objetivo foram para a ficha.** A aba que era "Missão" virou
  "Jornada" e reúne tudo isso; "Relações" agora mostra também confiança e memórias das
  pessoas do Mundo Vivo, não só a reputação numérica de antes.
- **O mercador ganhou um balcão de verdade** — um quadro que abre por cima da tela, em vez
  de um trecho dentro do painel antigo.
- **A leitura mudou de cara.** A narrativa e os textos da ficha usam agora uma fonte de
  livro (Alegreya) em vez da fonte de terminal (VT323) e da fonte do resto do app (Geist);
  os títulos e badges curtos continuam na fonte de fliperama (Press Start 2P).
- **No celular, os alvos de toque cresceram** para pelo menos 44 pixels, a barra de ação e
  a prateleira de objetos rolam de lado com uma "trava" suave em cada item, e os menus da
  barra de ação (Técnicas, Táticas...) abrem como uma folha subindo da base da tela.

## O que mudou por baixo

- `GameChat.tsx` (que já passava de 2000 linhas) virou só o dono do estado; a apresentação
  se espalhou em componentes novos, todos em `Frontend/src/components/jogo/`:
  `LogNarrativa`, `AbaJornada`, `AbaRelacoes`, `BalcaoMercador`, `Palco`, `DockAcoes`,
  `HudBarra`. `AdventureStage.tsx` e `LivingWorld.tsx` (e `CabecalhoRegiao.tsx`) saíram.
- Uma seleção só (`{tipo: 'inimigo'|'pessoa'|'objeto', id}`), guardada em `GameChat`,
  substitui os dois estados de seleção que existiam antes (um no console de combate, outro
  no painel Mundo Vivo).
- `Frontend/src/lib/verbos.ts` (novo) concentra a regra "que botões aparecem para esta
  pessoa/objeto" — antes vivia dentro do JSX do painel Mundo Vivo.
- Fontes trocadas via `@fontsource` (auto-hospedadas, como já era o Geist): Alegreya no
  lugar de Geist e VT323; Press Start 2P continua, mas com uma regra mais clara — só rótulo
  curto sem acento, porque essa fonte não desenha vogal acentuada. Isso pegou um bug
  escondido: alguns rótulos acentuados ("CAPÍTULO ENCERRADO", "NÍVEL", "CRIAÇÃO") estavam
  na fonte errada há tempos e o acento simplesmente sumia; corrigidos junto.
- `h-dvh` no lugar de `h-screen` na raiz da tela — no celular, a barra de endereço do
  navegador some e volta sem que a altura "trave" errado.

## Como testei

- `tsc --noEmit`, `npm run build` e `npx eslint` limpos em cada etapa (as poucas
  pendências de lint encontradas já existiam antes desta fase, sem relação com ela).
- vitest: 16 casos novos para `verbos.ts`, 7 para `DockAcoes` (sem seleção, combate,
  seleção com verbo social entrando em modo proposta, verbo direto, limpar seleção), 3
  para `AbaJornada` (encerrar capítulo respeita o que o servidor decide). Suíte:
  49 de 51 verdes — as 2 restantes já falhavam antes desta fase.
- Ao vivo, no navegador, com um herói de teste: selecionar um NPC e negociar por texto
  (teste de carisma rolado, narrativa e confiança do NPC caindo de verdade); examinar um
  objeto da prateleira sem abrir modo de proposta; abas Jornada e Relações mostrando
  capítulo, conflito e memórias; telas de 375×812 e 768×1024 sem vazar conteúdo pra fora
  da tela (achado e corrigido um vazamento horizontal real: faltava `min-w-0` na coluna do
  chat, o que empurrava o rodapé pra fora da área escurecida da gaveta da ficha no
  celular).

## O que ficou registrado para depois

- `e2e/jogar-um-turno.spec.ts` está quebrado desde antes desta fase (o fluxo de login
  mudou; o teste ainda espera cair direto na seleção de raça). Sinalizado à parte; o passo
  "clicar ator → verbo → resposta" que esta fase pedia para o e2e fica para quando esse
  conserto entrar.
- `guardrail.opcoes_padrao` (Backend) ainda sugere "Verificar o inventário" mesmo com a
  ficha sempre visível — pode não fazer mais sentido, não mexido nesta fase.
- Confirmação ao vivo de `comerciar` pelo Balcão com resposta real do narrador fica para
  quando a cota do provedor gratuito permitir (o mesmo problema de sempre).
