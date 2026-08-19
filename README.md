# Mestre.IA

Um RPG narrado por um LLM — FastAPI + Groq no backend, React no front.

> Este README é propositalmente mínimo — só o necessário para rodar. A arquitetura, as decisões e o porquê de cada uma vivem em [`PLANO_MESTRE.md`](PLANO_MESTRE.md) e em [`docs/`](docs/). Um README de engenheiro completo (diagrama, limitações conhecidas) é entrega da Etapa 2 do plano.

## Pré-requisitos

- [Python 3.11+](https://www.python.org/)
- [uv](https://docs.astral.sh/uv/getting-started/installation/) — `pip install uv`
- [Node.js 20+](https://nodejs.org/) com npm
- Uma chave da [Groq](https://console.groq.com/keys) (grátis) — opcional, ver abaixo

## Rodar

Backend (num terminal):

```bash
cd Backend
cp .env.example .env   # cole sua GROQ_API_KEY, ou deixe em branco
uv sync
uv run uvicorn api:app --reload --port 8000
```

Frontend (em outro terminal):

```bash
cd Frontend
npm install
npm run dev
```

Abra `http://localhost:5173`.

**Sem chave da Groq:** o jogo ainda sobe e a criação de personagem funciona — ela cai num prólogo de fallback pré-escrito (`api.py:48`) em vez de gerar um com IA. O chat responde com narrativa vazia. É suficiente para navegar a interface; não é suficiente para jogar de verdade.

Se tiver [`just`](https://github.com/casey/just) instalado, os dois comandos acima viram `just backend-dev` e `just frontend-dev` (veja o [`justfile`](justfile) para a lista completa).

## Testar

```bash
cd Backend
uv run pytest -v
```

## Estrutura

```
Backend/    FastAPI + SQLAlchemy + Groq
Frontend/   React + TypeScript + Vite + Tailwind
docs/       decisões (ADR), diário de progresso — ver docs/README.md
aprender/   lições sobre o próprio código, para quem escreveu o projeto
```
