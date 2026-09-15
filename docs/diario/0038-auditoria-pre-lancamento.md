# Auditoria pré-lançamento: revisando a Fase 1 antes de lançar

**Período:** 15/09/2026 · sessão dedicada a revisar o trabalho em andamento da Fase 1
("Mundo Vivo": economia, instalações, organizações, projetos) antes de integrá-lo

## O que aconteceu

Antes de considerar o jogo pronto para um lançamento de verdade, pedi uma passagem
completa: achar bugs, riscos de segurança e melhorias claras em tudo que ainda estava em
andamento e não commitado — a Fase 1 do plano "jogo completo", que ainda não tinha
passado por uma revisão de conjunto. Três buscas em paralelo (backend, frontend,
operação/infraestrutura) leram o código de verdade, rodaram a suíte de testes real e
reproduziram medições ao vivo, em vez de só ler e opinar. Os achados foram organizados em
três níveis, e ficou combinado corrigir todos nesta rodada.

## O que foi corrigido

**Bugs de correção e segurança:**
- Nove ferramentas novas (despachar remessa, propor melhoria, registrar organização,
  mobilizar organização, planejar projeto, registrar avanço, propor e cumprir acordo,
  apresentar percepções) podiam ficar disponíveis para o narrador **durante um combate**,
  se o texto do jogador colidisse por acaso com uma palavra-gatilho (ex. uma frase de
  combate que mencionasse "organização"). Quatro delas nem tinham a segunda linha de
  defesa (a checagem interna "não faça isso em combate") que as outras já tinham. Corrigido
  nos dois níveis — ver [ADR-0037](../adr/0037-auditoria-pre-lancamento-mundo-vivo.md)
  para o porquê da dupla guarda.
- Quatro rotas que chamam o modelo de IA (criar personagem, exportar crônica, o oráculo de
  origem em duas etapas, validar chave própria) não tinham nenhum limite de uso. Como a
  chave gratuita da Groq é compartilhada entre todos os jogadores, uma pessoa martelando
  qualquer uma dessas rotas podia esgotar a cota do dia para todo mundo — o mesmo risco
  que já era tratado em `/chat` e `/game/action`, só que essas quatro tinham ficado de
  fora. Agora todas têm limite por minuto.
- O cookie de sessão não carregava a flag `Secure`. Em produção o site já roda inteiro em
  HTTPS, então não era explorável na prática, mas é uma correção de uma linha que vale
  fazer de qualquer forma.
- Quando uma ferramenta quebrava por um erro interno, o texto cru da exceção Python
  voltava para o contexto do modelo — e podia, em teoria, aparecer parafraseado na
  narrativa do jogo. Agora o erro real só é registrado no log do servidor; o modelo recebe
  uma mensagem genérica.

**Melhorias de experiência (mobile e dados do jogador):**
- No celular, quando a aba "Jornada" está aberta, ela cobre o resto da tela — então se uma
  ação nova (inaugurar uma melhoria, aceitar um acordo) falhasse, o aviso de erro aparecia
  atrás dessa gaveta e o jogador não via nada. Agora o erro e o aviso de "resolvendo sua
  ação" aparecem dentro da própria aba também.
- Um card de sugestão desabilitado (enquanto uma ação está sendo resolvida) continuava
  brilhando como se estivesse clicável. Agora fica visivelmente apagado.
- O campo "o que eu quero construir" (ambição do jogador) era limpo assim que o botão era
  clicado, mesmo se o envio falhasse — perdendo até 500 caracteres digitados sem chance de
  recuperar. Agora só limpa quando o projeto realmente nasce.
- A seção "Lugares que você transformou" simplesmente desaparecia quando vazia, sem
  explicar que ela existe. Agora mostra uma frase dizendo que ainda não há nada ali, como
  as outras seções já fazem.

**Testes que faltavam:**
- Um teste de regressão específico para o bug de combate acima (para nunca mais voltar
  silenciosamente).
- Um teste que mede o orçamento de tokens de um turno realista com vários assuntos ao
  mesmo tempo, não só o caso mais simples — a mesma classe de problema que já tinha
  quebrado em produção uma vez (diário 0026).
- Testes novos para três componentes de tela que não tinham nenhum: o card de
  relacionamento (hábito e voz do NPC), o balcão do mercador (item esgotado desabilita a
  compra) e o painel "sinais da cena". Mais casos de sucesso para os cliques de
  "inaugurar" e "aceitar acordo", que só tinham o caminho de erro coberto antes.

## O que decidi não mexer agora

- **Reduzir o teto local de tokens do turno.** A conta mostrou que apertar esse número o
  suficiente para fechar a lacuna teórica quebraria ~20 testes que usam o conjunto
  completo de ferramentas por conveniência (sem simular o filtro real de produção), sem
  trazer proteção proporcional — o risco de verdade está em quantas ferramentas um turno
  ativa ao mesmo tempo, não no teto absoluto. Detalhe da decisão no
  [ADR-0037](../adr/0037-auditoria-pre-lancamento-mundo-vivo.md).
- **Rastreamento de erros em produção (algo como Sentry), o "acordar devagar" do servidor
  gratuito depois de ficar inativo, e uma nota sobre o `docker-compose` local.** São
  reais, mas exigem decisões de ferramenta/custo que não são "corrigir um bug" — viraram
  itens novos em `docs/backlog-pos-lancamento.md`.

## Como testei

- Backend: suíte inteira (674 testes, incluindo os novos), `ruff check` e `mypy` limpos.
- Frontend: suíte inteira (80 testes, incluindo os novos), `npm run build` (checagem de
  tipos + build de produção) limpo. `npm run lint` tem débito pré-existente, não
  relacionado a esta auditoria, registrado como pendência separada (ver abaixo) — não foi
  criado nem aumentado nesta rodada.
- Não foi feito um teste ao vivo no navegador com backend real (exigiria banco de dados,
  autenticação e uma chave de LLM configurada, fora do que esta sessão conseguia montar) —
  a confiança desta rodada vem da suíte automatizada e da leitura direta do código, não de
  clicar no app rodando.
- CI ganhou um job novo para o frontend (build, testes, lint informativo) — antes só o
  backend tinha esse gate; o frontend só era checado pelo build da Vercel, depois do
  deploy, sem bloquear PR.

## O que ficou registrado para depois

- `npm run lint` tem 17 erros pré-existentes em 7 arquivos (a maioria em `sfx.ts` e
  `trilha.ts`, sobre acessar `ref.current` durante o render — provavelmente uma regra
  nova/mais estrita de uma versão recente do `eslint-plugin-react-hooks`). Não é desta
  auditoria, mas como o job de CI novo já roda lint, ficou visível: por ora o passo não
  derruba o build (`continue-on-error`), até alguém revisar esses 7 arquivos com calma.
- Todos os outros itens "fora de escopo" desta auditoria (rastreamento de erros, cold
  start, docker-compose) estão em `docs/backlog-pos-lancamento.md`.
