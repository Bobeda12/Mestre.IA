# ADR-0001 — Gerenciar as dependências do backend com uv, não pip + venv

**Data:** 19/08/2026
**Status:** Aceito
**Etapa:** 0
**Supersede:** —

---

## Contexto

`Backend/requirements.txt` estava quebrado de um jeito específico: gerado com `pip freeze > requirements.txt` no PowerShell, o arquivo saiu em **UTF-16** (assinatura `ff fe`). `pip install -r requirements.txt` lê UTF-8 por padrão — o arquivo quebra em qualquer máquina que não seja a que o gerou, inclusive dentro de um container Docker.

Ele também carregava **14 pacotes do SDK do Gemini** (`google-ai-generativelanguage`, `google-api-core`, `grpcio`, `protobuf`, etc.) sem um único `import google` em qualquer arquivo `.py` do projeto — resíduo de uma fase anterior à migração para a Groq. `grep -rhoE "^import|^from" Backend/*.py` confirma: os imports reais são `fastapi`, `pydantic`, `python-dotenv`, `groq`, `sqlalchemy`, `uvicorn` — nada de Google.

Não existia lockfile: duas pessoas rodando `pip install -r requirements.txt` em datas diferentes podiam acabar com versões diferentes de `starlette` ou `pydantic`, sem nenhum sinal disso no repositório.

## Decisão

Backend gerenciado por **`uv`**, com `pyproject.toml` declarando as dependências reais e `uv.lock` fixando as versões exatas resolvidas. `requirements.txt` foi removido. `Backend/venv/` (criado por `python -m venv`) foi apagado; `uv sync` cria sua própria `.venv/`.

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Regerar `requirements.txt` em UTF-8 | menor mudança possível | não resolve a causa raiz — `pip freeze` continua sem lockfile determinístico, e alguém no PowerShell recria o mesmo bug amanhã | resolve o sintoma, não o problema |
| Poetry | lockfile determinístico, maduro, comunidade grande | `uv` é 10–100× mais rápido para instalar (relevante ao rodar `uv sync` no CI a cada PR, a partir da Etapa 2), e fala `pyproject.toml` padrão sem formato próprio | Poetry teria resolvido o mesmo problema; a escolha foi por velocidade e por ser o padrão emergente da comunidade Python em 2026 |
| pip-tools (`pip-compile`) | mais simples, menos uma ferramenta nova | ainda usa `pip install` por baixo (lento), e não substitui o gerenciamento de ambiente virtual | resolve só metade do problema (lock, não velocidade nem venv) |

## Consequências

**Ganhamos:**
- `uv sync` reproduz o ambiente exato em qualquer máquina, a partir do `uv.lock` — testado apagando `.venv` e reconstruindo do zero (ver diário 0001)
- instalação de ~2 segundos em vez de dezenas
- os 14 pacotes do Google saíram — o `pyproject.toml` só lista o que o código de fato importa

**Pagamos:**
- mais uma ferramenta para instalar antes de rodar o projeto (mitigado: `pip install uv` funciona em qualquer máquina com Python, sem instalador separado)
- o time (só eu, por enquanto) precisa aprender o vocabulário do `uv` (`sync`, `run`, `add`) em vez do `pip install` que todo mundo já sabe

**Fica em aberto:**
- ruff e mypy — cogitados para o mesmo `pyproject.toml` — ficam para a Etapa 2, para não misturar "arrumar a casa" com "melhorar a casa" na mesma etapa

## Como saber que erramos

Se `uv sync` falhar em alguma plataforma que o projeto precise suportar (ex.: a imagem Docker da Etapa 2, ou o ambiente do Fly.io na Etapa 9) e a causa for o próprio `uv` — não o código —, isso é sinal para reavaliar. Até lá, a hipótese é que um gerenciador de pacotes não deveria ser o gargalo de portabilidade de um projeto Python.

## Referências

- [Documentação do uv — Getting Started](https://docs.astral.sh/uv/getting-started/installation/)
- [uv — Why not pip-tools / Poetry?](https://docs.astral.sh/uv/pip/compatibility/)
