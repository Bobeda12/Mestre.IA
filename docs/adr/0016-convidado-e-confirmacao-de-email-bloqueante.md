# ADR-0016 — Convidado como `Usuario` sem e-mail; confirmação de e-mail bloqueante para quem tem e-mail

**Data:** 22/08/2026
**Status:** Aceito
**Etapa:** 10
**Supersede:** —

---

## Contexto

O jogo está no ar desde a Etapa 9, mas só foi testado pelo próprio autor. `docs/backlog-pos-lancamento.md` lista o que esse uso real revelou antes de mandar o link para amigos — dois itens deste ADR vêm de lá:

- **A porta de entrada exige e-mail+senha antes do primeiro turno.** Todo produto que faz isso perde gente exatamente no primeiro contato — e este projeto não tem dado nenhum sobre quantos.
- **Não existe teto de custo por jogador** (ver ADR e código do A-3, item separado desta etapa) — mas o teto só funciona se der para saber quem é quem, inclusive quem ainda não criou conta. Um jogador sem identidade nenhuma quebraria essa contagem.
- **A chave da Groq é uma só, e é do autor.** Um convite para "dez amigos" precisa que cada e-mail seja de verdade — sem confirmação, nada impede alguém de criar contas com e-mails inventados, o que também quebraria o teto por usuário do A-3 (um usuário "fantasma" por e-mail nunca confirmado é um usuário que nunca é penalizado por esgotar o próprio teto de verdade).

`Usuario.email: Mapped[str | None]` já era opcional desde o ADR-0014 (uma conta podia ter só senha, só Google, ou os dois) — o schema já permitia um usuário sem e-mail nenhum, só nunca tinha sido usado assim.

## Decisão

**Convidado é um `Usuario(email=None)`, sem tabela nova.** `POST /auth/convidado` cria a linha, seta o mesmo cookie de sessão assinado que já existe (`services/auth.py`). `POST /auth/reivindicar` (autenticado como convidado) faz um `UPDATE` no mesmo `usuario_id` — os heróis não mudam de dono, só o `Usuario` ganha `email`/`senha_hash`. Rate limit apertado em `/auth/convidado` (1 por IP a cada 10 min), para não virar fábrica de contas descartáveis.

**Confirmação de e-mail é bloqueante para quem tem e-mail — não para convidado.** Nova coluna `email_verificado: bool` (default `False`). `get_current_verified_user` (nova dependency, ao lado de `get_current_user`) levanta `403` se `current_user.email is not None and not current_user.email_verificado` — aplicada só nas rotas que criam/avançam personagem (`/create_character`, `/chat`, `/chat/stream`), nunca em `/auth/*` nem em rotas de leitura (`/load_game`), senão o jogador nem consegue ver a própria tela pedindo confirmação. Contas via Google entram já verificadas (`obter_ou_criar_usuario_google`) — o Google já confirmou o e-mail no próprio fluxo OAuth (`email_verified` checado em `trocar_code_por_userinfo`), reconfirmar seria redundante.

O token de confirmação reaproveita o HMAC do cookie de sessão (`services/auth._assinar`/`_verificar`) — mesma chave de assinatura, payload com um campo `proposito: "confirmar_email"` explícito, para um token de confirmação nunca poder ser mal-lido como outra coisa (cookie de sessão, `state` do OAuth) se os formatos um dia colidirem por acaso. Validade de 24h, sem tabela nova.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Sessão anônima (sem `Usuario`, um cookie solto) | mais simples de implementar | quebraria o teto de custo por usuário do A-3 (nada para contar contra); heróis de convidado não teriam dono nenhum no schema `usuario (1:N) personagem` do ADR-0005 | o schema já modela usuário como dono de personagem — inventar um segundo conceito de "dono" só para convidado duplicaria a autorização por IDOR inteira |
| Confirmação suave (joga sem confirmar; bloqueia só troca de senha/recuperação) — a recomendação original do `docs/backlog-pos-lancamento.md` | não perde jogador nenhum na porta; menor atrito | não resolve o problema que motivou o item: um e-mail nunca confirmado continua sendo um teto de custo furado, exatamente o caso que mais importa quando o link vai para "dez amigos" de uma vez | o autor preferiu explicitamente a versão mais rígida — decisão de produto, registrada aqui por não ter alternativa técnica real por trás, só a escolha entre dois graus de rigor |
| Biblioteca de e-mail transacional com SDK próprio de template (ex. SendGrid com dynamic templates) | templates versionados fora do código | mais uma conta, mais uma camada de indireção para um e-mail HTML de três linhas | Resend com HTML inline (`app/infra/email.py`) resolve o mesmo problema com uma chamada de API só, sem template engine nenhuma — mesmo espírito de "não pesar mais que o problema pede" do ADR-0014 |
| Log do link no console citado como precedente do padrão condicional do Google | economizaria desenhar um fallback novo | **não existe de fato no código** — `google_disponivel()` é só uma flag booleana (`GET /auth/opcoes`), sem log nenhum quando as credenciais faltam | confirmado por exploração antes de implementar (ver `[[mestre-ia-verificar-codigo-antes-de-planejar]]`); o fallback "loga o link sem `RESEND_API_KEY`" é um padrão novo neste projeto, não uma cópia |

## Consequências

**Ganhamos:**
- O link pode ser mandado para um amigo sem exigir e-mail antes do primeiro turno — o atrito da porta de entrada cai para um clique.
- Ninguém perde progresso ao criar conta depois: `/auth/reivindicar` é um `UPDATE`, não uma migração de dados.
- O teto de custo por usuário (A-3) e a confirmação de e-mail se sustentam mutuamente: sem confirmação, o teto seria fácil de furar criando e-mails falsos; com convidado tendo teto próprio (menor), a porta sem e-mail não vira porta sem limite.
- Mesmo mecanismo de assinatura (HMAC) para três usos diferentes (sessão, `state` do OAuth, confirmação de e-mail) — zero dependência nova, zero tabela nova.

**Pagamos:**
- **O cookie de convidado é a única prova de identidade dele.** Limpar os dados do navegador, ou trocar de navegador, perde o herói — sem recuperação possível, porque não existe e-mail para recuperar por. Isso precisa estar escrito na tela (`Login.tsx`), não só neste ADR.
- Confirmação bloqueante é mais rígida do que a maioria dos produtos faz na porta de entrada — um jogador real pode registrar com e-mail, não ver o link a tempo, e ficar preso na tela `ConfirmeEmail` até checar a caixa de entrada (ou o spam). É uma escolha deliberada do autor, não um acidente, mas é o tipo de decisão que vale medir depois de mandar para amigos de verdade.
- `Usuario.email_verificado` não tem `server_default` no modelo do SQLAlchemy — só na migration (`0009_email_verificado.py`, `server_default=sa.false()`). Se algum código no futuro criar um `Usuario` fora do ORM (SQL cru), essa linha nasceria com o valor errado do banco (embora o default do driver para `BOOLEAN NOT NULL` sem valor explícito normalmente falhe alto, não silenciosamente).

**Fica em aberto:**
- Sem `RESEND_API_KEY` configurada em produção, ninguém recebe e-mail nenhum — o fluxo cai inteiro no fallback de log, que só o autor vê (`fly logs`). Configurar a chave é pré-requisito para o link funcionar de verdade para um amigo, não só para o autor testando localmente.
- O convite para reivindicar (mostrado no jogo depois do primeiro combate vencido ou 8 turnos) é um heurística de frontend, sem A/B nem métrica de conversão ainda — só existe telemetria de "sessão criada"/"turno", não de "convite mostrado"/"convite aceito".

## Como saber que erramos

Se, depois de mandar o link para amigos de verdade, a maior parte da fricção relatada for "não vi o e-mail de confirmação a tempo" (em vez de "não sabia se tinha que criar conta"), é sinal de que a confirmação bloqueante trocou um problema (custo por e-mail falso) por outro maior (abandono na porta) — nesse caso, reavaliar para a confirmação suave que o `docs/backlog-pos-lancamento.md` recomendava originalmente, com o teto de custo do convidado (mais apertado) segurando o risco de e-mail falso sozinho.

## Referências

- [ADR-0005](0005-usuario-personagem-antes-do-login.md) — o schema `usuario (1:N) personagem` que o convidado reaproveita sem tabela nova.
- [ADR-0014](0014-senha-com-google-opcional.md) — o cookie de sessão HMAC que o token de confirmação reaproveita.
- `docs/backlog-pos-lancamento.md` — a triagem original dos itens A-1/A-2 desta etapa.
- [Resend — Node/Python SDK docs](https://resend.com/docs/send-with-python) — a API usada em `app/infra/email.py`.
