"""Iniciativas coletivas usam os relógios e as intervenções do mundo existente."""

from app.domain.living_world import ConflitoMundo
from app.domain.organizacoes import Organizacao
from app.services.emergencia import _presente


def registrar_organizacao(executor, organizacao: dict) -> dict:
    m = executor.w_state.mundo
    g = Organizacao.model_validate(organizacao)
    if g.id in m.organizacoes:
        return {"existente": m.organizacoes[g.id].model_dump()}
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Apresente a organização numa conversa fora do perigo imediato."}
    if len(m.organizacoes) >= 20 or len(set(g.membros)) != len(g.membros):
        return {"erro": "Use membros distintos; limite de vinte organizações por campanha."}
    if any(n not in m.pessoas or not _presente(executor, n) for n in g.membros):
        return {"erro": "Os membros precisam ser NPCs registrados e presentes; não filie o jogador automaticamente."}
    g.local = executor.w_state.local
    m.organizacoes[g.id] = g
    executor.eventos.append(f"Você conhece {g.nome}: {g.proposito}")
    return {"organizacao": g.model_dump()}


def mobilizar_organizacao(executor, organizacao: str, origem: str, iniciativa: dict) -> dict:
    from app.services.living_world import registrar_conflito

    w = executor.w_state
    m = w.mundo
    g = m.organizacoes.get(organizacao)
    c = ConflitoMundo.model_validate(iniciativa)
    if not g or executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Organização registrada e conversa fora de combate são necessárias."}
    anterior = m.conflitos.get(c.id)
    if anterior:
        if anterior.organizacao == g.id:
            return {"existente": anterior.model_dump()}
        return {"erro": "Este ID já pertence a outra iniciativa."}
    npc = m.pessoas.get(c.agente)
    evento = next((e for e in m.acontecimentos if e.id == origem), None)
    if (not npc or c.agente not in g.membros or not _presente(executor, c.agente)
            or c.local != w.local or not evento):
        return {"erro": "Vincule um membro presente a um acontecimento real e ao local atual."}
    if evento.local != npc.local and not any(k.texto == evento.descricao for k in npc.conhecimentos):
        return {"erro": "O representante não conhece esse acontecimento distante."}
    if any(v.organizacao == g.id and v.origem == origem for v in m.conflitos.values()):
        return {"erro": "A organização já reagiu a esse acontecimento."}
    if any(v.agente == c.agente and v.estado == "ativo" for v in m.conflitos.values()) or sum(
        v.organizacao == g.id and v.estado == "ativo" for v in m.conflitos.values()
    ) >= 2:
        return {"erro": "O representante já está ocupado ou a organização tem duas iniciativas ativas."}
    if c.efeito == "bloquear":
        cena = m.cenas.get(w.local)
        alvo = cena.entidades.get(c.alvo) if cena else None
        if not alvo or alvo.recolhido or alvo.estado in {"destruido", "bloqueado"}:
            return {"erro": "O bloqueio precisa de um alvo acessível ainda não bloqueado."}
    # Pelo menos uma hora de jogo para reconhecer o sinal e intervir; o motor controla o relógio.
    c.intervalo = max(30, c.intervalo)
    resultado = registrar_conflito(executor, c.model_dump(exclude={"organizacao", "origem"}))
    if "erro" in resultado:
        return resultado
    registrado = m.conflitos[c.id]
    registrado.organizacao, registrado.origem = g.id, origem
    return {**resultado, "organizacao": g.nome,
            "orientacao": "Apoiar, atrasar ou negociar usa intervir_conflito. O tempo avança a iniciativa."}


def iniciativa_viavel(mundo, conflito) -> bool:
    """Não execute trabalho de um membro que partiu nem bloqueie objetos que desapareceram."""
    if not conflito.organizacao:
        return True
    grupo = mundo.organizacoes.get(conflito.organizacao)
    npc = mundo.pessoas.get(conflito.agente)
    if (not grupo or conflito.agente not in grupo.membros or not npc
            or npc.local != conflito.local or npc.disposicao == "ausente"):
        return False
    if conflito.efeito == "bloquear":
        cena = mundo.cenas.get(conflito.local)
        alvo = cena.entidades.get(conflito.alvo) if cena else None
        return bool(alvo and not alvo.recolhido and alvo.estado not in {"destruido", "bloqueado"})
    return True


def painel_organizacoes(w_state) -> list[dict]:
    m = w_state.mundo
    return [{
        **g.model_dump(exclude={"membros"}),
        "membros": [{"id": n, "nome": m.pessoas[n].nome} for n in g.membros if n in m.pessoas],
        # Só mostra andamento observável no local. Não transmite notícias distantes por telepatia.
        "iniciativas": [{"id": c.id, "nome": c.nome, "estado": c.estado,
                         "sinal": c.sinal if c.estado == "ativo" else c.desfecho}
                        for c in m.conflitos.values() if c.organizacao == g.id and c.local == w_state.local],
    } for g in m.organizacoes.values()]
