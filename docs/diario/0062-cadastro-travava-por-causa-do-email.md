# O cadastro travava: o Render grátis não deixa mandar e-mail

**Período:** 22/10/2026 · continuação do diário 0061

## O que você viu

Ao criar uma conta, a tela ficava carregando para sempre.

## A causa

Quando alguém cria conta, o servidor manda um e-mail de confirmação. Ele fazia isso pelo
Gmail usando SMTP (o "protocolo antigo" de e-mail, que usa as portas 25, 465 ou 587). Só que
desde 26/09/2025 o **Render grátis bloqueia essas portas**: a conexão nunca completa. E o
código não tinha tempo limite, então ficava esperando para sempre. Medi em produção: o
cadastro não respondia em 45 segundos, enquanto o login de convidado respondia em menos de 1.

## O que mudou

1. **Envio pela API do Gmail.** Em vez do SMTP, o servidor pede ao Gmail, por HTTPS (a mesma
   "porta" de qualquer site, que o Render não bloqueia), para mandar o e-mail. Sai da sua
   própria conta Gmail, então a entrega continua boa e a confirmação de e-mail continua
   obrigatória. Reaproveita o mesmo cadastro do Google que já faz o login funcionar.
2. **Tempo limite de 15 segundos em tudo.** Se algo travar de novo, a pessoa recebe "Não deu
   para enviar o e-mail de confirmação agora. Tente de novo em instantes." Nunca mais
   carregamento infinito.
3. A ordem de tentativa é: API do Gmail, depois SMTP, depois Resend. Sem nenhum configurado,
   o link só aparece no log (útil no computador local).

## O que falta para funcionar (é com você, ~10 minutos)

Gerar uma "chave de renovação" (refresh token) que autoriza o servidor a mandar e-mail pela
sua conta. É feito uma vez.

1. **Google Cloud Console** (o mesmo projeto do login com Google):
   - APIs e serviços, Biblioteca, procure **Gmail API** e clique em Ativar.
   - Tela de consentimento OAuth: clique em **Publicar app** (o status tem que ser "Em
     produção"). Em "Testing" a chave morre em 7 dias.
   - Credenciais, abra o cliente OAuth e, em "URIs de redirecionamento autorizados",
     adicione `https://developers.google.com/oauthplayground`.
2. **OAuth Playground** (developers.google.com/oauthplayground):
   - Engrenagem no canto, marque **Use your own OAuth credentials** e cole o Client ID e o
     Client Secret (os mesmos do `GOOGLE_CLIENT_ID` e `GOOGLE_CLIENT_SECRET` do Render).
   - No Passo 1, digite no campo de escopo `https://www.googleapis.com/auth/gmail.send` e
     clique em Authorize APIs. Entre com o Gmail que vai ser o remetente. Aparece "app não
     verificado": é seu, clique em Avançado e continue.
   - No Passo 2, clique em Exchange authorization code for tokens e copie o **Refresh token**.
3. **Render**, em Environment:
   - `GMAIL_REFRESH_TOKEN`: o token copiado.
   - `GMAIL_REMETENTE`: o endereço Gmail que você usou no passo anterior.

Não cole o token em conversas nem no código: ele manda e-mail em seu nome.

## Limites e riscos

- O Gmail comum envia até uns 500 e-mails por dia, de sobra para este jogo.
- Se você republicar o app no Google ou revogar o acesso, a chave deixa de valer e o
  cadastro volta a mostrar a mensagem de erro; é só gerar outra.
- Se o app continuar em "Testing" ao gerar a chave, ela expira em 7 dias.

## Como conferir

`uv run pytest` no `Backend/` (979 testes, 2 novos: o envio pela API e a falha que vira
mensagem clara). Em produção: criar uma conta com um e-mail seu e ver o e-mail chegar.
