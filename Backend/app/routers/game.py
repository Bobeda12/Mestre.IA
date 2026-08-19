from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.domain.character import LoadRequest, UserAction
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem, get_db
from app.infra.llm_client import ErroMestre, chamar_com_fallback
from app.services import combat
from app.services.agent_loop import executar_turno
from app.services.guardrail import corrigir_narrativa, validar_narrativa
from app.services.memory import contexto_recente
from app.services.narrator import montar_contexto
from app.services.tools import ToolExecutor

router = APIRouter(tags=["game"])


def _buscar_personagem(db: Session, session_id: str, mensagem_404: str) -> Personagem:
    heroi = db.query(Personagem).filter(Personagem.session_id == session_id).first()
    if heroi is None:
        raise HTTPException(status_code=404, detail=mensagem_404)
    return heroi


def _resposta(heroi: Personagem, c_state: CombatState, q_state: QuestLog, **extra: object) -> dict:
    return {
        "hp_atual": heroi.hp_atual,
        "hp_max": heroi.hp_max,
        "defesa": heroi.defesa,
        "ouro": heroi.ouro,
        "inventory": heroi.inventario,
        "atributos": heroi.atributos,
        "combat_active": c_state.ativo,
        "inimigos": [i.model_dump() for i in c_state.inimigos],
        "missao": q_state.model_dump(),
        **extra,
    }


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
        "ouro": heroi.ouro,
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

    hist = contexto_recente(list(heroi.historico_chat), n=4)

    # Teste de morte é consequência automática de HP 0, não uma decisão do
    # jogador/modelo — resolvido antes de chamar o modelo, e sem ferramenta
    # nenhuma disponível (o herói está inconsciente, não pode agir).
    eventos_morte: list[str] = []
    eventos_ferramentas: list[str] = []
    if heroi.hp_atual <= 0:
        eventos_morte, hp_morte = combat.turno_morte(c_state)
        heroi.hp_atual = hp_morte
        prompt_morte = (
            f"{regras.get_biblia()}\n[HEROI] {heroi.nome} está inconsciente, a 0 PV, lutando contra a morte. "
            "Narre isso em 1-2 frases sombrias — sem diálogo de combate, sem números, sem ferramentas."
        )
        msgs = [{"role": "system", "content": prompt_morte}] + hist + [{"role": "user", "content": user_input.action}]
        try:
            resp = chamar_com_fallback(msgs)
            narrativa = resp.choices[0].message.content or ""
        except ErroMestre:
            narrativa = ""
    else:
        prompt = montar_contexto(heroi, w_state, c_state, q_state)
        msgs = [{"role": "system", "content": prompt}] + hist + [{"role": "user", "content": user_input.action}]
        executor = ToolExecutor(heroi, c_state, w_state)
        try:
            narrativa, eventos_ferramentas, _chamadas = executar_turno(msgs, executor)
        except ErroMestre as e:
            return _resposta(heroi, c_state, q_state, narrativa=f"*({e.mensagem})*", erro=True)

    violacoes = validar_narrativa(narrativa, heroi, c_state, w_state)
    if violacoes:
        narrativa = corrigir_narrativa(narrativa, violacoes, msgs)

    todos_eventos = eventos_morte + eventos_ferramentas
    if todos_eventos:
        narrativa += "\n\n" + "\n".join(todos_eventos)

    novo_hist = list(heroi.historico_chat)
    novo_hist.append({"role": "user", "content": user_input.action})
    novo_hist.append({"role": "assistant", "content": narrativa})
    # Reatribuição, não mutação in-place: é assim que o SQLAlchemy detecta
    # a mudança numa coluna JSON. Ver Lição 03.
    heroi.historico_chat = novo_hist
    heroi.combat_state = c_state.model_dump()
    heroi.world_state = w_state.model_dump()
    db.commit()

    return _resposta(heroi, c_state, q_state, narrativa=narrativa)
