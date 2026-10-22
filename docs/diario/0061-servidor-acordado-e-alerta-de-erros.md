# Servidor acordado e alerta de erros

**Período:** 22/10/2026 · continuação do diário 0060

## Os dois problemas

1. **O servidor dormia.** O Render grátis desliga o backend depois de uns 15 minutos sem
   ninguém usar. O primeiro jogador do dia esperava de 30 a 60 segundos olhando uma tela
   parada.
2. **Eu não saberia se algo quebrasse.** O único jeito de descobrir um erro era abrir o log
   do Render e procurar.

## O que mudou

1. **Ping a cada 10 minutos.** O arquivo `.github/workflows/manter-acordado.yml` pede ao
   GitHub para chamar `/health` do backend de 10 em 10 minutos. Chamar o servidor o mantém
   acordado. É de graça porque o repositório é público, e não precisa de conta em outro
   serviço. O `/health` não consulta o banco, então o Neon continua livre para dormir.
   **Limite:** o GitHub às vezes atrasa essas tarefas agendadas, então de vez em quando o
   servidor ainda pode dormir. Um monitor externo (UptimeRobot, a cada 5 minutos) é mais
   firme, se isso incomodar.
2. **Sentry, um serviço que avisa de erros.** O backend (`app/infra/erros.py`) e o frontend
   (`src/lib/alertaDeErros.ts`) enviam ao Sentry os erros que ninguém tratou. Só liga quando
   existe a chave (`SENTRY_DSN` no Render e `VITE_SENTRY_DSN` na Vercel); sem ela, não faz
   nada, igual ao Langfuse.
3. **O texto do jogador não vai junto.** O erro sai sem cookies, sem IP e sem o corpo do
   pedido, que é onde está o que o jogador escreveu. O pacote do Sentry no navegador fica num
   arquivo à parte, baixado só quando a chave existe.
4. **A página de privacidade** passa a citar o Sentry, mas só quando ele estiver ligado.

## O que falta para ligar (é com você)

1. Criar conta grátis em sentry.io e dois projetos: um Python (FastAPI) e um React.
2. Colar o DSN do projeto Python em `SENTRY_DSN` no painel do Render.
3. Colar o DSN do projeto React em `VITE_SENTRY_DSN` na Vercel e fazer um Redeploy.

## Como conferir

`uv run pytest` no `Backend/` (979 testes, 2 novos para o Sentry) e `npm run build` no
`Frontend/`. O ping aparece na aba Actions do GitHub, no fluxo "manter-acordado"; dá para
rodá-lo na hora pelo botão "Run workflow".
