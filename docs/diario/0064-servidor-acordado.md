# Servidor acordado: um ping a cada 10 minutos

**Período:** 22/10/2026 · continuação do diário 0063

## O problema

O Render grátis desliga o backend depois de uns 15 minutos sem ninguém usar. O primeiro
jogador do dia esperava de 30 a 60 segundos olhando uma tela parada, e com o login de
convidado isso parecia um site quebrado.

## O que mudou

O arquivo `.github/workflows/manter-acordado.yml` pede ao GitHub para chamar `/health` do
backend de 10 em 10 minutos. Receber um pedido mantém o servidor acordado. É de graça porque o
repositório é público, e não precisa de conta em outro serviço. O `/health` não consulta o
banco, então o Neon continua livre para dormir.

## Limites

- O GitHub às vezes atrasa essas tarefas agendadas em horários de pico, então de vez em
  quando o servidor ainda pode dormir. Um monitor externo (UptimeRobot, a cada 5 minutos) é
  mais firme, se isso incomodar.
- O agendamento só vale a partir da branch `main`. Para testar na hora, use o botão "Run
  workflow" na aba Actions.
- O GitHub desliga tarefas agendadas se o repositório ficar 60 dias sem nenhuma atividade.

## Sobre o Sentry

Uma versão anterior deste trabalho (PR #2) trazia também o Sentry, um serviço de alerta de
erros. Decidi não usá-lo agora: exige criar conta e configurar chaves, e para um protótipo o
log do Render basta. O código dele não entrou.
