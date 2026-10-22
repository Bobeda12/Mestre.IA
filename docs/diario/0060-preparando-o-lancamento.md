# Preparando o lançamento: a revisão final antes de abrir

**Período:** 22/10/2026 · continuação do diário 0059

## O que eu queria saber

"Dá para lançar hoje? Falta algo? Tem algo errado?" Em vez de achar que estava tudo bem,
fiz uma revisão em três frentes: o que estava pendente nos documentos, o estado da produção
(Render e Vercel) e a saúde do código (testes, tipos, build).

## O que encontrei e o que fiz

1. **O código novo ainda não estava em produção.** A branch `feat/texto-livre-e-progressao`
   tem as Fases 1 a 4, mas não tinha sido mesclada em `main`. Não há migração de banco nova,
   então o risco do merge é baixo. (O merge depende de você.)
2. **A verificação automática estava vermelha.** O "linter" (que confere o estilo do código)
   reclamava de 17 linhas compridas e de 2 imports sem uso, e o mypy (que confere os tipos)
   de 3 pontos em `combat.py`. Nada disso muda o jogo, mas o CI (o robô que roda as checagens
   a cada envio) ia falhar. Corrigi: os 2 imports saíram, os 3 tipos foram arrumados
   (uma variável era reaproveitada com dois significados) e as linhas compridas receberam um
   aviso `noqa`, porque são textos de prompt e quebrá-las mudaria o texto que o modelo lê.
   Resultado: ruff e mypy limpos, 977 testes do backend passando, 86% de cobertura.
3. **O link do e-mail de confirmação levava a um login perdido.** Quando alguém confirmava o
   e-mail, o servidor gravava o cookie de sessão no endereço do Render, mas o jogo roda no
   endereço da Vercel. O navegador não leva um cookie de um endereço para o outro, e a pessoa
   voltava deslogada. É o mesmo problema que o login do Google já tinha resolvido, passando
   pelo "proxy" da Vercel (um atalho que faz a Vercel repassar o pedido ao Render, para o
   navegador achar que é tudo um lugar só). Apontei `CONFIRMACAO_EMAIL_URL` no `render.yaml`
   para o endereço da Vercel. **Atenção:** o Render não reaplica sozinho um valor que já existe,
   então é preciso trocar também no painel.
4. **Tela branca em caso de erro.** Qualquer falha de desenho na tela deixava tudo em branco.
   Criei `ErrorBoundary.tsx`: agora aparece "Algo deu errado", com botão de recarregar. O
   progresso fica no servidor, então recarregar é seguro.
5. **Faltavam privacidade e termos.** O jogo guarda e-mail e senha e manda o texto das jogadas
   ao Google. Criei a página `/privacidade`, em linguagem simples, descrevendo só o que o
   código realmente faz, e um aceite obrigatório ao criar conta. O e-mail de contato para
   pedidos de dados vem da variável `VITE_EMAIL_CONTATO` (Vercel), para não gravar um e-mail
   pessoal no código. Sem ela, a seção de contato some.

## O que continua de pé (não bloqueia)

- A cota gratuita do Gemini sustenta uns 185 turnos por dia, ou seja, poucos jogadores ativos.
  A tela de "Cota do servidor esgotada" já existe.
- O Render grátis dorme: o primeiro acesso demora de 30 a 60 segundos. Um ping de uptime em
  `/health` a cada 5 a 10 minutos resolve sem código.
- Sem Sentry (rastreio de erros), sem teste ao vivo de chefe, aliado e loja encantada.
- O lint do frontend segue com 17 erros antigos, tolerados no CI.

## Como conferir

`uv run ruff check .`, `uv run mypy app evals` e `uv run pytest` no `Backend/`; `npm run build`
no `Frontend/`. Falta o passo que só dá para fazer em produção: criar uma conta de verdade e
clicar no link do e-mail.
