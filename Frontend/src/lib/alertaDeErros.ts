// Alerta de erros do navegador (Sentry). Sem VITE_SENTRY_DSN não faz nada e o
// pacote nem é baixado: o `import()` dinâmico vira um arquivo à parte.
export const ALERTA_DE_ERROS_ATIVO = Boolean(import.meta.env.VITE_SENTRY_DSN);

export function iniciarAlertaDeErros() {
  if (!ALERTA_DE_ERROS_ATIVO) return;
  import('@sentry/react')
    .then((Sentry) => {
      Sentry.init({
        dsn: import.meta.env.VITE_SENTRY_DSN as string,
        environment: import.meta.env.MODE,
        // O texto das jogadas é privado: nada de IP, cookies nem replays.
        sendDefaultPii: false,
        tracesSampleRate: 0,
      });
    })
    .catch(() => {
      // Falhar em avisar do erro nunca pode virar um erro novo para o jogador.
    });
}

export function reportarErro(erro: Error) {
  if (!ALERTA_DE_ERROS_ATIVO) return;
  import('@sentry/react')
    .then((Sentry) => Sentry.captureException(erro))
    .catch(() => {});
}
