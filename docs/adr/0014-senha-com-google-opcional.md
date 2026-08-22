# ADR-0014 — Login por senha (PBKDF2) com Google OAuth opcional; cookie de sessão assinado à mão

**Data:** 21–22/08/2026
**Status:** Aceito
**Etapa:** 8
**Supersede:** —

---

## Contexto

O schema já tem `usuario (1:N) personagem` desde a Etapa 2 (ADR-0005) — mas até agora todo personagem pertencia a um `USUARIO_LOCAL_ID = 1` fixo, criado no `lifespan` da app. Não existia login, e a lista de heróis da tela inicial vinha do `localStorage` do navegador (`Home.tsx`), não do servidor.

**Nota sobre o processo:** a primeira versão desta etapa implementou login por e-mail mágico (link de uso único, sem senha), seguindo o que `PLANO_MESTRE.md` §4.4 já previa: *"autenticação sem senha é justamente o caso em que rolar o próprio é defensável — não há hash de senha a errar."* Ao revisar a decisão com o usuário, ele preferiu o padrão mais familiar (senha + login social), por ser o que a maioria dos jogadores espera de um app de conta única. Como o ADR ainda não tinha sido commitado, a decisão foi revisada aqui, não superseded por um ADR novo — o histórico da mudança fica no diário desta etapa, não numa cadeia de ADRs.

## Decisão

**Login por e-mail e senha, com Google como opção adicional.** Um `Usuario` pode ter `senha_hash`, `google_sub`, ou os dois — nunca nenhum dos dois.

- **Senha**: `PBKDF2-HMAC-SHA256` com salt aleatório de 16 bytes e 260.000 iterações (`services/auth.py:hash_senha`/`verificar_senha`), formato auto-descritivo (`pbkdf2_sha256$<iterações>$<salt>$<hash>`) — não `bcrypt`/`argon2` (a escolha padrão da indústria hoje) porque não havia acesso à rede na sessão que implementou isto, para instalar qualquer dependência nova. PBKDF2 é aprovado pelo NIST (SP 800-132) e já vem na `hashlib` da stdlib do Python — funcional e defensável, mas com uma ressalva registrada em "Como saber que erramos".
- **Google OAuth**: *authorization code flow* padrão. `GET /auth/google/iniciar` redireciona para o Google com um `state` aleatório (guardado num cookie `httpOnly` de 10 minutos — defesa contra CSRF: sem isso, alguém poderia mandar a vítima direto para `/auth/google/callback` com um `code` da própria conta do atacante, "logando" a vítima na conta errada). `GET /auth/google/callback` troca o `code` por um `access_token`, e usa esse token para perguntar ao **próprio Google** quem é a conta (`GET .../oauth2/v3/userinfo`) — o código nunca decodifica nem valida o `id_token` (JWT) localmente. Perguntar à API do Google via HTTPS já é a fonte da verdade, e evita reimplementar verificação de assinatura RS256 e busca de chaves públicas (JWKS) à mão, que é onde a maioria das implementações caseiras de "verificar JWT do Google" erra.
- **Sem `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET` configurados** (não dá para criar essas credenciais por conta própria — exigem uma conta no Google Cloud Console), o botão "Entrar com Google" simplesmente não aparece no front (`GET /auth/opcoes` devolve `{google_disponivel: false}`), em vez de existir e quebrar no meio do fluxo.
- **Cookie de sessão**: inalterado desde a primeira versão — `httpOnly`, `SameSite=Lax`, 30 dias, HMAC-SHA256 assinado à mão (`_assinar`/`_verificar`, payload em base64url + assinatura comparada em tempo constante com `hmac.compare_digest`). O mecanismo de sessão não depende de como o login aconteceu.

**Autorização por recurso** (inalterada da primeira versão): toda rota que lê ou muda um personagem confere `personagem.usuario_id == current_user.id`, devolvendo **403** — não um 404 disfarçado — quando não bate. Defesa contra IDOR, coberta por teste com dois usuários reais.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| E-mail mágico (versão original desta etapa) | zero senha para vazar/hashear errado; ~150 linhas | menos familiar para quem espera o padrão senha+Google de qualquer app; depende de latência de e-mail em todo login (mitigado pelo cookie de 30 dias, mas ainda presente no primeiro acesso) | o usuário preferiu explicitamente o padrão mais reconhecível — ver "Contexto" |
| `bcrypt`/`argon2` para hash de senha | padrão atual da indústria, desenhado especificamente contra ataque em hardware dedicado (GPU/ASIC) | não instalável nesta sessão (sem rede) | PBKDF2 (stdlib, sem dependência nova) cobre a mesma garantia central — não é possível reverter o hash, e força bruta exige testar senha por senha, uma a uma — só é mais lento contra hardware especializado; ver "Como saber que erramos" |
| Validar `id_token` do Google localmente (decodificar o JWT, verificar assinatura RS256 contra as chaves públicas do Google) | evita uma chamada de rede extra (`userinfo`) | exige biblioteca de JWT + busca/cache das chaves JWKS do Google, e refazer a verificação de assinatura e expiração à mão é justamente onde implementações caseiras de OAuth mais erram | chamar `userinfo` com o `access_token` é mais simples, mais curto, e desloca a responsabilidade de validação para o próprio Google — o preço é uma chamada HTTP a mais por login, irrelevante na escala deste projeto |
| Serviço de auth gerenciado (Clerk, Auth0, Supabase Auth) | pronto, testado em produção, já resolve senha + OAuth de vários provedores | mais uma conta, mais um SDK no front, mais um provedor no diagrama | ainda seria mais peso do que o problema pede — `PLANO_MESTRE.md` §4.4 já registra essa recusa; o custo de rolar por conta própria não mudou ao trocar de e-mail mágico para senha+Google |

## Consequências

**Ganhamos:**
- Padrão de login reconhecível — o jogador não precisa aprender um fluxo novo.
- Login com Google funciona sem o jogador nunca digitar senha, quando configurado; sem ele, cai graciosamente para e-mail+senha.
- `localStorage` continua fora de cena para qualquer coisa que importe — heróis e sessão seguem a pessoa entre navegadores, igual à primeira versão.
- IDOR continua coberto por teste automatizado com dois usuários reais — a troca de mecanismo de login não tocou nessa parte.
- **O achado ao vivo da primeira versão continua válido e foi reaproveitado**: `localhost` e `127.0.0.1` são sites diferentes para `SameSite`, e o cookie de sessão (inalterado) ainda depende de alinhar `VITE_API_URL` em `localhost`. Ver Lição 09.

**Pagamos:**
- **PBKDF2 em vez de `bcrypt`/`argon2`** — funcionalmente correto (NIST-aprovado, stdlib), mas sem o custo de memória (`argon2`) ou o ajuste de fator de trabalho mais granular que as bibliotecas dedicadas oferecem. Reavaliar se a rede permitir instalar uma dependência nova antes de um deploy real.
- **Login social só cobre Google** — sem GitHub, sem Apple. Suficiente para o escopo do projeto (não é um produto B2B nem mobile-first), mas registrado como limite deliberado, não esquecimento.
- Uma conta criada só por Google não tem senha — se um dia o jogador quiser "logar sem o Google", precisaria de um fluxo de "definir senha" que hoje não existe.
- Nenhuma forma de revogar **uma** sessão específica sem derrubar todas — mesma limitação da primeira versão, aceitável na escala de um jogador por conta.

**Fica em aberto:**
- Rate limit em `/auth/login`/`/auth/registrar` — hoje nada impede tentativas repetidas de senha para o mesmo e-mail. Sem rate limit, é uma porta aberta para força bruta online (diferente de força bruta offline contra o hash, que o PBKDF2 já mitiga). Cabe na Etapa 9, junto com rate limit geral.
- `SESSION_SECRET` tem um valor de desenvolvimento hardcoded — precisa ser sobrescrito por variável de ambiente antes de qualquer deploy real.

## Como saber que erramos

Se o PBKDF2 (em vez de `bcrypt`/`argon2`) virar fonte de um incidente real — por exemplo, um vazamento de banco seguido de senhas quebradas por força bruta em hardware dedicado numa velocidade preocupante — é sinal de migrar para uma biblioteca dedicada assim que a rede permitir, com uma migração de formato de hash que reconhece o prefixo `pbkdf2_sha256$` e converte no próximo login bem-sucedido (padrão já usado por frameworks como o Django ao trocar de algoritmo de hash).

## Referências

- [ADR-0005](0005-usuario-personagem-antes-do-login.md) — o schema `usuario (1:N) personagem` que esta etapa autentica de verdade.
- `PLANO_MESTRE.md`, Etapa 8 e §4.4 — o escopo original.
- [OWASP — Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) — PBKDF2 como opção aceitável quando `bcrypt`/`argon2` não estão disponíveis.
- [Google Identity — OAuth 2.0 for Web Server Applications](https://developers.google.com/identity/protocols/oauth2/web-server) — o *authorization code flow* implementado em `services/auth.py`.
- [OWASP — Session Management Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Session_Management_Cheat_Sheet.html) — `httpOnly`/`SameSite` como defesa contra roubo de sessão via XSS/CSRF.
- Lição 09 — sessão, cookie e token por dentro, incluindo a pegadinha `localhost` × `127.0.0.1`.
