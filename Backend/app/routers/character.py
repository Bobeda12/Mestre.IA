import random
from typing import Literal

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.domain.character import CharacterCreationRequest
from app.domain.living_world import MundoVivo
from app.domain.state import CombatState, LocalDescoberto, QuestLog, WorldState
from app.infra.byok import ChaveUsuario
from app.infra.data_manager import regras
from app.infra.db import Personagem, Usuario, get_db
from app.services import memory, telemetria
from app.services.auth import get_current_verified_user
from app.services.geracao_atributos import criar_token_atributos
from app.services.narrator import gerar_prologo_missao
from app.services.rules_engine import MATRIZ_CLASSICA, calcular_modificador, gerar_atributos_dados

router = APIRouter(tags=["character"])


class GerarAtributosRequest(BaseModel):
    modo: Literal["classica", "dados"]


class GerarAtributosResponse(BaseModel):
    valores: list[int]
    token: str | None = None


@router.post("/gerar_atributos", response_model=GerarAtributosResponse)
def gerar_atributos(
    pedido: GerarAtributosRequest, current_user: Usuario = Depends(get_current_verified_user)
) -> dict:
    """Remaster da criação (Fase 3) — o servidor é quem decide os seis
    valores, sempre (ADR-0002): a Matriz Clássica é fixa e pública, então
    não precisa de token; "dados" rola no servidor e devolve um token
    assinado que `CharacterCreationRequest.valida_atributos` confere depois.
    Rolagem ilimitada de propósito — cada chamada aqui é independente, o
    token anterior simplesmente nunca é usado."""
    if pedido.modo == "classica":
        return {"valores": MATRIZ_CLASSICA, "token": None}
    valores = gerar_atributos_dados()
    return {"valores": valores, "token": criar_token_atributos(valores)}


@router.post("/create_character")
def create_character(
    char: CharacterCreationRequest,
    current_user: Usuario = Depends(get_current_verified_user),
    db: Session = Depends(get_db),
    # BYOK (rodada de conserto) — antes desta mudança, criar personagem
    # sempre gastava a conta do servidor mesmo com "Traga sua própria
    # chave" ativado; só os turnos de jogo respeitavam o header.
    chave_usuario: str | None = Header(default=None, alias="X-Gemini-Key"),
) -> dict:
    chave = ChaveUsuario(chave_usuario)
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
    roteiro = gerar_prologo_missao(char, chamar_fn=chave.chamar_fn)

    world_state = WorldState(
        local=roteiro["local_inicial"], clima=roteiro["clima_inicial"], turno=1,
        inicio_aventura=roteiro.get("inicio_aventura", char.inicio_aventura),
        semente_aventura=roteiro.get("semente_aventura", 0),
        marcos=roteiro.get("chaves", []), hora_do_dia=roteiro.get("hora_do_dia", 8),
        versao_progressao=1,
        mundo=MundoVivo.model_validate(roteiro.get("mundo_inicial", {})),
    )
    # Rodada de conserto (Parte 2, item J) — "chega de goblins", agora
    # também pro ponto de partida: quando `gerar_prologo_missao` aceitou um
    # local NOVO (fora de data/locations.json, com descrição de verdade), é
    # aqui que ele entra pra valer em `locais_descobertos` — mesmo formato
    # que `tools.mover(descricao_proposta)` já usa em pleno jogo. Sem isto,
    # o herói "nasceria" num lugar que o resto do motor nunca ouviu falar.
    descricao_local_novo = roteiro.get("local_inicial_descricao")
    if descricao_local_novo:
        world_state.locais_descobertos = {
            roteiro["local_inicial"]: LocalDescoberto(descricao=descricao_local_novo, clima=roteiro["clima_inicial"])
        }
    # Fase 4 da revisão de gameplay — o esqueleto de Atos nasce junto com o
    # prólogo (mesma chamada ao modelo, `gerar_prologo_missao` já valida o
    # formato antes de devolver).
    quest_log = QuestLog(
        nome_missao=roteiro["nome_missao"], objetivo_missao=roteiro["objetivo_missao"], atos=roteiro["atos"]
    )

    novo = Personagem(
        usuario_id=current_user.id,
        session_id=session_id,
        nome=char.nome,
        raca=char.raca,
        classe=char.classe,
        alinhamento=char.alinhamento,
        background=char.background,
        objetivo=char.objetivo,
        imagem=char.imagem or None,
        historia_texto=char.historia_texto or None,
        resumo_historia=char.resumo_historia or None,
        temperamento_mestre=char.temperamento_mestre,
        dificuldade=char.dificuldade,
        hp_atual=hp,
        hp_max=hp,
        defesa=defesa,
        atributos=attr_final,
        inventario=d_classe.get("equipamento_inicial", ["Mochila", "Tocha"]),
        world_state=world_state.model_dump(),
        combat_state=CombatState().model_dump(),
        quest_log=quest_log.model_dump(),
        historico_chat=[{"role": "assistant", "content": roteiro["intro_narrativa"],
                         "opcoes": roteiro.get("opcoes", [])}],
    )
    db.add(novo)
    db.commit()
    telemetria.registrar_evento(db, current_user.id, "sessao_criada", personagem_id=novo.id)
    # Etapa 11 (B-7): a história que o jogador escreveu vira o primeiro
    # EventoMemoria dele — assim ela pode voltar pela busca híbrida (Etapa
    # 5) num turno 40 qualquer, não só no prólogo (turno 0 marca "antes do
    # jogo começar", não um turno de jogo de verdade).
    if char.historia_texto.strip():
        memory.registrar_evento(db, novo.id, 0, "historia_pessoal", char.historia_texto)
    return {
        "status": "Criado", "session_id": session_id, "hp_max": hp, "defesa": defesa,
        "inicio_aventura": world_state.inicio_aventura, "opcoes": roteiro.get("opcoes", []),
    }
