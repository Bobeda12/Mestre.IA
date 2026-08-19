from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.domain.character import LoadRequest, UserAction
from app.domain.state import CombatState, Inimigo, QuestLog, WorldState
from app.infra.db import Personagem, get_db
from app.services.memory import contexto_recente
from app.services.narrator import ErroMestre, chamar_mestre, montar_contexto

router = APIRouter(tags=["game"])


def _buscar_personagem(db: Session, session_id: str, mensagem_404: str) -> Personagem:
    heroi = db.query(Personagem).filter(Personagem.session_id == session_id).first()
    if heroi is None:
        raise HTTPException(status_code=404, detail=mensagem_404)
    return heroi


@router.post("/load_game")
def load_game(req: LoadRequest, db: Session = Depends(get_db)) -> dict:
    heroi = _buscar_personagem(db, req.session_id, "Save não encontrado")
    c_state = CombatState.model_validate(heroi.combat_state or {})
    w_state = WorldState.model_validate(heroi.world_state or {})

    return {
        "nome": heroi.nome,
        "raca": heroi.raca,
        "classe": heroi.classe,
        "hp_atual": heroi.hp_atual,
        "hp_max": heroi.hp_max,
        "defesa": heroi.defesa,
        "inventory": heroi.inventario,
        "atributos": heroi.atributos,
        "local": w_state.local,
        "combat_active": c_state.ativo,
        "inimigos": [i.model_dump() for i in c_state.inimigos],
        "missao": heroi.quest_log,
    }


@router.post("/chat")
async def chat_endpoint(user_input: UserAction, db: Session = Depends(get_db)) -> dict:
    heroi = _buscar_personagem(db, user_input.session_id, "Sessão não encontrada.")

    w_state = WorldState.model_validate(heroi.world_state or {})
    c_state = CombatState.model_validate(heroi.combat_state or {})
    q_state = QuestLog.model_validate(heroi.quest_log or {})

    prompt = montar_contexto(heroi, w_state, c_state, q_state)
    hist = contexto_recente(list(heroi.historico_chat), n=4)
    msgs = [{"role": "system", "content": prompt}] + hist + [{"role": "user", "content": user_input.action}]

    try:
        dados = chamar_mestre(msgs)
    except ErroMestre as e:
        return {
            "narrativa": f"*({e.mensagem})*",
            "erro": True,
            "hp_atual": heroi.hp_atual,
            "hp_max": heroi.hp_max,
            "defesa": heroi.defesa,
            "inventory": heroi.inventario,
            "atributos": heroi.atributos,
            "combat_active": c_state.ativo,
            "inimigos": [i.model_dump() for i in c_state.inimigos],
            "missao": q_state.model_dump(),
        }

    narrativa = dados.get("narrativa", "")

    # Combate básico (a máquina de estados de verdade é a Etapa 3).
    if dados.get("spawn_battle") and not c_state.ativo:
        c_state.ativo = True
        c_state.inimigos = [Inimigo(nome="Inimigo", hp=10, max_hp=10, ca=10)]
        narrativa += "\n\n⚔️ Inimigos surgem!"

    novo_hist = list(heroi.historico_chat)
    novo_hist.append({"role": "user", "content": user_input.action})
    novo_hist.append({"role": "assistant", "content": narrativa})
    # Reatribuição, não mutação in-place: é assim que o SQLAlchemy detecta
    # a mudança numa coluna JSON. Ver Lição 03.
    heroi.historico_chat = novo_hist
    heroi.combat_state = c_state.model_dump()
    db.commit()

    return {
        "narrativa": narrativa,
        "hp_atual": heroi.hp_atual,
        "hp_max": heroi.hp_max,
        "defesa": heroi.defesa,
        "inventory": heroi.inventario,
        "atributos": heroi.atributos,
        "combat_active": c_state.ativo,
        "inimigos": [i.model_dump() for i in c_state.inimigos],
        "missao": q_state.model_dump(),
    }
