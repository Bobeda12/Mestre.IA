from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.infra.db import Personagem, Usuario, get_db
from app.services.auth import get_current_user

router = APIRouter(prefix="/personagens", tags=["personagens"])


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
    return {"status": "arquivado"}
