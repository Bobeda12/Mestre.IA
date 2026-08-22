# Backlog pós-lançamento — o que os primeiros testes revelaram

**Contexto:** o jogo está no ar (Etapa 9 concluída) e passou por testes rápidos do autor,
antes de ser enviado para amigos. Este documento tria as melhorias encontradas e propõe
três ciclos de trabalho — Etapas 10, 11 e 12.

**Triagem:** cada item passa pelas duas perguntas de [PLANO_MESTRE.md](../PLANO_MESTRE.md) §7 —
*vira uma métrica?* e *o jogador sente em um turno?*. Itens que falham nas duas estão no
fim, na sala de espera.

**Como ler as colunas:** `h` é estimativa de horas de trabalho efetivo (o ritmo do projeto é
~10h/semana). Estimativa é chute informado, não promessa.

---

## Mapa das etapas

Quatro etapas novas (10 a 13); duas delas grandes demais para uma entrega só, divididas em
`a` e `b`. **Seis blocos entregáveis, ~172h, ~17 semanas efetivas.** A ordem abaixo é a de
execução, não a numérica — a 13 passa na frente da 12b, e o porquê está no fim do documento.

| Ordem | Bloco | h | Itens | Em uma frase |
|---|---|---|---|---|
| 1 | **10 — O portão dos amigos** | 31 | A-1 … A-7 | dá para mandar o link sem medo |
| 2 | **11a — Identidade** | 19 | B-1, B-2, B-3 | abre a página, tem um endereço decente e parece um jogo |
| 3 | **11b — Os momentos** | 30 | B-4, B-6, B-7, B-8, B-9 | como o jogo soa, abre e fala |
| 4 | **12a — O motor honesto** | 26 | C-1, C-2, C-3, C-8 | as regras aguentam uma hora de partida — e ficam explicadas |
| 5 | **13 — O combate** | 32 | D-1 … D-6 | a luta vira a melhor parte do jogo |
| 6 | **12b — A mesa** | 34 | C-4, C-5, C-6, C-7 | o jogo vira *seu*, e a morte tem peso |

**Se der para fazer só uma coisa:** o B-9 (a voz do mestre, 10h) muda todo turno que
qualquer pessoa vai ler, e não pede migration nem componente novo. É o maior retorno por
hora do documento inteiro.

---

## 0. O que o código já tem — e por que ainda não parece ter

Metade da sua lista já existe no backend e não chega ao jogador. Vale saber antes de
planejar, para não reimplementar:

| Você pediu | Estado real |
|---|---|
| Inventário | ✅ existe (`db.py:Personagem.inventario`, HUD em `GameChat.tsx`) — falta *usar* item pela interface, hoje só o narrador aciona |
| Fotos de raças e classes | ✅ existem, 21 arquivos em `Frontend/public/assets/` — usados só na criação |
| Foto do personagem | ⚠️ meio-existe: `charImage` viaja em `location.state` e **não é persistida**; ao recarregar a página vira a foto genérica da classe |
| Evolução por nível | ✅ motor pronto (`rules_engine.subir_nivel`, `XP_POR_NIVEL`, barra de XP no HUD) — mas a economia está quebrada (ver P-1) |
| Combate gamificado | ⚠️ parcial: iniciativa, alvo clicável, dano flutuante e cards de rolagem já existem; falta *o jogador agir por botão* em vez de digitar |
| Ícone | ❌ `index.html` ainda tem `favicon: /vite.svg` e `<title>frontend</title>` |

### Três problemas que os testes não mostraram, mas o código mostra

**P-1 — A progressão é inalcançável.** A tabela de XP é a do SRD 5e
(`rules_engine.py:25`): nível 5 exige 6500 XP. O bestiário inteiro tem 5 monstros valendo
25–200 XP. Chegar ao nível 5 exige ~130 goblins. Na prática o jogo tem dois níveis, não cinco.

**P-2 — Não existe cura fora de uma poção.** O único item com efeito mecânico é
`"Poção de Cura"` (`tools.py:36`). Não há descanso curto nem longo. O HP só desce — toda
partida longa termina em morte por atrito, não por decisão errada.

**P-3 — Não existe teto de custo por jogador.** O rate limit é 20 requisições/minuto por
sessão (`game.py:81`). Não há orçamento diário por usuário. A chave da Groq é uma só e é
sua. É exatamente a terceira armadilha do PLANO_MESTRE §7 ("a cota no dia do lançamento"),
e ela vira real no minuto em que você mandar o link para dez amigos.

**P-4 — A história que o jogador escreve é jogada fora.** `historia_texto` (até 4000
caracteres, o campo mais pessoal da criação) entra no prompt do prólogo
(`narrator.py:56`) e **nunca é gravada**: não existe coluna para ela em `Personagem`. Ou
seja, o texto que responde "quem é esse personagem" existe por exatamente uma chamada ao
modelo e depois some — o sistema de memória da Etapa 5 nunca o enxerga.

**P-5 — O herói começa num lugar que o mundo não conhece.** `local_inicial` vem como texto
livre do modelo no prólogo e vai direto para `world_state.local`, sem passar pelo catálogo.
`data/locations.json` tem três locais ("Vila de Phandalin", "Masmorra Esquecida", "Floresta
das Sombras") e a ferramenta `mover` valida contra ele. O jogo começa, portanto, fora do
mapa que ele mesmo valida.

**P-6 — O formato da narração nunca foi especificado.** O prompt de sistema
(`narrator.montar_contexto`) diz o que narrar e proíbe JSON, mas não diz **como formatar**.
A bíblia do mestre também não fala de formatação (nenhuma menção a markdown). Enquanto isso
o front renderiza texto cru — `<p className="whitespace-pre-wrap">{msg.content}</p>`,
`GameChat.tsx:509` — sem interpretar markdown nenhum. Quando o modelo decide usar `**` ou
`*`, o jogador vê os asteriscos.

---

## Etapa 10 — O portão dos amigos · ~31h · 3 semanas

**Objetivo:** o link pode ser enviado sem medo — de custo, de lentidão, de constrangimento
e de perder o feedback.

**Por que primeiro:** nada aqui é sobre diversão. É sobre não desperdiçar a única primeira
impressão que você tem com cada amigo, e sobre capturar o que eles sentirem.

| # | Item | h | Métrica? | Sentido no turno? |
|---|---|---|---|---|
| A-1 | Jogar sem e-mail (convidado) | 5 | ✅ funil de entrada | ✅ entra e joga |
| A-2 | Confirmação de e-mail | 4 | ➖ | ➖ |
| A-3 | Teto de custo por usuário/dia | 3 | ✅ custo por sessão | ✅ mensagem honesta em vez de erro |
| A-4 | Botão "isso ficou estranho" | 2 | ✅ dataset de falhas | ➖ |
| A-5 | Gaveta mobile (pendência da Etapa 7) | 4 | ➖ | ✅ o amigo vai abrir no celular |
| A-6 | Latência: medir e cortar | 10 | ✅ p50/p95 do turno, tempo até o 1º token | ✅✅ é o que mais incomoda hoje |
| A-7 | Formato único da narração | 3 | ➖ | ✅ some o `*` sobrando |

> **A etapa passou de 18h para 31h.** No ritmo de ~10h/semana são 3 semanas, não 2. Se
> apertar, A-2 e A-5 escorregam para a Etapa 11 sem prejuízo — A-6 e A-7 não, porque são
> exatamente o que o amigo percebe nos primeiros trinta segundos.

### A-1 — Jogar como convidado

O schema **já permite**: `Usuario.email` é `Mapped[str | None]` (`db.py:18`). Convidado é um
usuário sem e-mail. Não precisa de tabela nova nem de migration.

- `POST /auth/convidado` → cria `Usuario(email=None)`, seta o mesmo cookie de sessão
  assinado que já existe (`services/auth.py`). Rate limit apertado neste endpoint (uma conta
  por IP a cada X minutos), senão vira fábrica de contas.
- `Login.tsx`: botão **"Jogar agora"** acima do formulário, não abaixo. O e-mail vira o
  caminho secundário.
- `POST /auth/reivindicar` → o convidado preenche e-mail+senha **no mesmo `usuario_id`**;
  os heróis continuam sendo dele. É uma linha de UPDATE, e é o que torna a coisa toda
  honesta: ninguém perde progresso ao criar conta.
- O convite para reivindicar aparece depois do **primeiro momento bom** — a primeira vitória
  ou o fim da primeira cena — não na porta de entrada.
- Teste obrigatório: convidado cria herói → reivindica → herói continua acessível; e um
  convidado não enxerga o herói de outro (o mesmo teste de IDOR da Etapa 8).

**Risco:** o cookie de convidado é a única prova de identidade dele. Limpou o navegador,
perdeu o herói. Isso precisa estar escrito na tela, em uma linha, sem drama.

### A-2 — Confirmação de e-mail

- Campo `email_verificado: bool` em `Usuario` + migration Alembic.
- O token **não precisa de tabela**: reaproveite o HMAC que já assina o cookie
  (`services/auth.py`), com payload `{usuario_id, exp}` e validade de 24h. Link
  `GET /auth/confirmar?token=…`.
- Envio: Resend ou Postmark (plano gratuito resolve). Mesmo padrão condicional do Google —
  sem `RESEND_API_KEY` configurada, o backend **loga o link no console** e o fluxo continua
  funcionando em desenvolvimento (`opcoes()` já faz isso para o Google, `routers/auth.py:41`).
- **Política recomendada — confirmação suave:** joga sem confirmar; um aviso discreto pede a
  confirmação; e-mail não confirmado não pode trocar senha nem recuperar conta. Bloquear o
  jogo na porta custa jogadores reais para resolver um problema (spam) que você ainda não tem.

### A-3 — Teto de custo por usuário/dia

Você já grava `EventoTelemetria` por turno (`db.py:109`). Conte os turnos do dia por
`usuario_id` e corte em um teto configurável (sugestão inicial: 60 turnos/dia para conta
com e-mail, 20 para convidado). Ao estourar: HTTP 429 com uma mensagem *do mestre*, não do
servidor — "a taverna fecha ao anoitecer; volte amanhã". O mesmo tratamento vale para o 429
que vem da própria Groq. Hoje um erro de cota provavelmente aparece cru para o jogador.

### A-4 — Botão "isso ficou estranho"

Você já tem 👍/👎 por narração (`FeedbackNarracao`, Etapa 9). Adicione um campo de texto
opcional ao 👎 e grave junto o índice do turno. Durante o teste com amigos isso vale mais
que qualquer eval: é a única forma de saber *o que* incomodou, e alimenta o mesmo dataset
humano da Etapa 6.

### A-6 — Latência: medir primeiro, cortar depois

O relato é "depois do deploy ficou mais lento". Isso tem causas identificáveis no código, e
elas se dividem em duas famílias muito diferentes.

**Regra antes de tudo: meça.** O Langfuse já instrumenta as chamadas ao modelo, mas o
caminho suspeito aqui é o que **não** é chamada ao modelo — banco, embeddings, boot. Antes
de mexer, coloque um span (ou um `time.perf_counter()` logado, serve) em quatro pontos do
turno: recuperação de memória, embedding, laço do agente, escrita final. Otimizar sem isso
é chutar — e a Etapa 6 existe justamente para você não ser a pessoa que chuta.

**Família 1 — o boot da máquina (é o que mudou com o deploy).**

- `min_machines_running = 0` com `auto_stop_machines = 'stop'` (`fly.toml`): a máquina
  **desliga** quando ninguém joga. O primeiro turno depois de um tempo parado paga o boot
  inteiro. É a diferença mais óbvia entre o localhost (sempre quente) e a produção.
- O `CMD` do `Dockerfile` roda `uv run --no-dev alembic upgrade head` **a cada partida da
  máquina** — sync implícito do `uv` + conexão ao Neon + checagem de migrations, tudo antes
  do uvicorn sequer abrir a porta. Migration é trabalho de *deploy*, não de *boot*: isso
  deveria ser um release command do Fly, rodado uma vez por versão.
- **O modelo de embeddings não está no imagem.** `fastembed` baixa o
  `paraphrase-multilingual-MiniLM-L12-v2` do HuggingFace **na primeira vez que é usado**, ou
  seja, dentro do primeiro turno de um jogador numa máquina nova. Baixar no `docker build`
  (e carregar o modelo num hook de *lifespan*, não no primeiro pedido) tira esse custo do
  caminho do jogador de uma vez.
- A VM é `shared-cpu-1x`, 1 vCPU compartilhado. Os embeddings rodam **localmente em ONNX**
  (`infra/embeddings.py`) — na sua máquina isso é instantâneo, num vCPU compartilhado não é.

**Família 2 — o custo por turno, que cresce com a partida.**

- `memory.memorias_relevantes` faz `db.query(EventoMemoria).filter(...).all()` — **todos** os
  eventos do personagem, **com os embeddings**, a cada turno, para só então fazer BM25 e
  cosseno em Python (`memory.py:63`). Com SQLite local isso era leitura de arquivo; com Neon
  é uma transferência de rede que cresce a cada turno jogado. Se a lentidão piora conforme a
  sessão avança, é aqui. Correção imediata: `.order_by(turno.desc()).limit(N)`. Correção
  boa: filtrar candidatos no SQL antes de trazer vetor nenhum.
- São **dois** embeddings por turno (a busca e o `registrar_evento`), ambos síncronos, ambos
  no caminho da resposta.
- O laço do agente pode dar até `agent_max_passos = 6` idas e voltas à Groq num único turno
  — cada ferramenta chamada é uma chamada nova ao modelo.
- `atualizar_resumo_rolante` dispara **outra** chamada ao modelo a cada ~8 turnos, dentro do
  pedido, antes do `db.commit()` e antes do frame `state`.
- Se o guardrail acusa violação, `corrigir_narrativa` é **mais** uma chamada — depois de o
  jogador já ter lido o texto.
- O modelo principal é o `gpt-oss-120b`; o `20b` da cadeia de fallback é sensivelmente mais
  rápido.

**Ordem sugerida de ataque** (as três primeiras são baratas e provavelmente resolvem a maior
parte):

1. Modelo de embedding embutido na imagem + carregado no startup.
2. `alembic upgrade head` fora do `CMD` (vira release command).
3. Limitar os eventos trazidos do banco por turno.
4. Mover `registrar_evento` e `atualizar_resumo_rolante` para **depois** do frame `state` —
   escrita de memória não precisa segurar a resposta do jogador (`BackgroundTasks`).
5. Só então decidir sobre `min_machines_running = 1`, que custa dinheiro por mês e é a
   última coisa a comprar, não a primeira.

**Métrica de pronto:** p50 e p95 do tempo até o primeiro token, medidos antes e depois,
escritos no diário. Isso é conteúdo de post — "meu jogo ficou 4x mais rápido e eu sei
exatamente por quê" é uma frase que precisa dos dois números.

### A-7 — Formato único da narração

O modelo às vezes responde em markdown e o chat mostra os asteriscos crus. Causa exata: o
prompt de sistema nunca diz qual é o formato de saída (proíbe JSON e pede prosa, e só), e o
front renderiza texto puro sem interpretar markdown (`GameChat.tsx:509`). Ninguém está
errado — o contrato nunca foi escrito.

**Duas correções, e as duas juntas** — é o mesmo padrão de fronteira de confiança do
ADR-0002: pedir ao modelo é a primeira linha, validar no servidor é a que vale.

1. **Diga o formato no prompt.** Uma frase em `montar_contexto` e uma seção na bíblia:
   prosa corrida, sem markdown, sem `*`, `**`, `#`, listas ou blocos de código; ênfase pela
   escolha da palavra, não pela tipografia.
2. **Normalize no servidor**, antes de persistir — uma função pequena e determinística
   (`limpar_formatacao`) ao lado do guardrail que já existe em `services/guardrail.py`.
   Persistir limpo importa porque o histórico vira contexto do próximo turno: sujeira
   formatada ensina o modelo a formatar mais.

**O detalhe não óbvio, e é o que vai te morder:** no caminho de streaming os tokens saem um
a um, e um `**` pode chegar partido entre dois frames — não dá para passar regex num pedaço.
Então: limpeza leve no cliente enquanto o texto flui (um passe simples sobre o acumulado, não
sobre o pedaço), e a normalização de verdade no servidor sobre o texto completo, antes de
gravar. O frame `correcao` do SSE já estabelece o precedente de "o cliente ajusta o texto
depois que ele terminou".

**Decisão a tomar junto:** hoje o próprio sistema injeta `*({erro})*` e linhas com emoji
(`🎲`, `💀`) dentro da narrativa. Se a regra é "nada de markdown", esses também precisam
mudar de forma — ou virar mensagens estruturadas separadas, que é mais limpo e combina com
os `RollCard` que já existem.

---

## Etapa 11 — Cara de jogo · ~49h · 5 semanas (dividida em 11a e 11b)

**Objetivo:** a primeira tela já diz "isto é um jogo", antes de qualquer texto ser lido.

### A decisão que precisa de ADR: qual 8-bit

Isto é uma troca de identidade visual — toca toda a interface e desvaloriza (ou não) as 21
artes que já existem. Duas rotas honestas:

**Rota 1 — pele arcade sobre a arte atual (recomendada, ~12h).** Fonte de pixel
(*Press Start 2P* para títulos, *VT323* para corpo), paleta fechada de 16 cores, molduras
9-slice, `image-rendering: pixelated`, barras de vida em blocos em vez de gradiente, ícones
em pixel-art no lugar dos `lucide-react` no HUD. As fotos de raça/classe entram por um
filtro de pixelização feito **em build time** (downscale + quantização de cores por script,
não filtro CSS em tempo real — filtro CSS custa quadro e não quantiza a paleta). Resultado:
identidade coesa, zero arte jogada fora.

**Rota 2 — arte pixel nova (~30h + custo de geração).** 9 raças + 12 classes + 5 monstros +
itens, tudo redesenhado. O risco real não são as horas: é a **consistência de estilo** entre
21 imagens geradas separadamente, que é onde esse tipo de projeto costuma ficar feio.

**Recomendação:** Rota 1 agora, com sprites pixel dos 5 monstros junto (são cinco, é barato
e é o que mais parece jogo durante o combate). Retratos pixel entram depois, um por vez, se
você quiser.

| # | Item | h | Observação |
|---|---|---|---|
| B-1 | Sistema visual 8-bit (Rota 1) | 12 | tokens em `index.css`, componente `PixelFrame`, script de pixelização |
| B-2 | O link: endereço, ícone e cartão | 4 | o endereço em si, favicon 32×32, `<title>`, `og:image` — ver abaixo |
| B-3 | Foto do personagem que persiste | 3 | campo `imagem` em `Personagem`; hoje se perde ao recarregar |
| B-4 | Música por tema | 6 | ver abaixo |
| B-6 | Tela de morte arcade | 3 | GAME OVER + estatísticas da run (a retrospectiva de IA é o item C-4) |
| B-7 | Tela de abertura da campanha | 7 | quem é o herói, como chegou ali, onde está — ver abaixo |
| B-8 | Dados explicados (qual atributo, de onde vem o bônus) | 4 | ver abaixo |
| B-9 | A voz do mestre: dramática em vez de descritiva | 10 | **o maior impacto por hora do backlog inteiro** |

> **Etapa 11 chegou a 47h**, e pede a mesma divisão que a 12:
> **11a — identidade** (B-1, B-2, B-3 · 19h) e **11b — os momentos** (B-4, B-6, B-7, B-8,
> B-9 · 30h). E veja a nota no fim do B-9: ele é forte candidato a ser puxado para a Etapa
> 10, na frente de itens mais caros e menos sentidos.

### B-2 — O link

Hoje o link é `https://mestre-ia-seven.vercel.app`, e o `-seven` é sufixo automático da
Vercel por colisão de nome, não escolha sua. Quando ele cai num grupo de WhatsApp, ele
aparece sem ícone, com o título "frontend" (`index.html` nunca foi editado) e sem imagem de
prévia. São três coisas separadas, e só a última custa dinheiro.

**1. Tirar o `-seven` — grátis, ~20 minutos.** Renomear o projeto na Vercel (Settings →
General → Project Name) muda o endereço para `mestre-ia.vercel.app`, se estiver livre. O
que quebra junto, e é onde essa mudança dá trabalho de verdade:

- `CORS_ORIGINS` no Fly (`fly secrets set` — lembrando que ele é string separada por
  vírgula, não JSON, e do `MSYS_NO_PATHCONV=1` se for pelo git-bash; os dois já morderam
  você na Etapa 9)
- `frontend_url` nas settings do backend — é para onde o OAuth do Google redireciona
- As origens e URIs autorizadas no Google Cloud Console, quando o OAuth de produção sair
- `README.md:7` e `docs/runbook.md:6`

O `Frontend/vercel.json` **não** muda: ele aponta para o Fly.io, não para o próprio front.

**2. Cartão de link — grátis, ~1h.** `<title>` de verdade, favicon, e `og:image` +
`og:title` + `og:description`. A imagem de prévia pode ser uma arte 1200×630 no estilo
definido em B-1. Isso é o que faz a diferença entre "um link" e "um jogo" na hora em que
alguém compartilha.

**3. Domínio próprio — o único item pago do backlog inteiro.** `.com.br` no Registro.br sai
por ~R$40/ano; `.com` por ~US$12/ano. Na Vercel é Settings → Domains, dois registros de DNS,
e o certificado sai sozinho. O Fly também aceita domínio próprio de graça.

Duas notas honestas sobre isto:

- **Reverte uma decisão da Etapa 9**, onde domínio próprio ficou de fora deliberadamente.
  Reverter é legítimo — só merece uma linha no diário dizendo por quê, senão daqui a seis
  meses parece esquecimento.
- **Tem um ganho técnico escondido, e não é pequeno.** Com `app.seudominio.com` e
  `api.seudominio.com`, front e back passam a ser o *mesmo site* para efeito de cookie
  (`SameSite=Lax` vale entre subdomínios do mesmo domínio registrável) — que é exatamente o
  problema que o proxy `/api/*` da Vercel existe para contornar (ADR-0015). Ou seja: o
  domínio próprio resolve na raiz o que hoje é contornado. **Mesmo assim, não mexa no proxy
  agora** — ele funciona, e trocar dois mecanismos ao mesmo tempo é como se perde um fim de
  semana. Fica registrado como simplificação futura.

**Ordem recomendada:** faça 1 e 2 agora (grátis, e o link melhora hoje); decida sobre o 3
quando quiser. Um domínio de verdade no link do currículo lê diferente de um `.vercel.app` —
esse, e não a técnica, é o argumento a favor.

### B-4 — Música por tema, sem virar projeto próprio

- **O tema vem do estado, não do modelo.** `combate ativo → combate`; `hp < 30% → suspense`;
  `gameOver → tristeza`; senão `aventura`. Pedir o tema ao LLM adiciona latência e uma chance
  de erro para resolver algo que o servidor já sabe.
- Hook `useTrilha(tema)` com crossfade de ~1,5s. Trocar faixa a seco é pior que não ter música.
- **Autoplay é bloqueado por todos os navegadores** até o primeiro gesto do usuário. A
  trilha começa no primeiro clique — na prática, ao criar o personagem ou enviar a ação.
- Botão de mudo persistido em `localStorage`, e **começar mudo** é defensável: o amigo pode
  estar no ônibus.
- Faixas CC0/CC-BY (Kenney, OpenGameArt, Incompetech). Loops curtos em `.ogg`, ~1MB cada.
  Crédito em `docs/CREDITOS.md` — usar CC-BY sem atribuir é violação de licença, e é o tipo
  de descuido que aparece no portfólio.

### B-7 — Tela de abertura da campanha

**O prólogo já existe e você provavelmente nem percebeu.** `gerar_prologo_missao`
(`narrator.py:45`) gera local inicial, clima, nome e objetivo da missão e uma narrativa de
três parágrafos "in media res", conectada ao passado e à história que o jogador escreveu.
Ele é gravado como `historico_chat[0]` — e aparece na tela como **mais uma bolha de chat,
igual a todas as outras**. Todo o material está lá; falta o momento.

**O que fazer:**

- **Tela cheia antes do primeiro turno**, não uma bolha: retrato do herói, nome, raça e
  classe, o local e o clima, o texto do prólogo em ritmo de digitação, e um botão só —
  "Começar". Sai dali direto para o chat, com o prólogo já no histórico.
- **Ficha de identidade no topo**: uma linha que responde as três perguntas que você
  levantou — quem ele é, de onde veio, onde está. Você já tem os três campos
  (`background`, `objetivo`, `world_state.local`).
- **Reaproveite na retomada:** a mesma tela, mais curta, ao voltar num herói existente
  (é o "Anteriormente…" da lista de extras — os dois viraram o mesmo componente).

**Dois defeitos que este item precisa consertar junto, senão a abertura mente:**

1. **Persistir `historia_texto`** (P-4). Coluna nova em `Personagem` + migration. Hoje o
   texto mais pessoal da criação é usado uma vez e descartado — e é justamente o que deveria
   alimentar a tela de abertura, a memória de longo prazo e a retrospectiva de morte (C-4).
   Bônus: com ele gravado, dá para registrá-lo como o primeiro `EventoMemoria` do
   personagem, e o passado dele passa a poder voltar na busca híbrida no turno 40.
2. **Validar `local_inicial` contra `data/locations.json`** (P-5). Ou o prólogo escolhe entre
   os locais existentes (enum na saída, como já é feito com os monstros em
   `iniciar_combate`), ou o local proposto é criado no catálogo. Começar num lugar que a
   ferramenta `mover` não reconhece é a mesma classe de bug que a Etapa 3 resolveu no
   combate: o narrador inventando algo que o motor não sabe existir.

**Enquanto estiver aí:** o prólogo é o último lugar do sistema que ainda usa o modo JSON
antigo (`narrator.py:23` confessa isso). Se for mexer, é a hora de alinhá-lo ao tool calling
do ADR-0007. E ele roda **dentro** do `POST /create_character`, síncrono — o jogador espera
uma chamada completa ao modelo com a tela travada. Com a tela de abertura, esse tempo vira
tempo de leitura, o que é uma solução melhor que otimizar.

### B-8 — Dados explicados

Hoje o card mostra `d20(14) +2 = 16 vs CD 12 · SUCESSO`. O jogador vê o número, mas não vê
**de onde ele veio**: qual atributo foi testado, por que o bônus é +2, por que a CD é 12.

A informação existe no backend e se perde no caminho: o texto do evento diz "Teste de
destreza" (`tools.py:78`), mas `DadosRolagem` (`domain/eventos.py`) **não tem campo de
atributo** — e o card lê `DadosRolagem`, não o texto. O `RollCard` não tem como mostrar o
que nunca recebeu.

- Campos novos em `DadosRolagem`: `atributo`, `arma`, e um `partes_bonus` explícito —
  `[{"rotulo": "Destreza", "valor": 2}, {"rotulo": "Proficiência", "valor": 2}]`. O bônus de
  ataque hoje é modificador + proficiência somados num número só; separar é exatamente
  responder "por que +4?".
- `RollCard` passa a mostrar o rótulo ("TESTE DE DESTREZA", "ATAQUE COM CIMITARRA") e a
  decomposição. O componente `ui/tooltip.tsx` já existe — a conta detalhada pode viver ali
  para não poluir o card.
- Uma legenda do que é CD e CA, uma vez, na primeira aparição de cada.

Isto não é enfeite: é a mesma promessa da Etapa 7 ("o jogador vê que o mestre não trapaceia")
levada até o fim. Card que mostra um `+2` sem origem ainda pede confiança; card que mostra
`Destreza +2` prova.

### B-9 — A voz do mestre

**O texto não está descritivo por acaso: o sistema manda ele ser assim, em três lugares.**

1. **A bíblia obriga.** `data/biblia_mestre.txt` tem uma seção chamada `[O MOTOR SENSORIAL]`
   que diz, literalmente, que a cada cena o mestre "deve (obrigatoriamente) descrever pelo
   menos 3 sentidos" — visão, audição, olfato/tato.
2. **O prompt de sistema repete.** `montar_contexto` fecha pedindo "tom sombrio e sensorial
   (visão, som, cheiro — a bíblia acima exige isso)".
3. **E o juiz da Etapa 6 dá nota por isso.** A rubrica em `evals/judge.py:28` tem um eixo
   `qualidade_sensorial`: "a narrativa usa pelo menos 3 sentidos".

Ou seja: o modelo está obedecendo. Três sentidos obrigatórios por turno, com stakes ou sem,
viram parágrafo de enchimento — e enchimento constante é exatamente a sensação de preguiça
que você descreveu.

**A consequência que quase ninguém veria a tempo:** se você mudar só o prompt, **sua própria
avaliação vai acusar regressão**. O eixo `qualidade_sensorial` cai, a média cai, o baseline
do CI reclama, e o número vai dizer que ficou pior enquanto o jogo ficou melhor. A métrica
premia o defeito. Corrigir a rubrica faz parte do item, não é opcional — e essa história,
contada num post, vale mais que qualquer feature: *descobri que minha métrica estava
premiando exatamente o que incomodava o jogador.*

**Antes de escrever prompt: há uma decisão de direção aqui, e ela é sua.** A primeira linha
da bíblia diz "Você não é um autor de livros de fantasia. Você é uma Simulação de Realidade
Física e Social". Isso é uma recusa deliberada do épico — foi escolhida, não é descuido.
O que você está pedindo agora contradiz isso de frente.

A reconciliação que eu defendo: **manter a ética, trocar a voz.** Verossimilhança é sobre
*consequência* — o mundo não protege o jogador, o rei manda prender, a queda mata. Nada
disso exige prosa morna. Um texto pode ser implacável e elétrico ao mesmo tempo; o que a
bíblia confundiu foi "não ser condescendente" com "ser um relatório".

**O que muda, concretamente:**

- **Um detalhe sensorial escolhido, não três obrigatórios.** Trocar a cota por um critério:
  o detalhe entra quando *aumenta* a tensão, e fica de fora quando só ocupa espaço.
- **Teto de tamanho, que hoje não existe em lugar nenhum.** Algo como ~80 palavras em
  combate, ~150 fora dele. Limite de comprimento é o conserto de prosa mais confiável que
  existe — ele força escolha.
- **Ritmo variável.** Perigo pede frase curta. Exploração aguenta frase longa. Hoje todo
  turno tem o mesmo tamanho e a mesma forma, e a monotonia cansa mais que o excesso.
- **Terminar em movimento, nunca em cenário.** O último período de cada turno tem que ser
  algo acontecendo ou prestes a acontecer. Cena que termina em paisagem é cena que devolve
  o jogador ao teclado sem urgência.
- **Verbo antes de adjetivo**, e uma lista curta de anti-padrões proibidos ("o ar estava
  pesado", "um silêncio ensurdecedor", "você sente um arrepio") — banir o clichê nomeado
  funciona muito melhor que pedir "seja original".
- **Dois ou três exemplos curtos da voz desejada, dentro do prompt.** Este é o instrumento
  mais forte da lista, e de longe: modelo aprende voz por exemplo, não por adjetivo. Cinco
  linhas de exemplo valem mais que um parágrafo de instrução.
- **A rubrica do juiz muda junto:** `qualidade_sensorial` vira algo como `impacto_narrativo`
  (tensão, ritmo, gancho no fim), e o baseline é regerado na mesma sessão.
- **Não esqueça do guardrail:** `corrigir_narrativa` (`services/guardrail.py`) reescreve o
  texto quando acha contradição, e o reprompt dela não carrega nenhuma regra de estilo. Se
  ficar como está, toda correção devolve o tom antigo pela porta dos fundos.

**Como saber se funcionou** — e aqui você tem duas fontes, o que é raro: rodar o eval antes
e depois com a rubrica nova, e olhar a razão de 👍/👎 por narração, que já está gravada desde
a Etapa 9. Se as duas concordarem, a mudança é real. Se discordarem, a interessante é a
discordância.

> **Nota de prioridade:** este é o item de maior impacto por hora do backlog inteiro. É
> trabalho de prompt, bíblia e rubrica — nenhuma migration, nenhum componente novo — e ele
> muda a primeira impressão de **todo** turno que qualquer amigo vai ler. Se você quiser um
> ganho grande antes de mandar o link, é este, não o pixel art. Puxá-lo para a Etapa 10 no
> lugar de A-2 e A-5 é uma troca que eu faria.

---

## Etapa 12 — O jogo por baixo · ~60h · 6 semanas (dividida em 12a e 12b)

**Objetivo:** as regras sustentam uma partida de uma hora sem quebrar nem entediar.
É a etapa mais "portfólio" das três: quase tudo aqui vira número.

| # | Item | h | Métrica |
|---|---|---|---|
| C-1 | Simulador de balanceamento | 10 | taxa de vitória, turnos por combate, HP restante |
| C-2 | Economia de XP e bestiário por nível | 6 | tempo até o nível 2/3 |
| C-3 | Descanso curto e longo | 4 | mortes por atrito ↓ |
| C-8 | Aba de regras, gerada do motor | 6 | abandono no 1º turno ↓ (fica no bloco 12a) |
| C-4 | Retrospectiva de morte gerada por IA | 8 | taxa de "criar novo herói após morrer" |
| C-5 | Criação de personagem interativa | 10 | conclusão do funil de criação, tempo até o 1º turno |
| C-6 | Temperamento, dificuldade e estilo da campanha | 8 | retenção por perfil escolhido |
| C-7 | Companheiros: o herói não anda sozinho | 8 | turnos por sessão, retenção |

> **54h é etapa demais.** Cinco semanas sem entregar nada jogável é onde projeto morre. Ela
> pede uma divisão em duas, e a linha de corte natural é *regra* × *sensação*:
> **12a — o motor honesto** (C-1, C-2, C-3, C-8 · 26h): balanceamento, XP, descanso e a aba
> de regras gerada em cima deles. É quase tudo invisível na tela, mas é o que faz a partida
> de uma hora existir, e gera o relatório do post.
> **12b — a mesa** (C-4 a C-7 · 34h): retrospectiva, criação interativa, os três knobs e os
> companheiros. Tudo o que o jogador percebe.
> Se o semestre apertar, 12a sozinha já conserta o jogo; 12b é o que o torna memorável.
>
> *(O antigo C-6, "ações em botão", virou a Etapa 13 — o pedido de melhorar o combate
> cresceu o suficiente para não caber como um item.)*

### C-1 — Balancear com simulação, não com achismo

`Backend/evals/simulador.py`: roda N=10.000 combates *sem LLM nenhum* — só `rules_engine` e
`combat`, que já são puros e recebem `rng` injetável (foi para isso que a Etapa 3 separou o
juiz do narrador). Para cada par (nível do herói × encontro), reporta:

- taxa de vitória
- turnos até resolver
- HP médio restante na vitória
- taxa de teste de morte disparado

Alvos sugeridos, para ter contra o que ajustar: encontro comum do nível ≈ **85–90% de
vitória com ~50% de HP restante**; chefe ≈ **60%**. Saída em
`docs/relatorios/0002-balanceamento.md`, com a tabela antes e depois do ajuste. Este
relatório é conteúdo de post por si só — "balanceei meu RPG com 10 mil simulações" é uma
frase com número atrás.

### C-2 — A economia de XP (resolve P-1)

Três mudanças, todas baratas:

1. **Curva própria, encurtada.** A tabela do SRD pressupõe meses de campanha; seu jogo
   pressupõe uma sessão. Algo como `{1:0, 2:100, 3:300, 4:700, 5:1200}`. Isso é um desvio
   consciente do 5e — precisa entrar no README, na lista de desvios que já existe lá, e num
   ADR curto. Divergir da regra publicada é legítimo; divergir sem registrar é o que
   estraga o argumento da Etapa 6 (o golden dataset usa o 5e como referência externa).
2. **XP não-combate.** Ferramenta `concluir_objetivo(objetivo)` que concede XP por missão
   cumprida e descoberta. Sem isso, o jogador que resolve tudo conversando nunca sobe de
   nível — e o jogo pune exatamente o estilo de jogo que o seu narrador faz melhor.
3. **Bestiário por banda de nível.** Hoje são 5 monstros em 2 categorias (`Nivel_1` e
   `Chefe`). Chegar a ~15 em bandas 1–5 é edição de JSON, não código, e é pré-requisito do
   C-1 ter o que balancear.

### C-3 — Descanso (resolve P-2)

Ferramenta `descansar(tipo)`: **curto** gasta um dado de vida e recupera `1dX+CON`;
**longo** recupera tudo e só pode acontecer em local seguro, uma vez por "dia" narrativo.
Bloqueada durante combate, como `mover` já é. Sem isso não existe arco de partida — só
uma ladeira até a morte.

### C-8 — Aba de regras, gerada do motor

Uma aba que explica o sistema enxuto que o jogo usa: atributos e modificadores, CA, CD e a
escala de dificuldade, dado de vida e HP, iniciativa, ataque e dano, testes de morte, XP e
nível, descanso, e as ações táticas do D-3. Serve a três coisas ao mesmo tempo — onboarding
para o amigo que nunca jogou D&D, transparência do sistema (mesma família do `RollCard`), e
o lugar onde finalmente mora a lista do que ficou **fora** do 5e, que o PLANO_MESTRE §9.2
manda estar escrito "para não parecer omissão".

**A decisão que faz esse item valer ou apodrecer: a página é gerada, não escrita.**

Uma página de regras digitada à mão começa correta e mente em duas semanas — basta o C-2
mudar a curva de XP, o C-3 acrescentar descanso ou o D-3 criar "Investir". Escreva um
`GET /regras` que devolve os valores **do próprio motor**:

- limiares de XP e bônus de proficiência de `rules_engine.XP_POR_NIVEL` /
  `bonus_proficiencia`
- fórmula do modificador e regras de crítico/falha crítica de `resolver_ataque`
- catálogo de raças, classes e armas de `data/*.json` — inclusive as propriedades que já têm
  efeito real ("Sutil" usa o melhor entre Força e Destreza, "Munição" usa Destreza)
- escala de CD, que hoje só existe como texto na descrição da ferramenta `rolar_teste`
- as ações táticas e seus efeitos, quando o D-3 existir

Assim a aba não pode mentir: se o número mudou no motor, mudou na página. E isso é uma frase
boa de entrevista — *a documentação de regras do jogo é gerada do código que as executa*.

**Um cuidado que parece detalhe e não é:** a aba **não** pode ser a `biblia_mestre.txt`
servida na tela. A bíblia é a instrução do mestre, não o manual do jogador — ela contém
coisas como "não proteja o jogador de sua própria estupidez", que é direção de tom, não
regra. E servi-la seria vazar o prompt de sistema de propósito, justo com o vazamento de
prompt ainda em aberto no relatório da Etapa 6.

**Detalhe que dá um acabamento desproporcional ao custo:** tornar os termos clicáveis a
partir do jogo. `vs CD 15` no card de rolagem leva direto para a seção de dificuldade; o
nome da raça na ficha leva para os traços dela. Ajuda dentro do contexto vale muito mais que
uma aba que o jogador precisa lembrar de abrir.

**Por que no bloco 12a:** é exatamente quando as regras param de se mexer (curva de XP,
descanso e balanceamento acabaram de ser decididos). Se quiser antecipar, antecipe o
endpoint — a página cresce sozinha conforme o motor ganha regra.

### C-4 — A retrospectiva da morte

O item mais bonito da sua lista, e o que melhor mostra o sistema que você construiu: é a
memória da Etapa 5 sendo usada para algo que o jogador *sente*.

- `POST /jogo/{id}/epitafio`, chamado uma vez quando `resultado == "morte"`.
- Contexto do prompt: os eventos mais marcantes de `evento_memoria` (a busca híbrida já
  ordena por relevância), o `resumo_rolante`, e as estatísticas duras — turnos vividos,
  inimigos derrotados, ouro acumulado, nível, e **como morreu**.
- Saída em duas partes: uma retrospectiva em segunda pessoa e um **epitáfio de uma linha**
  para a lápide.
- **Grave o resultado** em `Personagem` (campo `epitafio`). Regenerar a cada visita custa
  dinheiro e, pior, dá uma memória diferente da mesma morte a cada vez.
- Métrica que vale a pena: quantos jogadores criam um novo herói *depois* de ver a
  retrospectiva, contra a taxa de hoje.

### C-5 — Criação de personagem interativa

- **Modo conceito:** o jogador escreve uma frase — "um anão exilado que odeia magia" — e o
  modelo **propõe** raça, classe, distribuição de atributos e background por tool call. O
  servidor revalida o point-buy como sempre (`domain/character.py`, ADR-0002); o jogador vê
  a proposta e pode ajustar tudo. É o mesmo padrão "o modelo propõe, o servidor decide" que
  já é a tese do projeto, agora aplicado à porta de entrada.
- **Rolagem animada** como alternativa ao point-buy: 4d6 descarta o menor, com os dados
  aparecendo na tela. É o momento mais divertido de criar ficha em mesa, e hoje ele é um
  formulário.
- **Três perguntas do destino:** mini-questionário que concede um traço de background. Dá
  personalidade sem inventar mecânica nova.

### C-6 — Temperamento, dificuldade e estilo da campanha

Três botões na criação (e editáveis depois, na ficha), cada um com três opções — não mais
que três, pelo motivo que está no fim desta seção:

| Botão | Opções | O que ele muda de verdade |
|---|---|---|
| **Temperamento do mestre** | Cruel · Justo · Generoso | só o tom da narração — uma seção no prompt de sistema |
| **Dificuldade** | História · Aventura · Brutal | CD, composição dos encontros, XP |
| **Estilo da campanha** | Exploração · Investigação · Guerra | que locais e monstros o prólogo e as cenas puxam |

**A regra que decide se este item ajuda ou estraga o projeto:** dificuldade muda as
**entradas** do juiz, nunca o resultado do dado. Concretamente — ela pode ajustar a CD que o
modelo propôs (um offset de ±2, aplicado no servidor e **visível no card**), o número e o
nível dos inimigos em `iniciar_combate`, e o XP concedido. Ela **não pode** somar um bônus
secreto na rolagem nem repetir um dado ruim.

O motivo não é purismo: você passou a Etapa 7 inteira provando ao jogador que o mestre não
trapaceia, e o `RollCard` é essa prova na tela. Um modificador oculto transforma o card numa
mentira educada, e derruba a única coisa que diferencia este projeto de um chat com tema de
RPG. Se a dificuldade muda a CD, o card mostra `vs CD 15 (Brutal +2)` — e aí ela é uma regra,
não um truque.

**Onde cada coisa mora:**

- Três colunas em `Personagem` + migration; enum validado no servidor, como raça e classe
  (`routers/character.py` já é o lugar onde o servidor decide).
- Temperamento e estilo entram em `narrator.montar_contexto` como uma seção curta. Estilo
  também entra no prólogo (B-7), que é onde ele mais aparece.
- Dificuldade entra em `services/tools.py` (offset de CD, XP) e em `services/combat.py`
  (quantos e quais inimigos) — no motor, não no prompt. Pedir "seja mais difícil" ao modelo
  produz dificuldade percebida, não dificuldade medida, e a Etapa 12 inteira é sobre a
  segunda.
- **Esta é a alavanca que o C-1 precisa.** O simulador roda os três níveis de dificuldade e
  mostra as três taxas de vitória — sem isso, "Brutal" é adjetivo; com isso, é um número.

**O custo escondido, e por isso "três opções, não cinco":** cada botão multiplica o espaço de
comportamento que a Etapa 6 avalia. 3×3×3 são 27 combinações, e você não vai escrever 27
casos golden. A saída é avaliar **um eixo por vez** — um caso por opção, com os outros dois
botões fixos no padrão — e declarar isso no ADR. Fingir cobertura completa aqui seria pior
que não ter os botões.

### C-7 — Companheiros: o herói não anda sozinho

RPG é jogo de mesa, de grupo — e hoje o jogador está sozinho contra o mundo, o que deixa a
partida solitária e sem ninguém para conversar. O pedido é certeiro. **Mas ele encosta na
decisão de escopo §9.3**, e vale separar em dois níveis, porque um é barato e o outro é uma
etapa inteira.

**Nível 1 — companheiro narrativo (é o que cabe aqui, ~8h).**

Um ou dois NPCs que acompanham o herói: comentam a cena, reagem ao que ele faz, discordam,
lembram do que aconteceu, opinam sobre a missão. Mecanicamente **não entram no combate**.

- Coluna `companheiros` em `Personagem` (nome, arquétipo, relação com o herói), criada no
  prólogo (B-7) — o "como você chegou aqui" ganha um "com quem".
- Entram em `montar_contexto` como uma seção própria, com instrução explícita de dar voz a
  eles em pelo menos uma fala por cena — senão o modelo os esquece em três turnos.
- A infraestrutura já existe e está subaproveitada: `reputacao_npcs` e
  `resumo.npcs_conhecidos` (Etapa 5) já rastreiam relação com NPC. Companheiro é um NPC com
  presença fixa na cena.
- **O companheiro é o melhor tutorial que existe.** "Podíamos tentar subir pela parede oeste"
  resolve a paralisia de tela em branco de dentro da ficção, sem caixa de ajuda. Se o
  jogador trava dois turnos seguidos, é o companheiro que sugere — não a interface.
- **Limite honesto para escrever no README:** o companheiro não toma dano, não rola dado e
  não pode morrer. Ele fala. Se a cena exige que ele se machuque, isso é narração, não
  estado. Melhor uma limitação declarada do que um aliado que "some" quando o combate começa.

**Nível 2 — aliado com ficha no combate (fora desta etapa, ~15h+ e um ADR).**

Aqui o motor muda de verdade: `CombatState` passa a ter aliados, `ordem_iniciativa` deixa de
tratar o herói como o único `-1`, `combat.turno_inimigos` precisa **escolher entre alvos** em
vez de sempre bater no herói, e o aliado precisa de turno próprio. É exatamente a
"complexidade de abstração de mesa com múltiplos jogadores" que o §9.3 recusou — e recusou
por um bom motivo: não move nenhuma métrica da tese.

**Recomendação:** faça o Nível 1 e meça. Se o feedback dos amigos disser que o companheiro
mudo em combate incomoda, aí o Nível 2 vira uma etapa própria, com ADR emendando o §9.3.
Decidir isso agora, sem o dado, é o tipo de aposta que a regra anti-escopo existe para evitar.

---

## Etapa 13 — O combate · ~32h · 3 semanas

**Objetivo:** o combate deixa de ser "digitar *eu ataco* várias vezes" e vira a parte do jogo
que dá vontade de contar depois.

### O que o combate é hoje, sendo honesto

A camada visual está boa: iniciativa real, alvo clicável, dano flutuante, barra de HP por
inimigo, cards de rolagem. O que está raso é **tudo o que o jogador pode decidir** — e isso
não é opinião, dá para listar:

- **O vocabulário tático tem um verbo.** As ferramentas disponíveis em combate são `atacar`
  e `usar_item`. Não existe esquivar, defender, investir, agarrar, empurrar. Também **não
  existe fugir** — nada em `services/combat.py` implementa retirada, então todo combate é
  até a morte de alguém. Um jogo em que a única decisão é "ataco de novo" não tem decisão.
- **Vantagem e desvantagem não existem no motor.** `resolver_ataque` rola **um** d20, ponto
  (`rules_engine.py:80`). É a mecânica central do 5e e a peça que faltando torna impossível
  implementar esquivar, cobertura, atacar caído, atacar cego, flanquear — todas viram
  "vantagem" ou "desvantagem" na regra real.
- **O bestiário promete táticas que ninguém executa.** `monsters.json` diz que o Lobo "ganha
  vantagem se tiver aliado perto", que o Goblin "ataca e foge (Ação Ardilosa)" e que o Kobold
  "foge se estiver sozinho". Nada disso roda: `_criar_inimigo` (`combat.py`) copia hp, ca e
  ataque, e **descarta o campo `comportamento`**. Os cinco monstros se comportam de forma
  idêntica — avançam e batem.
- **O momento mais tenso do jogo é invisível.** `CombatState` tem `sucessos_morte` e
  `falhas_morte` (os testes de morte, três a três), e `_resposta` (`game.py:37`) **não manda
  nenhum dos dois para o frontend**. O jogador caído a 0 PV está a duas falhas de perder o
  personagem e não vê contador nenhum. Isso é senso de perigo já implementado e jogado fora
  no último metro.

| # | Item | h | O que muda |
|---|---|---|---|
| D-1 | Vantagem e desvantagem no motor | 4 | pré-requisito de metade do resto |
| D-2 | Ação estruturada: o juiz antes do narrador | 8 | botão vira regra, não texto interpretado |
| D-3 | Vocabulário tático (esquivar, defender, investir, fugir) | 6 | passa a existir decisão |
| D-4 | Inimigos com comportamento de verdade | 4 | os cinco monstros deixam de ser o mesmo monstro |
| D-5 | Retratos e sprites de inimigo | 4 | (era o B-5) o perigo ganha rosto |
| D-6 | Senso de perigo | 6 | testes de morte visíveis, intenção telegrafada, a tela reagindo |

### D-1 — Vantagem e desvantagem

Rolar dois d20 e ficar com o melhor (vantagem) ou o pior (desvantagem). Em código é um
parâmetro em `resolver_ataque` e `resolver_teste_atributo` e umas dez linhas. Em consequência
é a base de tudo o que vem depois — e conserta, de quebra, a promessa quebrada do Lobo.

O card de rolagem precisa mostrar os **dois** dados (`d20(7) d20(18) → 18, vantagem`). Se o
sistema rola dois dados e mostra um, ele fica devendo exatamente a transparência que a Etapa
7 conquistou.

### D-2 — Ação estruturada: o juiz antes do narrador

**É a mudança de arquitetura desta etapa, e ela serve à tese do projeto.**

Hoje toda ação de combate faz o caminho longo: o jogador digita → o modelo interpreta → o
modelo *decide chamar* `atacar` → o motor resolve → o modelo narra. Isso tem três problemas
conhecidos, e o terceiro é o pior: **o modelo pode simplesmente não chamar a ferramenta**.

Com botão, o caminho inverte: o jogador clica "Esquivar" → o servidor **já sabe** qual regra
aplicar e resolve na hora, sem LLM → o narrador recebe o resultado pronto e só descreve.

O ganho é triplo, e vale escrever no ADR:

1. **Determinismo.** A ação escolhida por botão não depende de o modelo entender a frase nem
  de ele lembrar de chamar a ferramenta. A regra roda sempre.
2. **Velocidade.** Some o laço de tool calling (que pode dar até `agent_max_passos = 6` idas
   e voltas à Groq); sobra uma chamada só, para narrar. Isso conversa direto com o A-6.
3. **A tese, demonstrada.** "O juiz não precisa do narrador para funcionar" deixa de ser uma
   frase de arquitetura e vira algo que o jogador experimenta: o resultado aparece antes da
   prosa.

O campo de texto livre **continua existindo e continua sendo o principal** — é o que separa
este jogo de um menu de RPG de turno. Os botões cobrem as quatro ou cinco ações que se
repetem; a frase livre cobre tudo o que você não previu, pelo caminho de hoje.

### D-3 — Vocabulário tático

Um conjunto pequeno e rígido, que é o que "regras rígidas" quer dizer — cada botão tem um
efeito escrito, não uma intenção interpretada:

| Ação | Regra |
|---|---|
| **Atacar** | como hoje |
| **Investir** | −2 no acerto, +50% no dano — o botão de risco |
| **Esquivar** | ataques contra você têm desvantagem até seu próximo turno |
| **Defender** | +2 na CA até seu próximo turno |
| **Usar item** | abre o inventário e usa de verdade (hoje só o narrador consegue acionar) |
| **Fugir** | teste de Destreza contra a maior iniciativa inimiga; sucesso encerra o combate, falha custa um ataque livre de cada inimigo |

Fugir é o mais importante da lista, e não por diversão: **sem retirada, todo encontro mal
calibrado vira morte obrigatória**, e o jogador aprende que decisão não importa. É também o
que dá sentido ao C-1 — com fuga possível, "85% de vitória" passa a medir escolha, e não só
aritmética de dano.

### D-4 — Inimigos com comportamento

`Inimigo` (`domain/state.py`) ganha o campo `comportamento`, que hoje é lido do JSON e
descartado. Duas consequências:

- **No motor:** um punhado de táticas simples e determinísticas — o Kobold foge quando fica
  sozinho, o Lobo ataca com vantagem se outro lobo está vivo, o Goblin recua depois de bater.
  São `if`s, não IA. E cada um deles é uma promessa do bestiário sendo cumprida.
- **No prompt:** o comportamento entra na descrição da cena, para o narrador descrever o
  goblin recuando em vez de inventar bravura que a regra não tem.

### D-5 — Retratos e sprites

São cinco monstros. Cinco imagens resolvem o bestiário inteiro — e, se o bestiário crescer
para ~15 no C-2, são dez a mais, geradas no mesmo estilo de uma vez. Guardar em
`Frontend/public/assets/monstros/`, mesmo padrão de raças e classes. Sprite tremendo ao levar
dano, esmaecendo ao morrer.

### D-6 — Senso de perigo

- **Testes de morte visíveis.** Mandar `sucessos_morte`/`falhas_morte` no `_resposta` e
  desenhar três caveiras e três escudos preenchendo. É a informação mais tensa que o sistema
  produz e hoje ela não sai do backend. Item mais barato da etapa, maior retorno emocional.
- **Telegrafar a intenção.** Antes de o jogador agir, mostrar o que cada inimigo está prestes
  a fazer ("o Bugbear ergue a maça"). Vem do `comportamento` do D-4, é determinístico, e
  transforma o turno numa decisão informada em vez de um chute.
- **A tela reagindo:** vinheta vermelha pulsando abaixo de 30% de HP, tremida na tela ao
  levar crítico, o HUD de combate escurecendo o resto da interface.
- **Ameaça legível:** cada inimigo mostra o quanto machuca (`1d6+2` vira "perigoso" ou três
  caveirinhas), para o jogador escolher alvo com informação.
- **Silêncio antes do combate.** Um beat de música que corta ao entrar em combate faz mais
  pelo perigo do que qualquer efeito visual — depende do B-4.

**Pronto quando:** um amigo perde um combate, foge de outro, e consegue explicar depois por
que perdeu — sem falar "sei lá, a IA decidiu".

---

## Ideias novas que valem a pena, além da sua lista

| Ideia | Por que | h |
|---|---|---|
| **"Anteriormente…"** ao retomar um herói | `resumo_rolante` já existe; três linhas de recap antes do primeiro turno resolvem o "esqueci onde parei", que é o motivo real de abandono entre sessões | 3 |
| **Conquistas** | o motor de retenção mais barato que existe depois do XP; e você já grava todos os eventos necessários | 4 |
| **Página pública da tumba** (`/tumba/{slug}`) | o amigo compartilha a morte do herói e traz outro amigo. **Opt-in explícito** — a história contém texto que o jogador escreveu | 5 |
| **Painel das suas sessões** | você já grava `EventoTelemetria` e não tem como olhar. Sem isso, o teste com amigos gera dados que ninguém lê | 5 |
| **Tratamento visível de erro e lentidão** | quando a Groq demora ou devolve 429, o jogador precisa ver o mestre "pensando", não uma tela morta | 2 |

---

## Sala de espera — proposta para `BACKLOG.md`

Estas falham nas duas perguntas, ou custam desproporcionalmente. Ficam registradas para não
voltarem como ideia nova daqui a um mês:

| Ideia | Métrica? | Sentida? | Por que esperar |
|---|---|---|---|
| Arte pixel gerada para as 21 raças/classes | ❌ | ➖ | a Rota 1 do B-1 entrega a mesma sensação por um terço do custo |
| Geração de imagem da cena por turno | ❌ | ✅ | latência e custo por turno; volta a fazer sentido se o custo cair |
| Magias com slots, multiclasse, façanhas | ❌ | ➖ | já declarado fora do 5e implementado (PLANO_MESTRE §9.2) |
| Ranking entre jogadores | ❌ | ❌ | single-player (§9.3); ranking pede moderação e antifraude |

---

## Ordem sugerida e calendário

| Mês | Etapa | h | Marco |
|---|---|---|---|
| 1 | **10** | 31 | O link pode ser enviado — rápido, sem asteriscos, e o que os amigos sentirem volta para você |
| 2 | **11a** | 19 | Abre a página, tem endereço decente e parece um jogo |
| 2–3 | **11b** | 30 | Os momentos: abertura, música, morte, e **a voz do mestre** |
| 3 | **12a** | 26 | Aguenta uma hora de partida, e o jogador sabe as regras · 📣 Post 3 (o relatório de balanceamento) |
| 4 | **13** | 32 | O combate vira a melhor parte do jogo |
| 5 | **12b** | 34 | A mesa: companheiros, morte com retrospectiva, campanha do jeito do jogador |

~172h no total, ou ~17 semanas efetivas a 10h/semana. É mais que o triplo do primeiro rascunho
deste documento — o backlog cresceu junto com o uso real, que é exatamente o que devia
acontecer.

**Por que a 13 vem antes da 12b:** as duas são "sensação", mas o combate é onde o jogador
passa a maior parte do tempo, e a Etapa 13 depende do motor calibrado da 12a — enquanto a
12b (companheiros, retrospectiva) não depende de nenhuma das duas e pode esperar sem
bloquear nada.

**Se o tempo apertar:** A-1 e A-3 são o mínimo absoluto antes de enviar o link — um resolve
a porta de entrada, o outro impede que dez amigos animados virem uma conta de API. O resto
espera sem prejuízo.

**Documentos que cada etapa deve gerar** (a regra do documento, PLANO_MESTRE §7):

- Etapa 10 → `ADR-0016` (convidado e a conversão sem perder heróis) ·
  `docs/relatorios/0003-latencia.md` (p50/p95 antes e depois — o item A-6 não está pronto sem
  os dois números) · `Lição 11` (onde o tempo de um turno realmente vai) ·
  `docs/diario/0011-etapa-10.md`
- Etapa 11 → `ADR-0017` (a decisão de identidade visual e por que a Rota 1) ·
  `docs/diario/0012-etapa-11.md`
- Etapa 12a → `ADR-0018` (curva de XP própria: onde e por que divergimos do 5e) ·
  `docs/relatorios/0002-balanceamento.md` · `Lição 12` (balancear um jogo por simulação) ·
  `docs/diario/0013-etapa-12a.md`
- Etapa 13 → `ADR-0019` (ação estruturada: o juiz resolve antes de o narrador falar) ·
  `Lição 13` (o que muda quando o botão não passa pelo modelo) · `docs/diario/0014-etapa-13.md`
- Etapa 12b → `ADR-0020` (dificuldade muda as entradas do juiz, nunca o dado) ·
  `ADR-0021` (companheiros de Nível 1 e por que o Nível 2 continua fora do §9.3) ·
  `docs/diario/0015-etapa-12b.md`
