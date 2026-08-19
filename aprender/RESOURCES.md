# Recursos

Fontes de alta confiança para fundamentar as lições. Prioridade para documentação oficial e material escrito por quem construiu a coisa.

---

## Backend

### Tutorial oficial do FastAPI — ⭐ fonte primária
- **Link:** https://fastapi.tiangolo.com/tutorial/
- **Tipo:** documentação / tutorial
- **Autor:** Sebastián Ramírez (tiangolo), autor do framework
- **Por que confiar:** é o raro caso em que a documentação oficial é também o melhor curso disponível. Ensina em ordem crescente e cada página é executável.
- **Ler:** *First Steps*, *Request Body*, *Dependencies*. Cobre as paradas 3 e 4 da Lição 1.

### SQLAlchemy 2.0 — ORM Quick Start
- **Link:** https://docs.sqlalchemy.org/en/20/orm/quickstart.html
- **Tipo:** documentação
- **Nota:** o seu `database.py` usa `from sqlalchemy.ext.declarative import declarative_base`, que é o **caminho antigo**. Em 2.0 o correto é `from sqlalchemy.orm import declarative_base`. Vale conferir na doc e corrigir — é uma linha.

### Groq — Structured Outputs
- **Link:** https://console.groq.com/docs/structured-outputs
- **Tipo:** documentação do provedor
- **Relevância:** explica a diferença entre `json_object` (o que você usa: garante sintaxe) e saída presa a um schema (garante os campos). É a base da Fase 0 do roadmap.

### Groq — Text Chat
- **Link:** https://console.groq.com/docs/text-chat
- **Relevância:** os papéis `system` / `user` / `assistant` e como o histórico é montado.

---

## Frontend

### react.dev — Learn React
- **Link:** https://react.dev/learn
- **Tipo:** documentação oficial
- **Por que confiar:** reescrita do zero em 2023 pela equipe do React, com foco em modelo mental em vez de API. Muito material antigo na internet ensina padrões abandonados (componentes de classe) — esta é a referência atual.
- **Ler:** *State: A Component's Memory* e *Synchronizing with Effects*.

### Guia do Vite
- **Link:** https://vite.dev/guide/
- **Relevância:** entender a diferença entre servidor de desenvolvimento e build de produção.

---

## Arquitetura de sistemas com LLM

### Anthropic — Building effective agents
- **Link:** https://www.anthropic.com/engineering/building-effective-agents
- **Tipo:** ensaio de engenharia
- **Por que confiar:** escrito a partir de sistemas reais em produção, e argumenta contra complexidade desnecessária em vez de a favor.
- **Relevância direta:** é a fundamentação da tese "narrador × juiz" do roadmap.

---

## Comunidades (para depois — sabedoria, não conhecimento)

Nenhuma testada ainda. Candidatas quando ele quiser expor o projeto:

- **r/LocalLLaMA** — discussão técnica de qualidade sobre arquitetura e avaliação de LLM, menos hype que a média
- **Discord do FastAPI** e **fórum do SQLAlchemy** — dúvidas de framework, respondidas por gente que mantém o código
- **Grupos de RPG solo com IA** — o público-alvo do jogo; útil na hora do lançamento público (Fase 5)

*(Ele ainda não expressou preferência sobre comunidades. Perguntar antes de insistir.)*

---

## Ainda não avaliado

- Um bom material sobre avaliação de sistemas com LLM (para a Fase 3 do roadmap). Buscar quando chegar a hora.
- Referência de tool calling / function calling com Llama no Groq.
