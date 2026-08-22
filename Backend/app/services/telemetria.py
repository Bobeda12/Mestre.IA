"""Telemetria de produto (Etapa 9) — ver `app/infra/db.py:EventoTelemetria`
para o porquê da granularidade mínima."""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from app.infra.db import EventoTelemetria


def registrar_evento(db: Session, usuario_id: int, tipo: str, personagem_id: int | None = None) -> None:
    db.add(EventoTelemetria(usuario_id=usuario_id, personagem_id=personagem_id, tipo=tipo))
    db.commit()


def turnos_hoje(db: Session, usuario_id: int) -> int:
    """Etapa 10 (A-3) — quantos turnos este usuário já jogou desde a
    meia-noite UTC de hoje. Naive UTC de propósito, mesma convenção de
    `services/auth.py._agora()`: o Postgres de produção guarda
    `criado_em` sem timezone, e comparar um `datetime` "aware" contra um
    valor "naive" lido do banco levantaria `TypeError` em qualquer
    aritmética Python (a query em si tolera, mas a consistência importa
    mais do que a exceção que não aconteceu desta vez)."""
    inicio_do_dia = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0, tzinfo=None)
    return (
        db.query(EventoTelemetria)
        .filter(
            EventoTelemetria.usuario_id == usuario_id,
            EventoTelemetria.tipo == "turno",
            EventoTelemetria.criado_em >= inicio_do_dia,
        )
        .count()
    )
