"""Descoberta, convivência e reconhecimento, ancorados no que foi jogado."""

from typing import TYPE_CHECKING

from app.domain.imersao import MarcaJornada, MomentoPessoal, Oportunidade
from app.services.emergencia import _presente

if TYPE_CHECKING:
    from app.services.tools import ToolExecutor


def _origem(executor: "ToolExecutor", origem: str):
    return next((a for a in executor.w_state.mundo.acontecimentos if a.id == origem), None)


def registrar_momento(executor: "ToolExecutor", momento: dict) -> dict:
    m = MomentoPessoal.model_validate(momento)
    w = executor.w_state
    estado = w.mundo
    if m.id in estado.momentos:
        return {"existente": estado.momentos[m.id].model_dump()}
    npc = estado.pessoas.get(m.npc)
    origem = _origem(executor, m.origem)
    if not npc or not _presente(executor, m.npc) or not origem:
        return {"erro": "O momento requer NPC presente e acontecimento real."}
    if origem.local != npc.local and not any(c.texto == origem.descricao for c in npc.conhecimentos):
        return {"erro": "O NPC ainda não soube desse acontecimento."}
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "A cena exige atenção ao perigo atual; reserve a conversa para depois."}
    if w.turno - estado.ritmo.ultimo_momento < 3:
        return {"erro": "Deixe o jogador responder e agir antes de introduzir outro momento pessoal."}
    if any(v.npc == m.npc and v.origem == m.origem for v in estado.momentos.values()):
        return {"erro": "Esta experiência compartilhada já foi lembrada; não repita a mesma cena."}
    if len(estado.momentos) >= 40:
        return {"erro": "Limite de momentos atingido; desenvolva os vínculos existentes."}
    m.local, m.turno = w.local, w.turno
    estado.momentos[m.id] = m
    estado.ritmo.ultimo_momento = w.turno
    estado.ritmo.tensao_seguida = 0
    # A iniciativa é do NPC. Convite não registra aceitação, promessa ou afeto do herói.
    npc.lembrancas = [*npc.lembrancas, m.gesto][-40:]
    executor.eventos.append(f"{npc.nome}: {m.gesto}" + (f" {m.convite}" if m.convite else ""))
    return {"registrado": m.id, "gesto": m.gesto, "convite": m.convite}


def registrar_marca(executor: "ToolExecutor", marca: dict) -> dict:
    m = MarcaJornada.model_validate(marca)
    w = executor.w_state
    if m.id in w.mundo.marcas_jornada:
        return {"existente": w.mundo.marcas_jornada[m.id].model_dump()}
    origem = _origem(executor, m.origem)
    if not origem:
        return {"erro": "A marca precisa nascer de algo realmente jogado."}
    if m.tipo == "objeto":
        if m.alvo not in (executor.heroi.inventario or []):
            return {"erro": "Esse objeto não pertence ao herói."}
    elif m.tipo in {"vinculo", "apelido"}:
        npc = w.mundo.pessoas.get(m.alvo)
        if not npc or not _presente(executor, m.alvo):
            return {"erro": "Identifique a pessoa presente que atribui a marca."}
        if origem.local != npc.local and not any(c.texto == origem.descricao for c in npc.conhecimentos):
            return {"erro": "Essa pessoa não conhece o acontecimento."}
    elif m.alvo not in {"heroi", w.local}:
        return {"erro": "O feito precisa se referir ao herói ou ao local atual."}
    if len(w.mundo.marcas_jornada) >= 30 or any(
        v.origem == m.origem and v.tipo == m.tipo and v.alvo == m.alvo for v in w.mundo.marcas_jornada.values()
    ):
        return {"erro": "Esta marca já existe ou o limite foi atingido."}
    m.local, m.turno = w.local, w.turno
    w.mundo.marcas_jornada[m.id] = m
    executor.eventos.append(f"{m.nome} — {m.significado}")
    return {"registrada": m.id, "descricao": m.significado}


def apresentar_oportunidades(executor: "ToolExecutor", oportunidades: list[dict]) -> dict:
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "A cena exige atenção ao perigo atual; reserve percepções para depois."}
    if not 1 <= len(oportunidades) <= 3:
        return {"erro": "Apresente de uma a três percepções relevantes."}
    propostas = [Oportunidade.model_validate(o) for o in oportunidades]
    if len({o.id for o in propostas}) != len(propostas) or any(not _presente(executor, o.alvo) for o in propostas):
        return {"erro": "Use alvos presentes e IDs distintos; não invente recursos para facilitar a solução."}
    w = executor.w_state
    for o in propostas:
        o.local, o.expira_turno = w.local, w.turno + 2
    w.mundo.oportunidades = {o.id: o for o in propostas}
    return {"percepcoes": [o.model_dump(exclude={"expira_turno"}) for o in propostas]}


def registrar_ritmo(executor: "ToolExecutor", acao: str, resultado: dict, em_combate: bool) -> None:
    w = executor.w_state
    r = w.mundo.ritmo
    r.ultima_acao = acao
    if em_combate or resultado.get("sucesso") is False:
        r.tensao_seguida = min(10, r.tensao_seguida + 1)
    else:
        r.tensao_seguida = max(0, r.tensao_seguida - 1)
    if em_combate and executor.c_state.resultado == "vitoria":
        r.ultima_vitoria = w.turno
    if acao == "descansar":
        r.ultimo_descanso, r.tensao_seguida = w.turno, 0
    w.mundo.oportunidades = {
        chave: o for chave, o in w.mundo.oportunidades.items()
        if o.local == w.local and w.turno < o.expira_turno and _presente(executor, o.alvo)
    }


def direcao_cena(w_state, c_state) -> dict:
    r = w_state.mundo.ritmo
    if c_state.ativo:
        foco = "tensao"
        orientacao = "Mostre intenção inimiga, terreno e risco perceptível; acolha soluções criativas."
    elif w_state.turno - r.ultimo_momento < 3:
        foco = "escuta"
        orientacao = "Deixe o jogador responder ao gesto. Não acrescente missão ou outra interrupção."
    elif r.tensao_seguida >= 2 or w_state.turno - r.ultima_vitoria <= 2:
        foco = "respiro"
        orientacao = "Dê espaço à conquista e à convivência; não transforme automaticamente a vitória em ameaça."
    elif w_state.turno - r.ultimo_descanso <= 2:
        foco = "convivio"
        orientacao = "Uma pessoa pode lembrar um gesto vivido ou fazer um convite, sem exigir uma missão."
    else:
        foco = "descoberta"
        orientacao = "Ofereça uma pista observável com lógica persistente. O jogador decide se quer experimentar."
    return {"foco": foco, "orientacao": orientacao,
            "limite": "Sugestão de ritmo: não suspende perigos reais, prazos nem a escolha do jogador."}


def painel_imersao(w_state) -> dict:
    m = w_state.mundo
    return {
        "momentos": [v.model_dump() for v in m.momentos.values()][-6:],
        "marcas": [v.model_dump() for v in m.marcas_jornada.values()],
        "oportunidades": [o.model_dump(exclude={"expira_turno"}) for o in m.oportunidades.values()
                           if o.local == w_state.local and w_state.turno < o.expira_turno],
    }
