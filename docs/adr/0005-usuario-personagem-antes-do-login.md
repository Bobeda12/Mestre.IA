# ADR-0005 — Modelo de dados usuário × personagem, antes da tela de login

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 2
**Supersede:** —

---

## Contexto

Até esta etapa, `session_id` era a chave primária da tabela `herois` (`Backend/database.py`) — ou seja, na modelagem de dados, **personagem era sessão**. Isso combinava com o produto original (sessão anônima e descartável), mas deixou de combinar em 18/08/2026, quando a decisão de escopo §9.1 do `PLANO_MESTRE.md` fixou que o lançamento tem **login e biblioteca de heróis**, não sessão anônima.

O motivo de resolver isso *agora*, na Etapa 2, e não na Etapa 8 (quando a autenticação de verdade chega): trocar a chave primária de uma tabela com dados reais é a migration mais cara que existe — cada linha referenciando `herois.session_id` (hoje, nenhuma tabela faz isso, mas a tabela de memória vetorial da Etapa 5 faria) precisaria ser reescrita, e o próprio `session_id`, hoje uma string sem garantia de unicidade forte além do índice, teria que virar chave estrangeira em todo lugar. Hoje o banco não tem usuário nenhum jogando de verdade — o custo dessa mudança é zero. Depois que existir um primeiro usuário real, deixa de ser zero.

## Decisão

O schema nasce com duas tabelas:

```
usuario (id, email, criado_em)
   │ 1:N
personagem (id, usuario_id, session_id, nome, raca, classe, ...)
```

`Personagem.id` (inteiro, autoincremento) é a nova chave primária. `session_id` (a string `nome_1234` que o front já usa na URL `/jogar/:sessionId` e no `localStorage`) vira uma coluna comum, com índice único — ela continua existindo e continua sendo o identificador que atravessa a fronteira HTTP, porque o contrato com o Frontend não muda nesta etapa (nenhuma rota, payload ou tela é tocada).

Como ainda não existe tela de login, `app/main.py` garante, no startup, um único `Usuario` local fixo (`id=1`, `garantir_usuario_local()` em `app/infra/db.py`) — e todo personagem criado por `POST /create_character` recebe `usuario_id=1`. Este é o comportamento até a Etapa 8, quando a autenticação por e-mail mágico substitui o usuário fixo por usuários de verdade, sem precisar migrar a tabela `personagem` de novo — só passar a atribuir `usuario_id` a partir de uma sessão autenticada, em vez de uma constante.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Adiar o schema `usuario`/`personagem` para a Etapa 8, junto com a autenticação | menos trabalho agora; a Etapa 2 fica só sobre camadas, não sobre modelagem de dados | é exatamente a migration cara que este ADR existe para evitar — a Etapa 8 teria que trocar a PK de uma tabela que, a essa altura (depois das Etapas 3–7 gerando saves de teste reais), já teria dados que importam preservar | o custo de esperar cresce a cada etapa que roda por cima do schema antigo; adiar não elimina o trabalho, só o torna mais arriscado |
| Manter `session_id` como chave primária, e adicionar `usuario_id` como coluna extra sem trocar a PK | menor mudança de código | `session_id` é uma string derivada do nome do personagem (`f"{nome}_{random}"`) — não é um bom candidato a chave primária estável (dois jogadores podem, em teoria, colidir; e nada impede reescrevê-la no futuro). Manter uma PK de negócio em vez de uma PK técnica é uma escolha que a Etapa 8 (IDOR — checar que `personagem_id` só responde ao dono) tornaria mais frágil, não mais simples | PK técnica (inteiro autoincremento) é o padrão mais seguro para uma tabela que vai ganhar autorização por recurso em breve |
| Usar UUID em vez de inteiro autoincremento para `Personagem.id` | não vaza contagem de personagens criados; mais "correto" para sistemas distribuídos | este projeto é um monólito single-node (decisão consciente, `PLANO_MESTRE.md` §4.4) — o argumento de UUID (coordenação entre múltiplos nós gerando IDs) não se aplica; e inteiro autoincremento é mais simples de depurar em desenvolvimento | resolve um problema que o projeto não tem, ao custo de um tipo de dado mais pesado em todo índice e chave estrangeira |

## Consequências

**Ganhamos:**
- a Etapa 8 (login) vira "plugar autenticação em cima de um schema que já existe", não "migrar a tabela principal do produto com usuários reais nela" — o ganho é adiado até lá, mas garantido agora
- `Personagem.id` inteiro dá uma PK técnica estável, que a autorização por recurso da Etapa 8 (`personagem_id` só responde ao dono — a checagem de IDOR) pode usar sem ambiguidade
- o contrato HTTP não mudou: `session_id` continua sendo o que o front manda e recebe; ninguém no Frontend precisa saber que por baixo existe agora um `usuario_id`

**Pagamos:**
- uma tabela (`usuarios`) e uma linha (`garantir_usuario_local`) que não fazem nada de útil para o jogador hoje — é infraestrutura pura, construída antes da hora de uso, o oposto do que a "regra anti-escopo" do plano normalmente recomenda. A exceção se justifica porque o custo de *não* fazer isso agora (migration de PK com dados reais) é assimétrico: pequeno agora, grande depois.
- `usuario_id=1` fixo é, tecnicamente, uma authorization bypassada — qualquer requisição autentica como o mesmo usuário. Isso é aceitável só porque não existe múltiplos usuários ainda; se alguém expuser este backend publicamente antes da Etapa 8, a "conta" é compartilhada por todo mundo que acessar.

**Fica em aberto:**
- a Etapa 8 ainda vai precisar decidir o que fazer com personagens criados sob o `usuario_id=1` fixo antes de existir login — provavelmente atribuí-los ao primeiro usuário real que logar, ou descartá-los como dado de desenvolvimento. Este ADR não resolve isso, só evita que a pergunta exija uma migration de schema.

## Como saber que erramos

Se a Etapa 8 precisar alterar a estrutura da tabela `personagem` (não só passar a atribuir `usuario_id` dinamicamente) para suportar login de verdade, a modelagem feita aqui estava incompleta, e vale investigar o que faltou prever.

## Referências

- `PLANO_MESTRE.md` §9.1 — a decisão de produto (contas com múltiplos personagens) que este ADR implementa em schema
- [SQLAlchemy 2.0 — Relationship Configuration](https://docs.sqlalchemy.org/en/20/orm/relationship_config.html) — o par `relationship()`/`ForeignKey` usado entre `Usuario` e `Personagem`
