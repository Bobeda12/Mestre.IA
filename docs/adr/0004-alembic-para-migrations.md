# ADR-0004 — Adotar Alembic para migrations

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 2
**Supersede:** —

---

## Contexto

Até esta etapa, o schema do banco nascia de `Base.metadata.create_all(bind=engine)` (`Backend/database.py`, chamado uma vez em `criar_banco()`, no import de `api.py`). Isso cria tabelas que ainda não existem, mas **não** altera tabelas que já existem — não adiciona coluna, não muda tipo, não cria índice novo. O diário da Etapa 1 já registrou o sintoma: ao adicionar a coluna `defesa`, o `rpg_save.db` antigo não ganhou a coluna sozinho, e a solução foi apagar o arquivo e deixar o `create_all` recriar do zero.

Isso era aceitável enquanto o banco só continha saves de teste. Deixa de ser aceitável a partir de agora, por dois motivos que se reforçam: (1) a Etapa 2 introduz a primeira mudança de schema real — a tabela `usuarios` e a troca de `session_id` de chave primária para coluna única (`ADR-0005`) — que só pode ser feita bem uma vez, antes de existir dado real; (2) toda etapa daqui para frente adiciona colunas (HP em combate, inventário mutável, memória vetorial), e "apagar o banco a cada mudança" para de ser uma opção no momento em que existir um usuário de verdade jogando.

## Decisão

O schema passa a ser gerenciado por **Alembic**. `migrations/env.py` lê a URL do banco de `app.infra.settings.Settings` (não duplica a configuração no `alembic.ini`) e aponta `target_metadata` para `app.infra.db.Base.metadata`, permitindo `alembic revision --autogenerate` detectar o que mudou nos modelos SQLAlchemy. A primeira revisão (`migrations/versions/0001_initial.py`) cria o schema do zero — `usuarios` e `personagens` — sem migrar o `rpg_save.db` anterior, porque não existe dado real para preservar (mesmo precedente da Etapa 1).

`Base.metadata.create_all()` continua existindo, mas só em `tests/conftest.py` — testes recriam o schema do zero a cada execução, o que é mais rápido que rodar migrations, e não tem o risco de "esquecer de gerar uma revisão" que a suíte de testes correndo contra Alembic teria. Em desenvolvimento e produção, quem cria/atualiza o schema é sempre `alembic upgrade head` (via `just backend-migrate`, ou o entrypoint do `Dockerfile`).

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Continuar com `create_all()`, e aceitar apagar o banco a cada mudança de schema | zero ferramenta nova, zero código de migration | funciona só até existir um usuário de verdade com um save que importa; não é uma estratégia, é adiar o problema | a Etapa 2 é justamente o momento de resolver isso antes de existir dado real — depois fica caro |
| Escrever `ALTER TABLE` manual em SQL, versionado em arquivos numerados próprios | controle total, zero dependência nova | reinventa o que o Alembic já faz — detectar divergência entre modelo e schema, rastrear qual revisão está aplicada, suportar downgrade — com muito mais chance de erro humano | não há benefício em rolar isso à mão; ao contrário de autenticação (`ADR` futuro sobre e-mail mágico), aqui não há argumento de simplicidade a favor do código próprio |
| Adotar um banco "schemaless" de fato (Mongo-like) para os campos JSON já soltos (`world_state`, `combat_state`) | evitaria migration para esses campos especificamente | os campos "duros" (`nome`, `hp_atual`, `usuario_id`, as chaves estrangeiras) continuariam precisando de schema — trocaria um problema por dois: sem garantia de schema nos campos estruturados, e ainda sem suporte a JOIN/FK que o `usuario × personagem` (`ADR-0005`) depende | o projeto já usa SQL relacional para o que é relacional (Etapa 2) e JSON solto só onde já era solto antes; misturar os dois paradigmas no motor de banco inteiro é trocar um problema conhecido por vários desconhecidos |

## Consequências

**Ganhamos:**
- a próxima mudança de schema (Etapa 3: colunas de combate; Etapa 5: tabela de memória vetorial) tem um caminho testado — `alembic revision --autogenerate` + revisão manual do que foi gerado — em vez de "apagar e recriar"
- o `Dockerfile` do backend roda `alembic upgrade head` no entrypoint, então subir um container novo (ou um ambiente de produção futuro, Etapa 9) sempre parte de um schema correto, sem passo manual esquecível
- a revisão inicial (`0001_initial.py`) é, ela mesma, documentação executável do schema — mais confiável que um diagrama que pode ficar desatualizado

**Pagamos:**
- uma ferramenta nova para aprender (ver Lição 03) e um diretório (`migrations/`) para manter sincronizado com os modelos — esquecer de gerar uma revisão depois de mudar `db.py` é um jeito novo de causar bug
- o autogenerate do Alembic não é perfeito: ele não detecta certas mudanças (renomear coluna vira "dropar uma, criar outra"; mudanças dentro de colunas JSON são invisíveis para ele, porque o schema dentro do JSON não é dele) — toda revisão autogerada precisa ser lida antes de aplicada, não só confiada

**Fica em aberto:**
- ainda não existe uma migration que rodou contra um banco com dado real para preservar (a `0001_initial` parte do zero). A primeira migration de verdade "com dado para preservar" só vai acontecer numa etapa futura — é aí que esta decisão é testada de verdade.

## Como saber que erramos

Se o par "gerar revisão com autogenerate" + "revisar manualmente" continuar exigindo correção manual pesada em mais de uma revisão seguida (autogenerate errando o que mudou), é sinal de que os modelos SQLAlchemy estão usando um recurso que o Alembic não segue bem (ex.: `CheckConstraint` complexo), e vale escrever a revisão à mão a partir daí, em vez de confiar no autogenerate.

## Referências

- [Alembic — Tutorial](https://alembic.sqlalchemy.org/en/latest/tutorial.html)
- [Alembic — Auto Generating Migrations](https://alembic.sqlalchemy.org/en/latest/autogenerate.html), seção "What does Autogenerate Detect (and what does it not detect)"
