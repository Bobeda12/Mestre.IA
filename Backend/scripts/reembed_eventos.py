"""Reprocessa `embedding` de todo `EventoMemoria` existente com o provedor
atual (Etapa 14, ADR-0023: fastembed local de 384 dim -> Gemini de 768 dim).

Sem rodar isto, eventos gravados antes da troca continuam com o vetor
antigo — `hybrid_search._cosseno` já degrada essa comparação para "sem
similaridade" (0.0) em vez de quebrar (dimensões diferentes nunca são
comparáveis), então o jogo funciona sem este script: eventos antigos só
ficam recuperáveis por busca léxica (BM25), não por busca densa. Rodar
isto restaura o sinal denso também para eventos antigos.

Uso: `uv run python scripts/reembed_eventos.py [--dry-run]` (lê o
`DATABASE_URL` de `app/infra/settings.py`, o mesmo banco do app — passe
`DATABASE_URL=...` na frente do comando para mirar outro banco, ex. o de
produção). Idempotente: rodar duas vezes só reprocessa o mesmo texto de
novo, sem duplicar nada."""

import argparse
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infra import embeddings  # noqa: E402
from app.infra.db import EventoMemoria, SessionLocal  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Só conta quantos eventos seriam reprocessados.")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        eventos = db.query(EventoMemoria).all()
        desatualizados = [e for e in eventos if len(e.embedding) != embeddings.EMBED_DIM]
        print(
            f"{len(eventos)} eventos no total, {len(desatualizados)} "
            f"com dimensão diferente de {embeddings.EMBED_DIM}."
        )

        if args.dry_run or not desatualizados:
            return

        for i, evento in enumerate(desatualizados, start=1):
            evento.embedding = embeddings.embed_um(evento.texto)
            if i % 50 == 0:
                db.commit()
                print(f"{i}/{len(desatualizados)}...")
        db.commit()
        print("Concluído.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
