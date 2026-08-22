"""Telemetria de produto (Etapa 9) — ver `app/infra/db.py:EventoTelemetria`
para o porquê da granularidade mínima."""

from sqlalchemy.orm import Session

from app.infra.db import EventoTelemetria


def registrar_evento(db: Session, usuario_id: int, tipo: str, personagem_id: int | None = None) -> None:
    db.add(EventoTelemetria(usuario_id=usuario_id, personagem_id=personagem_id, tipo=tipo))
    db.commit()
