# ADR-0031 — Login devolve um motivo distinto (senha errada / pendente de confirmação / conta não encontrada / conta só-Google), abrindo mão da anti-enumeração original

**Data:** 29/08/2026
**Status:** Aceito
**Etapa:** 15
**Supersede:** —

---

## Contexto

Desde a revisão "registro sem estado" (commit `827ecfc`, sem ADR próprio até este), nenhum `Usuario` é gravado no banco até o clique no link de confirmação — e-mail e hash da senha viajam só dentro do token HMAC assinado, mandado por e-mail (`Backend/app/services/auth.py`, bloco "Registro sem estado").

Isso criou um caso de UX sem tratamento: se alguém tenta logar antes de clicar no link, `POST /auth/login` (`Backend/app/routers/auth.py`, antes desta revisão) não encontrava linha nenhuma em `Usuario` e devolvia `401 "E-mail ou senha incorretos."` — a mesma mensagem usada, de propósito, para senha errada e para e-mail nunca cadastrado (comentário removido nesta revisão: *"Mensagem genérica em qualquer um dos três casos... não é este endpoint que revela qual dos três aconteceu"*, anti-enumeração de contas). Sem diferenciação nenhuma, quem só esqueceu de confirmar o e-mail não tinha como saber disso — e não existia caminho nenhum, a partir da tela de login, para reenviar a confirmação (o reenvio só existia dentro da mesma aba, logo após o cadastro, em `ConfirmeEmail.tsx`).

## Decisão

`POST /auth/login` passa a devolver 4 motivos distintos, ao lado da mensagem (`ErroLogin`, `Backend/app/routers/auth.py`, com handler dedicado em `Backend/app/main.py`):

- `senha_incorreta` — conta confirmada existe, senha não bate.
- `pendente_confirmacao` — existe um `RegistroPendente` (tabela nova) recente para esse e-mail.
- `conta_nao_encontrada` — esse e-mail nunca foi usado para registro nenhum, ou o pendente venceu (mais de 24h, mesmo TTL do link de confirmação).
- `conta_google` — a conta existe e é só-Google (`senha_hash is None`); sugere o botão "Entrar com Google".

Para o motivo `pendente_confirmacao` existir, `/auth/registrar` e `/auth/reivindicar` passam a espelhar o convite (e-mail + hash da senha + `usuario_id`, quando aplicável) numa tabela nova, `RegistroPendente`, complementar ao token — o token continua sendo o que autentica o clique no link; a tabela só serve para o login *saber* que um pendente existe. Sem job de limpeza: uma linha mais velha que 24h é tratada como inexistente nas checagens (login e novo registro), a linha órfã continua no banco.

No frontend, `Login.tsx` lê o `motivo` e mostra a ação certa: reenviar confirmação, criar conta, ou entrar com Google — em vez de um texto único.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Manter a mensagem genérica, só reescrever o texto para mencionar a possibilidade de e-mail não confirmado (sem mudança de backend) | zero risco de enumeração; mudança mínima | usuário continua sem saber qual dos três casos é o dele; sem sinal algum para oferecer reenvio automaticamente | resolve só a superfície do problema — a pergunta "por que não consigo entrar" continua sem resposta |
| Heurística só no frontend (oferecer sempre um botão "reenviar" em qualquer erro de login, sem o backend confirmar que existe pendente) | não muda contrato da API | ou o botão aparece sempre (ruído, inclusive para senha errada) ou nunca (não resolve nada); e-mail nunca cadastrado dispararia reenvio inútil (`/auth/registrar` responde 200 do mesmo jeito, criando um pendente para um e-mail que o dono nunca digitou de propósito) | sem o backend saber a diferença entre "nunca registrado" e "pendente", o frontend só pode adivinhar |
| Guardar a senha_hash pendente só em cache in-memory/Redis, sem tabela nova | evitaria migração + linha órfã permanente | projeto não tem Redis nem cache compartilhado hoje (deploy é Fly/Render + Neon — ver ADR-0015/0022); adicionar uma peça de infra nova só para isto pesaria mais que o problema pede | mesmo raciocínio do ADR-0014 (não instalar peça nova por conveniência quando a peça existente resolve) — Postgres/SQLite já está lá, uma tabela pequena é o caminho mais simples |

## Consequências

**Ganhamos:**
- A tela de login finalmente diz por que a tentativa falhou, com uma ação concreta pra cada caso — paridade com o padrão de login de produtos grandes (Google, GitHub etc.), que também revelam esse tipo de estado.
- O reenvio de confirmação deixa de depender de estado só-de-aba: um usuário que volta depois, fecha a aba, ou troca de dispositivo, consegue reenviar a partir da própria tela de login.
- `conta_google` fecha um buraco de UX que já existia antes desta revisão (conta só-Google tentando logar com senha caía na mesma mensagem genérica, sem sugerir o botão certo).

**Pagamos:**
- **Abrimos mão da proteção anti-enumeração original no login.** Um atacante agora consegue descobrir se um e-mail está cadastrado (confirmado, pendente, ou nenhum dos dois) só tentando logar — troca deliberada, mitigada apenas pelo rate limit já existente (`10/minute` por IP, `app/infra/rate_limit.py`), sem camada nova de defesa.
- `RegistroPendente` é estado novo, sem expiração ativa no banco — uma linha nunca confirmada fica lá para sempre (só deixa de contar nas checagens depois de 24h). Em volume alto, isso seria lixo acumulando sem limite; no volume esperado do projeto, é aceitável.
- Mais uma tabela pra manter sincronizada com o token (upsert em `/registrar`/`/reivindicar`, delete em `/confirmar`) — dois lugares que podem, em teoria, divergir (ex.: se o processo cair entre o `db.add` do `Usuario` e o `delete` do pendente em `/auth/confirmar` — mitigado por estarem no mesmo `db.commit()`, mas não por uma transação com rollback automático em caso de exceção no meio).

**Fica em aberto:**
- Sem job de limpeza, quantas linhas `RegistroPendente` órfãs vão se acumular ao longo do tempo é uma pergunta sem resposta hoje — não há métrica nem alerta para isso.
- Nenhum ADR retroativo documenta a decisão original de "registro sem estado" (commit `827ecfc`) — só este ADR, que a estende. Ficou combinado com o autor não escrever esse retroativo agora.

## Como saber que erramos

Se aparecer qualquer sinal de scraping/enumeração de e-mails contra `/auth/login` (picos de tentativas de IPs distintos testando e-mails em sequência, reclamação de usuário sobre spam correlacionado a tentativa de login), reavaliar: ou reintroduzir a mensagem genérica só para o caso `conta_nao_encontrada` (o mais sensível, porque prova que um e-mail *não* está em uso — o oposto, provar que está, já era possível de qualquer forma pela tela de registro, que sempre teve um 409 para e-mail confirmado duplicado), ou adicionar uma camada de defesa nova (captcha, rate limit mais agressivo por e-mail além de por IP).

## Referências

- [ADR-0014](0014-senha-com-google-opcional.md) — mecanismo de senha/Google que este ADR estende.
- [ADR-0016](0016-convidado-e-confirmacao-de-email-bloqueante.md) — confirmação de e-mail bloqueante e o token HMAC de confirmação, reaproveitado sem mudança aqui.
- [ADR-0004](0004-alembic-para-migrations.md) — Alembic, usado para a migração `0013_registros_pendentes.py`.
- `Backend/app/routers/auth.py` (`ErroLogin`, `_upsert_registro_pendente`, `_pendente_expirado`) e `Backend/app/main.py` (handler de `ErroLogin`) — implementação.
