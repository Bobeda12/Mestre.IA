import json
from collections.abc import Generator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.domain.character import LoadRequest, UserAction
from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem, Usuario, get_db
from app.infra.llm_client import ErroMestre, chamar_com_fallback
from app.services import combat, memory, rag_regras, rules_engine
from app.services.agent_loop import executar_turno, executar_turno_stream
from app.services.auth import get_current_user
from app.services.guardrail import corrigir_narrativa, validar_narrativa
from app.services.memory import contexto_recente
from app.services.narrator import montar_contexto
from app.services.tools import ToolExecutor

router = APIRouter(tags=["game"])


def _buscar_personagem(db: Session, current_user: Usuario, session_id: str, mensagem_404: str) -> Personagem:
    heroi = db.query(Personagem).filter(Personagem.session_id == session_id).first()
    if heroi is None:
        raise HTTPException(status_code=404, detail=mensagem_404)
    # IDOR (ver ADR-0014): o id está na URL/corpo do pedido, então qualquer
    # um pode tentar adivinhar o session_id de outra pessoa. 403, não um
    # 404 silencioso — o personagem existe, só não é deste usuário.
    if heroi.usuario_id != current_user.id:
        raise HTTPException(status_code=403, detail="Este personagem não pertence a você.")
    return heroi


def _resposta(heroi: Personagem, c_state: CombatState, q_state: QuestLog, **extra: object) -> dict:
    return {
        "hp_atual": heroi.hp_atual,
        "hp_max": heroi.hp_max,
        "defesa": heroi.defesa,
        "ouro": heroi.ouro,
        "nivel": heroi.nivel,
        "xp": heroi.xp,
        "xp_proximo_nivel": regras_xp_proximo_nivel(heroi.nivel),
        "inventory": heroi.inventario,
        "atributos": heroi.atributos,
        "combat_active": c_state.ativo,
        "ordem_iniciativa": c_state.ordem_iniciativa,
        "turno_atual": c_state.turno_atual,
        "inimigos": [i.model_dump() for i in c_state.inimigos],
        "missao": q_state.model_dump(),
        **extra,
    }


def regras_xp_proximo_nivel(nivel: int) -> int | None:
    """`None` no nível máximo — não existe "próximo limiar" pra mostrar na
    barra de XP do HUD (Fase 3)."""
    return rules_engine.XP_POR_NIVEL.get(nivel + 1)


@router.post("/load_game")
def load_game(
    req: LoadRequest, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    heroi = _buscar_personagem(db, current_user, req.session_id, "Save não encontrado")
    c_state = CombatState.model_validate(heroi.combat_state or {})
    w_state = WorldState.model_validate(heroi.world_state or {})
    q_state = QuestLog.model_validate(heroi.quest_log or {})

    return _resposta(
        heroi, c_state, q_state,
        nome=heroi.nome, raca=heroi.raca, classe=heroi.classe, local=w_state.local, missao=heroi.quest_log,
    )


@router.post("/chat")
async def chat_endpoint(
    user_input: UserAction, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> dict:
    heroi = _buscar_personagem(db, current_user, user_input.session_id, "Sessão não encontrada.")

    w_state = WorldState.model_validate(heroi.world_state or {})
    c_state = CombatState.model_validate(heroi.combat_state or {})
    q_state = QuestLog.model_validate(heroi.quest_log or {})

    w_state.turno += 1
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
        # Etapa 5: as três camadas de memória entram aqui — longo prazo
        # (busca híbrida sobre eventos passados deste personagem), regras
        # (RAG sobre a bíblia, em vez do texto inteiro) e médio prazo
        # (sumário rolante estruturado). Ver services/memory.py e
        # services/rag_regras.py.
        resumo = ResumoRolante.model_validate(heroi.resumo_rolante or {})
        memorias = memory.memorias_relevantes(db, heroi.id, user_input.action, w_state.turno)
        regras_relevantes = rag_regras.regras_relevantes(user_input.action)
        nomes_na_cena = {i.nome for i in c_state.inimigos} | set(resumo.npcs_conhecidos)
        reputacoes = {nome: valor for nome, valor in heroi.reputacao_npcs.items() if nome in nomes_na_cena}

        prompt = montar_contexto(
            heroi,
            w_state,
            c_state,
            q_state,
            regras_relevantes=regras_relevantes,
            memorias=memorias,
            resumo=resumo,
            reputacoes=reputacoes,
        )
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
    memory.atualizar_resumo_rolante(heroi)
    db.commit()

    memory.registrar_evento(
        db,
        heroi.id,
        w_state.turno,
        tipo="morte" if eventos_morte else "turno",
        texto=f"{user_input.action} → {narrativa[:300]}",
        personagens=[i.nome for i in c_state.inimigos],
    )

    return _resposta(heroi, c_state, q_state, narrativa=narrativa)


def _sse(evento: str, dados: dict) -> str:
    return f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
def chat_stream_endpoint(
    user_input: UserAction, current_user: Usuario = Depends(get_current_user), db: Session = Depends(get_db)
) -> StreamingResponse:
    """Versão em streaming de `/chat` (Etapa 7, ADR-0012) — mesma regra de
    jogo, mesma persistência, só a entrega ao cliente muda. Duplica a
    montagem de contexto de `chat_endpoint` de propósito: o plano desta
    etapa promete que `/chat` "continua existindo sem mudanças" (evals/
    testes dependem dele), e fundir os dois caminhos custaria arriscar
    aquele contrato por uma limpeza que pode esperar (ver diário da Etapa 7,
    "o que ficou para depois").

    Frames SSE, na ordem em que o jogador vê:
    - `token`: um pedaço de texto de narração.
    - `tool_event`: uma ferramenta resolveu — dado estruturado da rolagem.
    - `correcao`: o guardrail (Etapa 4) reescreveu a narrativa depois que
      ela já tinha sido narrada ao vivo — ver a nota de honestidade abaixo.
    - `erro`: o turno não se recuperou sozinho.
    - `state`: sempre o último frame — o mesmo formato de `_resposta()`,
      pra o HUD atualizar HP/inventário/combate de uma vez.
    """
    heroi = _buscar_personagem(db, current_user, user_input.session_id, "Sessão não encontrada.")

    w_state = WorldState.model_validate(heroi.world_state or {})
    c_state = CombatState.model_validate(heroi.combat_state or {})
    q_state = QuestLog.model_validate(heroi.quest_log or {})

    w_state.turno += 1
    hist = contexto_recente(list(heroi.historico_chat), n=4)

    def gerar() -> Generator[str]:
        eventos_morte: list[str] = []
        eventos_ferramentas: list[str] = []
        msgs: list[dict] = []

        if heroi.hp_atual <= 0:
            eventos_morte, hp_morte = combat.turno_morte(c_state)
            heroi.hp_atual = hp_morte
            prompt_morte = (
                f"{regras.get_biblia()}\n[HEROI] {heroi.nome} está inconsciente, a 0 PV, lutando contra a morte. "
                "Narre isso em 1-2 frases sombrias — sem diálogo de combate, sem números, sem ferramentas."
            )
            msgs = (
                [{"role": "system", "content": prompt_morte}] + hist + [{"role": "user", "content": user_input.action}]
            )
            try:
                resp = chamar_com_fallback(msgs)
                narrativa = resp.choices[0].message.content or ""
            except ErroMestre:
                narrativa = ""
            if narrativa:
                yield _sse("token", {"texto": narrativa})
        else:
            resumo = ResumoRolante.model_validate(heroi.resumo_rolante or {})
            memorias = memory.memorias_relevantes(db, heroi.id, user_input.action, w_state.turno)
            regras_relevantes = rag_regras.regras_relevantes(user_input.action)
            nomes_na_cena = {i.nome for i in c_state.inimigos} | set(resumo.npcs_conhecidos)
            reputacoes = {nome: valor for nome, valor in heroi.reputacao_npcs.items() if nome in nomes_na_cena}

            prompt = montar_contexto(
                heroi, w_state, c_state, q_state,
                regras_relevantes=regras_relevantes, memorias=memorias, resumo=resumo, reputacoes=reputacoes,
            )
            msgs = [{"role": "system", "content": prompt}] + hist + [{"role": "user", "content": user_input.action}]
            executor = ToolExecutor(heroi, c_state, w_state)

            pedacos: list[str] = []
            erro_turno: str | None = None
            for evento in executar_turno_stream(msgs, executor):
                if evento.tipo == "token":
                    pedacos.append(evento.dados)
                    yield _sse("token", {"texto": evento.dados})
                elif evento.tipo == "tool_event":
                    yield _sse("tool_event", evento.dados)
                elif evento.tipo == "erro":
                    erro_turno = evento.dados
                    yield _sse("erro", {"mensagem": erro_turno})

            if erro_turno is not None:
                yield _sse("state", _resposta(heroi, c_state, q_state, narrativa=f"*({erro_turno})*", erro=True))
                return

            narrativa = "".join(pedacos)
            eventos_ferramentas = executor.eventos

        violacoes = validar_narrativa(narrativa, heroi, c_state, w_state)
        if violacoes:
            # O jogador já viu a narrativa crua ao vivo — reescrevê-la em
            # silêncio na tela seria confuso (o texto "mudaria sozinho").
            # A correção ainda entra no que é PERSISTIDO (memória futura
            # nunca vê a versão inconsistente), mas o cliente recebe um
            # frame à parte pra decidir como mostrar isso, em vez de um
            # replace mudo. Trade-off deliberado — ver ADR-0012.
            corrigida = corrigir_narrativa(narrativa, violacoes, msgs)
            yield _sse("correcao", {"narrativa": corrigida})
            narrativa = corrigida

        todos_eventos = eventos_morte + eventos_ferramentas
        if todos_eventos:
            narrativa += "\n\n" + "\n".join(todos_eventos)

        novo_hist = list(heroi.historico_chat)
        novo_hist.append({"role": "user", "content": user_input.action})
        novo_hist.append({"role": "assistant", "content": narrativa})
        heroi.historico_chat = novo_hist
        heroi.combat_state = c_state.model_dump()
        heroi.world_state = w_state.model_dump()
        memory.atualizar_resumo_rolante(heroi)
        db.commit()

        memory.registrar_evento(
            db, heroi.id, w_state.turno,
            tipo="morte" if eventos_morte else "turno",
            texto=f"{user_input.action} → {narrativa[:300]}",
            personagens=[i.nome for i in c_state.inimigos],
        )

        yield _sse("state", _resposta(heroi, c_state, q_state, narrativa=narrativa))

    return StreamingResponse(gerar(), media_type="text/event-stream")
