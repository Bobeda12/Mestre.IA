import functools
import json
from collections.abc import Callable, Generator
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from starlette.background import BackgroundTask

from app.domain.character import LoadRequest, UserAction
from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra import embeddings, llm_client
from app.infra.data_manager import regras
from app.infra.db import Personagem, SessionLocal, Usuario, get_db
from app.infra.llm_client import ErroMestre, chamar_com_fallback
from app.infra.rate_limit import limiter
from app.infra.settings import settings
from app.infra.tracing import medir, turno_span
from app.services import combat, memory, rag_regras, rules_engine, telemetria
from app.services.agent_loop import executar_turno, executar_turno_stream
from app.services.auth import get_current_user, get_current_verified_user
from app.services.guardrail import corrigir_narrativa, extrair_opcoes, limpar_formatacao, validar_narrativa
from app.services.memory import contexto_recente
from app.services.narrator import gerar_epitafio, montar_contexto
from app.services.tools import ToolExecutor, sincronizar_aliados

router = APIRouter(tags=["game"])

# Etapa 15 (BYOK) — modelo usado pro resumo rolante quando ele é ligado à
# chave do jogador (`chamar_com_chave_usuario`), no mesmo tier barato de
# `settings.modelo_barato` ("gemini:gemini-3.5-flash-lite"), só que sem o
# prefixo "provedor:" (que `chamar_com_chave_usuario` já fixa em "gemini").
_MODELO_BARATO_BYOK = settings.modelo_barato.rsplit(":", 1)[-1]


class _ChaveUsuario:
    """BYOK (Etapa 15) — agrupa as variantes de `chamar_fn`/`embed_fn`
    ligadas à chave que o jogador mandou no header `X-Gemini-Key` (nunca
    persistida — só vive como closure de `functools.partial` durante este
    request/BackgroundTask). Quando `chave` é `None`, todos os campos ficam
    `None` e quem consome usa o próprio default (cadeia/chave do
    servidor)."""

    def __init__(self, chave: str | None) -> None:
        self.presente = chave is not None
        self.chamar_fn: Callable[..., Any] | None = None
        self.chamar_fn_stream: Callable[..., Any] | None = None
        self.chamar_fn_barato: Callable[..., Any] | None = None
        self.embed_fn: Callable[[str], list[float]] | None = None
        if chave is not None:
            self.chamar_fn = functools.partial(llm_client.chamar_com_chave_usuario, api_key=chave)
            self.chamar_fn_stream = functools.partial(llm_client.chamar_stream_com_chave_usuario, api_key=chave)
            self.chamar_fn_barato = functools.partial(
                llm_client.chamar_com_chave_usuario, api_key=chave, modelo=_MODELO_BARATO_BYOK
            )
            self.embed_fn = functools.partial(embeddings.embed_um, api_key=chave)


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


def _verificar_teto_diario(db: Session, current_user: Usuario, chave: _ChaveUsuario, modo_emergencia: bool) -> None:
    """Etapa 10 (A-3) — teto de turnos por usuário/dia, checado antes de
    gastar uma chamada à Groq. `EventoTelemetria` (Postgres) é quem conta,
    não `slowapi` (em memória): a máquina do Fly desliga sozinha quando
    ninguém joga (`min_machines_running = 0`), e um contador em memória
    zeraria a cada boot — o teto precisa sobreviver a isso.

    Etapa 15 (BYOK) — quem manda a própria chave não consome cota do
    servidor, então não tem teto (`return` cedo). O "modo de emergência"
    (chave própria falhou, jogador topou usar a do servidor) tem um teto
    dedicado e bem mais curto que o normal, contado à parte
    (`tipo="turno_emergencia"`) — não vira um jeito de burlar o teto de
    conta só trocando de chave no meio do dia."""
    if chave.presente:
        return
    if modo_emergencia:
        teto = settings.teto_turnos_emergencia
        contados = telemetria.turnos_hoje(db, current_user.id, tipo="turno_emergencia")
    else:
        teto = settings.teto_turnos_conta if current_user.email is not None else settings.teto_turnos_convidado
        contados = telemetria.turnos_hoje(db, current_user.id)
    if contados >= teto:
        raise HTTPException(
            status_code=429,
            detail={"codigo": "teto_diario_atingido", "mensagem": "A taverna fecha ao anoitecer; volte amanhã."},
        )


def _tipo_telemetria_turno(chave: _ChaveUsuario, modo_emergencia: bool) -> str:
    """Etapa 15 (BYOK) — discrimina o tipo de `EventoTelemetria` gravado por
    turno, pra `turnos_hoje` conseguir contar cada teto separadamente sem
    misturar turnos que não consomem cota nenhuma (`turno_byok`) com os que
    consomem a cota normal (`turno`) ou a de emergência (`turno_emergencia`)."""
    if chave.presente:
        return "turno_byok"
    return "turno_emergencia" if modo_emergencia else "turno"


def _persistir_memoria_em_segundo_plano(
    heroi_id: int,
    turno: int,
    tipo: str,
    texto: str,
    personagens: list[str],
    chamar_fn_barato: Callable[..., Any] | None = None,
    embed_fn: Callable[[str], list[float]] | None = None,
) -> None:
    """Etapa 10 (A-6) — roda depois que a resposta já chegou ao jogador: nem
    o embedding (`infra/embeddings.embed_um`) nem a chamada ao modelo do
    resumo rolante (`memory.atualizar_resumo_rolante`) seguram mais o
    turno. Sessão própria (`SessionLocal`), não a do pedido — que já pode
    estar fechada quando isto roda, especialmente no `/chat/stream`.

    `chamar_fn_barato`/`embed_fn` (Etapa 15, BYOK): capturados como closure
    (`functools.partial` com a chave do jogador) ANTES desta tarefa ser
    agendada — o header HTTP que originou a chave já não existe mais
    quando isto roda em segundo plano."""
    db = SessionLocal()
    try:
        heroi = db.get(Personagem, heroi_id)
        if heroi is None:  # personagem arquivado/apagado entre o turno e isto rodar
            return
        memory.atualizar_resumo_rolante(heroi, chamar_fn=chamar_fn_barato)
        db.commit()
        memory.registrar_evento(db, heroi_id, turno, tipo=tipo, texto=texto, personagens=personagens, embed_fn=embed_fn)
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
        # Fase 3 da revisão de gameplay — roster persistente (fora e dentro
        # de combate; o HP em combate vem sincronizado de volta pra cá em
        # `sincronizar_aliados`, chamado antes desta função). Sem consumidor
        # no frontend ainda — nenhuma fase pediu HUD de aliado até aqui.
        "aliados": heroi.aliados,
        # Fase 8 da revisão de gameplay (Etapa 12/13) — a ferramenta
        # `ajustar_reputacao_npc` (Etapa 5) já existe e já entra no
        # contexto do narrador; nunca teve um consumidor no frontend até
        # aqui. Devolve todo o mapa (não só quem mudou neste turno) — é
        # pouca coisa, e o front decide sozinho o que faz sentido mostrar.
        "reputacao_npcs": heroi.reputacao_npcs,
        "combat_active": c_state.ativo,
        "ordem_iniciativa": c_state.ordem_iniciativa,
        "turno_atual": c_state.turno_atual,
        # Fase 1 da revisão de gameplay — o momento mais tenso do jogo
        # (herói a 0 PV, três falhas = morte) era calculado e nunca saía do
        # backend; o HUD desenha as caveiras/escudos a partir daqui.
        "sucessos_morte": c_state.sucessos_morte,
        "falhas_morte": c_state.falhas_morte,
        # Fase 1 — antes disto o frontend tratava QUALQUER `hp_atual <= 0`
        # como fim de jogo (GameChat.tsx), cobrindo a tela com "GAME OVER"
        # antes mesmo do primeiro teste de morte rodar. `resultado_combate`
        # é o sinal real: só "morte" (três falhas) é definitivo.
        "resultado_combate": c_state.resultado,
        # Fase 7 da revisão de gameplay — {"retrospectiva", "epitafio_curto"}
        # gerado uma vez quando `resultado_combate` vira "morte"; `None`
        # enquanto o herói está vivo.
        "epitafio": heroi.epitafio,
        "inimigos": [i.model_dump() for i in c_state.inimigos],
        "missao": q_state.model_dump(),
        **extra,
    }


def regras_xp_proximo_nivel(nivel: int) -> int | None:
    """`None` no nível máximo — não existe "próximo limiar" pra mostrar na
    barra de XP do HUD (Fase 3)."""
    return rules_engine.XP_POR_NIVEL.get(nivel + 1)


def _persistir_epitafio_se_confirmado(db: Session, heroi: Personagem, c_state: CombatState) -> None:
    """Fase 7 da revisão de gameplay — gerado uma vez, na primeira vez que
    `c_state.resultado` vira "morte" (chamado logo depois de
    `combat.turno_morte`, nos dois caminhos de `/chat`). `heroi.epitafio`
    já preenchido é o guarda: regerar a cada visita custaria dinheiro e
    daria uma memória diferente da mesma morte a cada vez."""
    if c_state.resultado != "morte" or heroi.epitafio is not None:
        return
    resumo = ResumoRolante.model_validate(heroi.resumo_rolante or {})
    marcantes = memory.eventos_marcantes(db, heroi.id)
    heroi.epitafio = gerar_epitafio(heroi, marcantes, resumo)


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
        imagem=heroi.imagem, turno_mundo=w_state.turno, clima=w_state.clima,
        background=heroi.background, objetivo=heroi.objetivo, historia_texto=heroi.historia_texto,
        historico_chat=heroi.historico_chat,
    )


@router.post("/chat")
@limiter.limit("20/minute")
async def chat_endpoint(
    request: Request,
    user_input: UserAction,
    background_tasks: BackgroundTasks,
    current_user: Usuario = Depends(get_current_verified_user),
    db: Session = Depends(get_db),
    chave_usuario: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_modo_emergencia: str | None = Header(default=None, alias="X-Modo-Emergencia"),
) -> dict:
    chave = _ChaveUsuario(chave_usuario)
    modo_emergencia = bool(x_modo_emergencia)
    heroi = _buscar_personagem(db, current_user, user_input.session_id, "Sessão não encontrada.")
    _verificar_teto_diario(db, current_user, chave, modo_emergencia)

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
        _persistir_epitafio_se_confirmado(db, heroi, c_state)
        prompt_morte = (
            f"{regras.get_biblia()}\n[HEROI] {heroi.nome} está inconsciente, a 0 PV, lutando contra a morte. "
            "[MOMENTO DE ALTO IMPACTO] — a vida por um fio, o momento mais tenso do jogo. Deixe a "
            "cena crescer, sem diálogo de combate, sem números, sem ferramentas."
        )
        msgs = [{"role": "system", "content": prompt_morte}] + hist + [{"role": "user", "content": user_input.action}]
        try:
            with turno_span(personagem_id=heroi.id, usuario_id=current_user.id, turno=w_state.turno):
                resp = (chave.chamar_fn or chamar_com_fallback)(msgs)
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
            memorias = memory.memorias_relevantes(
                db, heroi.id, user_input.action, w_state.turno, embed_fn=chave.embed_fn
            )
        # Etapa 15 (BYOK) — RAG de regras fica sempre na chave do servidor
        # (`embed_fn` não é passado aqui de propósito): é um texto fixo,
        # cacheado por processo por `id(embed_fn)`; ligar à chave do
        # jogador criaria um `functools.partial` novo a cada request e
        # reembedaria a bíblia inteira em toda chamada.
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
        executor = ToolExecutor(heroi, c_state, w_state, q_state)
        try:
            with (
                turno_span(personagem_id=heroi.id, usuario_id=current_user.id, turno=w_state.turno),
                medir("agente", personagem_id=heroi.id, turno=w_state.turno),
            ):
                narrativa, eventos_ferramentas, _chamadas = executar_turno(msgs, executor, chamar_fn=chave.chamar_fn)
        except ErroMestre as e:
            # Etapa 10 (A-7) — a mensagem de erro é um campo próprio, não
            # texto embutido em `narrativa` com `*(...)*`: o histórico
            # nunca vê essa linha (o `return` é antes de persistir), e o
            # cliente sabe que é um aviso do sistema pelo campo, não por
            # decorar um padrão de asterisco no texto.
            #
            # Etapa 15 (BYOK) — `erro_codigo` distingue uma falha da chave
            # do jogador (o front oferece o modo de emergência) de qualquer
            # outra falha do mestre (mensagem genérica, sem essa oferta).
            return _resposta(
                heroi, c_state, q_state, narrativa="", erro=True, erro_mensagem=e.mensagem,
                erro_codigo="chave_usuario_falhou" if chave.presente else None, turno_mundo=w_state.turno,
            )

    violacoes = validar_narrativa(narrativa, heroi, c_state, w_state)
    if violacoes:
        narrativa = corrigir_narrativa(narrativa, violacoes, msgs)
    # Etapa 10 (A-7) — antes de juntar os eventos de sistema (que já são
    # texto puro, emoji sem markdown) e de persistir: o histórico vira
    # contexto do próximo turno, e markdown sujo ali ensina o modelo a
    # formatar mais, não menos.
    narrativa = limpar_formatacao(narrativa)
    # Fase 1 da revisão de gameplay — a tag `[OPCOES]` nunca chega ao
    # jogador como texto; vira uma lista estruturada pro frontend renderizar
    # como botões (mantendo a caixa de texto livre como está).
    narrativa, opcoes = extrair_opcoes(narrativa)

    todos_eventos = eventos_morte + eventos_ferramentas
    if todos_eventos:
        narrativa += "\n\n" + "\n".join(todos_eventos)

    novo_hist = list(heroi.historico_chat)
    novo_hist.append({"role": "user", "content": user_input.action})
    novo_hist.append({"role": "assistant", "content": narrativa})
    # Reatribuição, não mutação in-place: é assim que o SQLAlchemy detecta
    # a mudança numa coluna JSON. Ver Lição 03.
    heroi.historico_chat = novo_hist
    sincronizar_aliados(heroi, c_state)  # Fase 3 — HP de aliado em combate precisa sobreviver ao turno
    heroi.combat_state = c_state.model_dump()
    heroi.world_state = w_state.model_dump()
    heroi.quest_log = q_state.model_dump()
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
        chamar_fn_barato=chave.chamar_fn_barato,
        embed_fn=chave.embed_fn,
    )
    telemetria.registrar_evento(
        db, current_user.id, _tipo_telemetria_turno(chave, modo_emergencia), personagem_id=heroi.id
    )

    return _resposta(
        heroi, c_state, q_state, narrativa=narrativa, opcoes=opcoes,
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
    chave_usuario: str | None = Header(default=None, alias="X-Gemini-Key"),
    x_modo_emergencia: str | None = Header(default=None, alias="X-Modo-Emergencia"),
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
    chave = _ChaveUsuario(chave_usuario)
    modo_emergencia = bool(x_modo_emergencia)
    heroi = _buscar_personagem(db, current_user, user_input.session_id, "Sessão não encontrada.")
    # Checado aqui, antes de `StreamingResponse` existir — depois que a
    # stream abre, a rota não pode mais levantar `HTTPException` normal
    # (ver a mesma observação nos frames `erro`/`state` mais abaixo).
    _verificar_teto_diario(db, current_user, chave, modo_emergencia)

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
            _persistir_epitafio_se_confirmado(db, heroi, c_state)
            prompt_morte = (
                f"{regras.get_biblia()}\n[HEROI] {heroi.nome} está inconsciente, a 0 PV, lutando contra a morte. "
                "[MOMENTO DE ALTO IMPACTO] — a vida por um fio, o momento mais tenso do jogo. Deixe a "
                "cena crescer, sem diálogo de combate, sem números, sem ferramentas."
            )
            msgs = (
                [{"role": "system", "content": prompt_morte}] + hist + [{"role": "user", "content": user_input.action}]
            )
            try:
                with turno_span(personagem_id=heroi.id, usuario_id=current_user.id, turno=w_state.turno):
                    resp = (chave.chamar_fn or chamar_com_fallback)(msgs)
                narrativa = resp.choices[0].message.content or ""
            except ErroMestre:
                narrativa = ""
            if narrativa:
                yield _sse("token", {"texto": narrativa})
        else:
            resumo = ResumoRolante.model_validate(heroi.resumo_rolante or {})
            with medir("memoria", personagem_id=heroi.id, turno=w_state.turno):
                memorias = memory.memorias_relevantes(
                    db, heroi.id, user_input.action, w_state.turno, embed_fn=chave.embed_fn
                )
            # Etapa 15 (BYOK) — mesma razão de `chat_endpoint`: RAG de
            # regras fica sempre na chave do servidor (cache por processo).
            regras_relevantes = rag_regras.regras_relevantes(user_input.action)
            nomes_na_cena = {i.nome for i in c_state.inimigos} | set(resumo.npcs_conhecidos)
            reputacoes = {nome: valor for nome, valor in heroi.reputacao_npcs.items() if nome in nomes_na_cena}

            prompt = montar_contexto(
                heroi, w_state, c_state, q_state,
                regras_relevantes=regras_relevantes, memorias=memorias, resumo=resumo, reputacoes=reputacoes,
            )
            msgs = [{"role": "system", "content": prompt}] + hist + [{"role": "user", "content": user_input.action}]
            executor = ToolExecutor(heroi, c_state, w_state, q_state)

            pedacos: list[str] = []
            erro_turno: str | None = None
            with (
                turno_span(personagem_id=heroi.id, usuario_id=current_user.id, turno=w_state.turno),
                medir("agente", personagem_id=heroi.id, turno=w_state.turno),
            ):
                for evento in executar_turno_stream(msgs, executor, chamar_fn=chave.chamar_fn_stream):
                    if evento.tipo == "token":
                        pedacos.append(evento.dados)
                        yield _sse("token", {"texto": evento.dados})
                    elif evento.tipo == "tool_event":
                        yield _sse("tool_event", evento.dados)
                    elif evento.tipo == "erro":
                        erro_turno = evento.dados
                        # Etapa 15 (BYOK) — `codigo` deixa o front oferecer
                        # o modo de emergência só quando a falha veio da
                        # chave do próprio jogador.
                        dados_erro: dict = {"mensagem": erro_turno}
                        if chave.presente:
                            dados_erro["codigo"] = "chave_usuario_falhou"
                        yield _sse("erro", dados_erro)

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
        # Fase 1 da revisão de gameplay — mesma extração do `/chat` síncrono.
        # A tag chega crua nos frames `token` ao vivo (o cliente já esconde
        # a cauda "[OPCOES" enquanto ela chega — GameChat.tsx); aqui é onde
        # o texto persistido/retomado nunca mais carrega a tag.
        narrativa, opcoes = extrair_opcoes(narrativa)

        todos_eventos = eventos_morte + eventos_ferramentas
        if todos_eventos:
            narrativa += "\n\n" + "\n".join(todos_eventos)

        novo_hist = list(heroi.historico_chat)
        novo_hist.append({"role": "user", "content": user_input.action})
        novo_hist.append({"role": "assistant", "content": narrativa})
        heroi.historico_chat = novo_hist
        sincronizar_aliados(heroi, c_state)  # Fase 3 — HP de aliado em combate precisa sobreviver ao turno
        heroi.combat_state = c_state.model_dump()
        heroi.world_state = w_state.model_dump()
        heroi.quest_log = q_state.model_dump()
        db.commit()

        # Etapa 10 (A-6) — só agenda; quem executa é `_tarefa_pos_stream`,
        # depois que o `state` abaixo já tiver saído pro jogador.
        resultado_pos_stream.update(
            heroi_id=heroi.id,
            turno=w_state.turno,
            tipo="morte" if eventos_morte else "turno",
            texto=f"{user_input.action} → {narrativa[:300]}",
            personagens=[i.nome for i in c_state.inimigos],
            chamar_fn_barato=chave.chamar_fn_barato,
            embed_fn=chave.embed_fn,
        )
        telemetria.registrar_evento(
            db, current_user.id, _tipo_telemetria_turno(chave, modo_emergencia), personagem_id=heroi.id
        )

        yield _sse(
            "state",
            _resposta(
                heroi, c_state, q_state, narrativa=narrativa, opcoes=opcoes,
                turno_index=len(heroi.historico_chat) - 1, turno_mundo=w_state.turno,
            ),
        )

    def _tarefa_pos_stream() -> None:
        if resultado_pos_stream:
            _persistir_memoria_em_segundo_plano(**resultado_pos_stream)

    return StreamingResponse(gerar(), media_type="text/event-stream", background=BackgroundTask(_tarefa_pos_stream))
