from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from app.infra.db import FeedbackNarracao, Personagem, Usuario, get_db
from app.services import telemetria
from app.services.auth import get_current_user

router = APIRouter(prefix="/personagens", tags=["personagens"])


class FeedbackRequest(BaseModel):
    turno_index: int
    valor: int

    @field_validator("valor")
    @classmethod
    def valida_valor(cls, v: int) -> int:
        if v not in (1, -1):
            raise ValueError("valor precisa ser 1 (👍) ou -1 (👎).")
        return v


@router.get("")
def listar_personagens(
    current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> list[dict]:
    """A tela "Meus heróis" do front. O servidor é a única fonte da lista
    desde a Etapa 8 — `localStorage` morreu (ver ADR-0014)."""
    personagens = (
        db.query(Personagem)
        .filter(Personagem.usuario_id == current_user.id, Personagem.arquivado.is_(False))
        .order_by(Personagem.criado_em.desc())
        .all()
    )
    return [
        {
            "session_id": p.session_id,
            "nome": p.nome,
            "raca": p.raca,
            "classe": p.classe,
            "hp_max": p.hp_max,
            "defesa": p.defesa,
            "nivel": p.nivel,
            "criado_em": p.criado_em.isoformat(),
        }
        for p in personagens
    ]


@router.patch("/{session_id}/arquivar")
def arquivar_personagem(
    session_id: str, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    personagem = db.query(Personagem).filter(Personagem.session_id == session_id).first()
    if personagem is None:
        raise HTTPException(status_code=404, detail="Personagem não encontrado.")
    # Mesma regra de autorização de routers/game.py: dono só de si mesmo,
    # ou 403 — é o que impede o IDOR (trocar o id na URL e mexer no
    # personagem de outra pessoa).
    if personagem.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="Este personagem não pertence a você.")
    personagem.arquivado = True
    db.commit()
    telemetria.registrar_evento(db, current_user.id, "personagem_arquivado", personagem_id=personagem.id)
    return {"status": "arquivado"}


@router.post("/{session_id}/feedback", status_code=201)
def registrar_feedback(
    session_id: str,
    req: FeedbackRequest,
    current_user: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """👍/👎 numa narração específica (Etapa 9) — `turno_index` é a posição
    dela em `Personagem.historico_chat` (ver `routers/game.py:_resposta`,
    que devolve esse índice em `turno_index` a cada turno)."""
    personagem = db.query(Personagem).filter(Personagem.session_id == session_id).first()
    if personagem is None:
        raise HTTPException(status_code=404, detail="Personagem não encontrado.")
    if personagem.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="Este personagem não pertence a você.")
    if not (0 <= req.turno_index < len(personagem.historico_chat)):
        raise HTTPException(status_code=400, detail="turno_index fora do histórico deste personagem.")

    db.add(FeedbackNarracao(personagem_id=personagem.id, turno_index=req.turno_index, valor=req.valor))
    db.commit()
    return {"status": "registrado"}
