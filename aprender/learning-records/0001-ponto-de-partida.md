# 0001 — Ponto de partida: o caminho de uma requisição

**Data:** 17/08/2026
**Lição:** [0001 — O caminho de uma jogada](../lessons/0001-o-caminho-de-uma-jogada.html)

## Contexto

Primeira sessão. O Breno tinha acabado de receber um roadmap de portfólio e pediu para desacelerar: quer entender o código que escreveu com ajuda de IA antes de evoluí-lo. Missão registrada em `MISSION.md`.

## O que foi ensinado

O trajeto completo de uma ação do jogador, em seis paradas, cada uma atribuída a uma biblioteca:

1. React (estado) → 2. axios (fronteira HTTP/JSON) → 3. Uvicorn + FastAPI + Pydantic (servidor, roteamento, validação) → 4. SQLAlchemy + SQLite (persistência) → 5. SDK do Groq + Llama 3.3 (inferência) → 6. commit e redesenho.

Mais o glossário completo do stack, em `reference/0001-glossario-do-stack.html`.

## Insights não óbvios que precisam sobreviver

- **A distinção Uvicorn / FastAPI / Pydantic** é a que mais confunde iniciantes: servidor, roteador e porteiro são três coisas. Se ele misturar isso numa sessão futura, revisar.
- **O contexto do LLM é remontado do zero a cada turno.** O modelo não tem memória; toda memória do jogo vem do banco e é reinjetada como texto. Este é o conceito-chave que sustenta toda a Fase 2 do roadmap (memória e RAG).
- **Colunas JSON no SQLAlchemy exigem reatribuição** para serem detectadas como sujas. O código dele já faz isso (`dict(heroi.combat_state)`), mas provavelmente por acaso — foi escrito por IA. Vale confirmar se ele entendeu o porquê.

## Achados sobre o próprio código (usados como gancho de motivação)

- A amnésia do mestre é a linha `historico_chat[-4:]`, não uma limitação do modelo.
- O prompt pede `hp_atual` ao modelo, mas o `return` devolve `heroi.hp_atual` do banco, inalterado. **O HP nunca muda no jogo.** Nem o modelo nem um motor governam o dano — ninguém governa. Este achado é a ponte natural para a Fase 1 do roadmap.
- `requirements.txt` está em UTF-16 (gerado por `pip freeze >` no PowerShell) e pode quebrar `pip install -r` em outra máquina.
- ~13 pacotes do Google no `requirements.txt` são resquício de uma fase com Gemini; nenhum é importado hoje.
- `database.py` importa `declarative_base` do caminho legado (`sqlalchemy.ext.declarative`) em vez de `sqlalchemy.orm`.

## Verificado

- O `.env` **nunca foi commitado** (`git log --all -- Backend/.env` vazio; `.gitignore` cobre `.env` em qualquer diretório). A chave da Groq não precisa ser rotacionada.
- O repositório tem 4 commits: `Versão Inicial`, `muito foda`, `criação de personagem`, `chega`.

## Próximo passo sugerido

Zona de desenvolvimento proximal: ele agora sabe *onde* as peças estão, mas não *o que custa* usá-las. A Lição 2 natural é o anatomia do prompt — papéis `system`/`user`/`assistant`, tokens e por que a bíblia inteira em todo turno é uma decisão cara. Isso prepara tanto a Fase 1 quanto a Fase 2 do roadmap.

Alternativa, se ele quiser algo mais concreto: a Lição 3 sobre o ORM, que dá o vocabulário para o dia em que o SQLite tiver que virar Postgres.
