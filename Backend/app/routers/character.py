import random

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.domain.character import CharacterCreationRequest
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import USUARIO_LOCAL_ID, Personagem, get_db
from app.services.narrator import gerar_prologo_missao
from app.services.rules_engine import calcular_modificador

router = APIRouter(tags=["character"])


@router.post("/create_character")
def create_character(char: CharacterCreationRequest, db: Session = Depends(get_db)) -> dict:
    d_classe = regras.get_class_details(char.classe)
    d_raca = regras.get_race_details(char.raca)
    if not d_classe:
        raise HTTPException(status_code=400, detail=f"Classe '{char.classe}' não existe.")
    if not d_raca:
        raise HTTPException(status_code=400, detail=f"Raça '{char.raca}' não existe.")

    # O front PROPÕE atributos e pontos livres; aqui é onde o servidor DECIDE.
    # (dá para burlar o front direto pela API — é exatamente por isso que a
    # regra vive aqui, e não só na interface. Ver ADR-0002.)
    bonus_racial = d_raca.get("bonus_atributos", {})
    pontos_livres_da_raca = bonus_racial.get("livre_escolha", 0)

    if len(char.atributos_livre) != pontos_livres_da_raca:
        raise HTTPException(
            status_code=400,
            detail=(
                f"{char.raca} concede {pontos_livres_da_raca} ponto(s) de atributo livre; "
                f"o pedido trouxe {len(char.atributos_livre)}."
            ),
        )
    for attr in char.atributos_livre:
        if bonus_racial.get(attr, 0) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"'{attr}' já recebe bônus fixo de {char.raca}; o ponto livre precisa ir para outro atributo.",
            )

    attr_final = {
        attr: valor + bonus_racial.get(attr, 0) + (1 if attr in char.atributos_livre else 0)
        for attr, valor in char.atributos.items()
    }

    hp = d_classe.get("dado_vida", 8) + calcular_modificador(attr_final["constituicao"])
    defesa = 10 + calcular_modificador(attr_final["destreza"])

    session_id = f"{char.nome.lower()}_{random.randint(1000, 9999)}"
    roteiro = gerar_prologo_missao(char)

    world_state = WorldState(local=roteiro["local_inicial"], clima=roteiro["clima_inicial"], turno=1)
    quest_log = QuestLog(nome_missao=roteiro["nome_missao"], objetivo_missao=roteiro["objetivo_missao"])

    novo = Personagem(
        usuario_id=USUARIO_LOCAL_ID,
        session_id=session_id,
        nome=char.nome,
        raca=char.raca,
        classe=char.classe,
        alinhamento=char.alinhamento,
        background=char.background,
        objetivo=char.objetivo,
        hp_atual=hp,
        hp_max=hp,
        defesa=defesa,
        atributos=attr_final,
        inventario=d_classe.get("equipamento_inicial", ["Mochila", "Tocha"]),
        world_state=world_state.model_dump(),
        combat_state=CombatState().model_dump(),
        quest_log=quest_log.model_dump(),
        historico_chat=[{"role": "assistant", "content": roteiro["intro_narrativa"]}],
    )
    db.add(novo)
    db.commit()
    return {"status": "Criado", "session_id": session_id, "hp_max": hp, "defesa": defesa}
