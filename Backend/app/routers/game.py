import json
from collections.abc import Generator

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.domain.character import LoadRequest, UserAction
from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem, SessionLocal, Usuario, get_db
from app.infra.llm_client import ErroMestre, chamar_com_fallback
from app.infra.rate_limit import limiter
from app.infra.settings import settings
from app.infra.tracing import medir, turno_span
from app.services import combat, memory, rag_regras, rules_engine, telemetria
from app.services.agent_loop import executar_turno, executar_turno_stream
from app.services.auth import get_current_user, get_current_verified_user
from app.services.guardrail import corrigir_narrativa, limpar_formatacao, validar_narrativa
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


def _verificar_teto_diario(db: Session, current_user: Usuario) -> None:
    """Etapa 10 (A-3) — teto de turnos por usuário/dia, checado antes de
    gastar uma chamada à Groq. `EventoTelemetria` (Postgres) é quem conta,
    não `slowapi` (em memória): a máquina do Fly desliga sozinha quando
    ninguém joga (`min_machines_running = 0`), e um contador em memória
    zeraria a cada boot — o teto precisa sobreviver a isso."""
    teto = settings.teto_turnos_conta if current_user.email is not None else settings.teto_turnos_convidado
    if telemetria.turnos_hoje(db, current_user.id) >= teto:
        raise HTTPException(status_code=429, detail="A taverna fecha ao anoitecer; volte amanhã.")


def _persistir_memoria_em_segundo_plano(
    heroi_id: int, turno: int, tipo: str, texto: str, personagens: list[str]
) -> None:
    """Etapa 10 (A-6) — roda depois que a resposta já chegou ao jogador: nem
    o embedding (`infra/embeddings.embed_um`) nem a chamada ao modelo do
    resumo rolante (`memory.atualizar_resumo_rolante`) seguram mais o
    turno. Sessão própria (`SessionLocal`), não a do pedido — que já pode
    estar fechada quando isto roda, especialmente no `/chat/stream`."""
    db = SessionLocal()
    try:
        heroi = db.get(Personagem, heroi_id)
        if heroi is None:  # personagem arquivado/apagado entre o turno e isto rodar
            return
        memory.atualizar_resumo_rolante(heroi)
        db.commit()
        memory.registrar_evento(db, heroi_id, turno, tipo=tipo, texto=texto, personagens=personagens)
    finally:
        db.close()


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
        imagem=heroi.imagem, turno_mundo=w_state.turno,
    )


@router.post("/chat")
@limiter.limit("20/minute")
async def chat_endpoint(
    request: Request,
    user_input: UserAction,
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_verified_user),
    db: Session = Depends(get_db),
) -> dict:
    heroi = _buscar_personagem(db, current_user, user_input.session_id, "Sessão não encontrada.")
    _verificar_teto_diario(db, current_user)

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
            with turno_span(personagem_id=heroi.id, usuario_id=current_user.id, turno=w_state.turno):
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
        with medir("memoria", personagem_id=heroi.id, turno=w_state.turno):
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
            with (
                turno_span(personagem_id=heroi.id, usuario_id=current_user.id, turno=w_state.turno),
                medir("agente", personagem_id=heroi.id, turno=w_state.turno),
            ):
                narrativa, eventos_ferramentas, _chamadas = executar_turno(msgs, executor)
        except ErroMestre as e:
            # Etapa 10 (A-7) — a mensagem de erro é um campo próprio, não
            # texto embutido em `narrativa` com `*(...)*`: o histórico
            # nunca vê essa linha (o `return` é antes de persistir), e o
            # cliente sabe que é um aviso do sistema pelo campo, não por
            # decorar um padrão de asterisco no texto.
            return _resposta(
                heroi, c_state, q_state, narrativa="", erro=True, erro_mensagem=e.mensagem, turno_mundo=w_state.turno
            )

    violacoes = validar_narrativa(narrativa, heroi, c_state, w_state)
    if violacoes:
        narrativa = corrigir_narrativa(narrativa, violacoes, msgs)
    # Etapa 10 (A-7) — antes de juntar os eventos de sistema (que já são
    # texto puro, emoji sem markdown) e de persistir: o histórico vira
    # contexto do próximo turno, e markdown sujo ali ensina o modelo a
    # formatar mais, não menos.
    narrativa = limpar_formatacao(narrativa)

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

    # Etapa 10 (A-6) — resumo rolante e evento de memória saem do caminho
    # crítico: o jogador não paga o embedding nem a chamada extra ao modelo
    # pra ver a própria narração.
    background_tasks.add_task(
        _persistir_memoria_em_segundo_plano,
        heroi.id,
        w_state.turno,
        "morte" if eventos_morte else "turno",
        f"{user_input.action} → {narrativa[:300]}",
        [i.nome for i in c_state.inimigos],
    )
    telemetria.registrar_evento(db, current_user.id, "turno", personagem_id=heroi.id)

    return _resposta(
        heroi, c_state, q_state, narrativa=narrativa,
        turno_index=len(heroi.historico_chat) - 1, turno_mundo=w_state.turno,
    )


def _sse(evento: str, dados: dict) -> str:
    return f"event: {evento}\ndata: {json.dumps(dados, ensure_ascii=False)}\n\n"


@router.post("/chat/stream")
@limiter.limit("20/minute")
def chat_stream_endpoint(
    request: Request,
    user_input: UserAction,
    current_user: Usuario = Depends(get_current_verified_user),
    db: Session = Depends(get_db),
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
    # Checado aqui, antes de `StreamingResponse` existir — depois que a
    # stream abre, a rota não pode mais levantar `HTTPException` normal
    # (ver a mesma observação nos frames `erro`/`state` mais abaixo).
    _verificar_teto_diario(db, current_user)

    w_state = WorldState.model_validate(heroi.world_state or {})
    c_state = CombatState.model_validate(heroi.combat_state or {})
    q_state = QuestLog.model_validate(heroi.quest_log or {})

    w_state.turno += 1
    hist = contexto_recente(list(heroi.historico_chat), n=4)

    # Etapa 10 (A-6) — preenchido dentro de `gerar()`, lido por
    # `_tarefa_pos_stream` depois que a resposta inteira já foi entregue
    # (`background=` do `StreamingResponse`, não `BackgroundTasks`: a rota
    # é `def`, não `async def`, e devolve a resposta antes do generator
    # rodar — não há como injetar `BackgroundTasks` aqui do jeito normal).
    resultado_pos_stream: dict = {}

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
                with turno_span(personagem_id=heroi.id, usuario_id=current_user.id, turno=w_state.turno):
                    resp = chamar_com_fallback(msgs)
                narrativa = resp.choices[0].message.content or ""
            except ErroMestre:
                narrativa = ""
            if narrativa:
                yield _sse("token", {"texto": narrativa})
        else:
            resumo = ResumoRolante.model_validate(heroi.resumo_rolante or {})
            with medir("memoria", personagem_id=heroi.id, turno=w_state.turno):
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
            with (
                turno_span(personagem_id=heroi.id, usuario_id=current_user.id, turno=w_state.turno),
                medir("agente", personagem_id=heroi.id, turno=w_state.turno),
            ):
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
                # O frame `erro` já mandou a mensagem estruturada, ao vivo
                # (Etapa 7). Este `state` final não repete ela dentro de
                # `narrativa` — era o único lugar que ainda sujava o texto
                # persistido com `*(...)*` (Etapa 10, A-7).
                yield _sse(
                    "state",
                    _resposta(
                        heroi, c_state, q_state, narrativa="", erro=True,
                        erro_mensagem=erro_turno, turno_mundo=w_state.turno,
                    ),
                )
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
        # Etapa 10 (A-7) — mesma limpeza do `/chat` síncrono, antes de
        # persistir. O jogador já viu o texto cru ao vivo nos frames
        # `token` (limpar aqui não reescreve a tela, só o que fica salvo
        # e vira contexto futuro) — a limpeza leve *durante* o streaming
        # é responsabilidade do cliente (GameChat.tsx).
        narrativa = limpar_formatacao(narrativa)

        todos_eventos = eventos_morte + eventos_ferramentas
        if todos_eventos:
            narrativa += "\n\n" + "\n".join(todos_eventos)

        novo_hist = list(heroi.historico_chat)
        novo_hist.append({"role": "user", "content": user_input.action})
        novo_hist.append({"role": "assistant", "content": narrativa})
        heroi.historico_chat = novo_hist
        heroi.combat_state = c_state.model_dump()
        heroi.world_state = w_state.model_dump()
        db.commit()

        # Etapa 10 (A-6) — só agenda; quem executa é `_tarefa_pos_stream`,
        # depois que o `state` abaixo já tiver saído pro jogador.
        resultado_pos_stream.update(
            heroi_id=heroi.id,
            turno=w_state.turno,
            tipo="morte" if eventos_morte else "turno",
            texto=f"{user_input.action} → {narrativa[:300]}",
            personagens=[i.nome for i in c_state.inimigos],
        )
        telemetria.registrar_evento(db, current_user.id, "turno", personagem_id=heroi.id)

        yield _sse(
            "state",
            _resposta(
                heroi, c_state, q_state, narrativa=narrativa,
                turno_index=len(heroi.historico_chat) - 1, turno_mundo=w_state.turno,
            ),
        )

    def _tarefa_pos_stream() -> None:
        if resultado_pos_stream:
            _persistir_memoria_em_segundo_plano(**resultado_pos_stream)

    return StreamingResponse(gerar(), media_type="text/event-stream", background=BackgroundTask(_tarefa_pos_stream))
