"""Intenções livres, memória causal e iniciativas geradas, sem missões roteirizadas."""

import json
from typing import TYPE_CHECKING

from app.domain.emergencia import Acontecimento, Aprendizado, Consequencia, Intencao, Particularidade
from app.services import living_world as mundo

if TYPE_CHECKING:
    from app.services.tools import ToolExecutor


def _presente(executor: "ToolExecutor", alvo: str) -> bool:
    w = executor.w_state
    if alvo in {"heroi", w.local}:
        return True
    if executor.c_state.ativo and any(
        i.nome == alvo and i.hp > 0 and not i.afastado for i in executor.c_state.inimigos
    ):
        return True
    pessoa = w.mundo.pessoas.get(alvo)
    if pessoa:
        return pessoa.local == w.local and pessoa.disposicao != "ausente"
    cena = w.mundo.cenas.get(w.local)
    entidade = cena.entidades.get(alvo) if cena else None
    return bool(entidade and not entidade.recolhido and entidade.estado != "destruido")


def _chave(executor: "ToolExecutor", alvo: str) -> str:
    if alvo == "heroi" or alvo in executor.w_state.mundo.pessoas:
        return alvo
    return f"{executor.w_state.local}:{alvo}"


def registrar_acontecimento(executor: "ToolExecutor", acao: str, resultado: dict) -> str:
    estado = executor.w_state.mundo
    estado.sequencia_acontecimentos += 1
    registro = Acontecimento(
        id=f"evento_{estado.sequencia_acontecimentos}", turno=executor.w_state.turno,
        local=executor.w_state.local, acao=acao,
        descricao=str(resultado.get("descricao") or json.dumps(resultado, ensure_ascii=False))[:700],
        sucesso=resultado.get("sucesso") if isinstance(resultado.get("sucesso"), bool) else None,
    )
    estado.acontecimentos = [*estado.acontecimentos, registro][-100:]
    return registro.id


def registrar_particularidade(executor: "ToolExecutor", particularidade: dict) -> dict:
    proposta = Particularidade.model_validate(particularidade)
    estado = executor.w_state.mundo
    if proposta.id in estado.particularidades:
        return {"existente": estado.particularidades[proposta.id].model_dump(), "aviso": "Regra preservada."}
    if not _presente(executor, proposta.alvo):
        return {"erro": "A particularidade precisa de um alvo presente e registrado."}
    if len({p.id for p in proposta.pistas}) != len(proposta.pistas) or any(
        not _presente(executor, p.alvo) for p in proposta.pistas
    ):
        return {"erro": "Cada pista precisa de ID distinto e alvo presente."}
    if len(estado.particularidades) >= 100:
        return {"erro": "Limite de particularidades atingido."}
    proposta.local = executor.w_state.local
    proposta.pistas_descobertas = []
    estado.particularidades[proposta.id] = proposta
    if proposta.publica:
        mundo.registrar_fato(executor, proposta.regra)
    return {"registrada": proposta.id, "pista": proposta.pista}


def resolver_intencao(executor: "ToolExecutor", proposta: dict) -> dict:
    p = Intencao.model_validate(proposta)
    estado = executor.w_state.mundo
    if not _presente(executor, p.alvo):
        return {"erro": "Alvo ausente. Use IDs do mundo, heroi ou o nome do local atual."}
    if p.meio and p.meio not in (executor.heroi.inventario or []) and not _presente(executor, p.meio):
        return {"erro": "O meio precisa existir no inventário ou na cena."}
    for referencia in p.particularidades:
        regra = estado.particularidades.get(referencia)
        if not regra or regra.local != executor.w_state.local or not regra.publica:
            return {"erro": "Use apenas particularidades conhecidas nesta cena."}
    # Valide AMBOS os ramos antes de rolar ou alterar qualquer estado.
    for ramo in (p.sucesso, p.falha):
        chaves = [(e.tipo, e.alvo, e.texto) for e in ramo]
        if len(set(chaves)) != len(chaves):
            return {"erro": "Não repita o mesmo efeito em um ramo."}
        relacoes = [e.alvo for e in ramo if e.tipo == "relacao"]
        if len(set(relacoes)) != len(relacoes):
            return {"erro": "Uma mudança de relação por pessoa em cada ação."}
        projetadas = {k: set(v) for k, v in estado.condicoes.items()}
        for efeito in ramo:
            if efeito.tipo == "condicao":
                projetadas.setdefault(_chave(executor, efeito.alvo), set()).add(efeito.texto)
        if any(len(v) > 12 for v in projetadas.values()):
            return {"erro": "A combinação ultrapassa o limite de condições do alvo."}
    for efeito in [*p.sucesso, *p.falha]:
        if efeito.tipo in {"revelar", "pista"}:
            regra = estado.particularidades.get(efeito.alvo)
            if not regra or regra.local != executor.w_state.local:
                return {"erro": "Particularidade ausente nesta cena."}
            if efeito.tipo == "pista":
                pista = next((p for p in regra.pistas if p.id == efeito.texto), None)
                if not pista or not _presente(executor, pista.alvo):
                    return {"erro": "A pista deve existir e sua fonte estar acessível."}
        elif efeito.tipo == "encerrar_consequencia":
            consequencia = estado.consequencias.get(efeito.alvo)
            if not consequencia or consequencia.local != executor.w_state.local or consequencia.estado == "encerrada":
                return {"erro": "Consequência indisponível nesta cena."}
        elif not _presente(executor, efeito.alvo):
            return {"erro": "Todos os efeitos precisam de alvos presentes."}
        if efeito.tipo == "relacao" and efeito.alvo not in estado.pessoas:
            return {"erro": "Relações só se aplicam a pessoas registradas."}
        if efeito.tipo not in {"encerrar_consequencia", "revelar"} and not efeito.texto.strip():
            return {"erro": "Descreva a mudança concreta de cada efeito."}
        condicoes = estado.condicoes.get(_chave(executor, efeito.alvo), [])
        if efeito.tipo == "condicao" and len(condicoes) >= 12:
            return {"erro": "Resolva uma condição existente antes de acrescentar outra."}
        if efeito.tipo == "remover_condicao" and efeito.texto not in condicoes:
            return {"erro": "A condição a remover não existe."}
    # A mesma solução não concede rolagens infinitas, mesmo com outra redação.
    preparacao = estado.preparacao
    preparada = bool(preparacao and preparacao.expira_em > estado.minutos and preparacao.atributo == p.atributo)
    assinatura = json.dumps({
        "preparacao": preparacao.model_dump() if preparada and preparacao else None,
        "meio": p.meio, "condicoes": estado.condicoes,
        "regras": sorted(p.particularidades),
        "efeitos": [e.model_dump() for e in p.sucesso],
    }, ensure_ascii=False, sort_keys=True)
    bonus = min(2, sum(
        a.ativo and a.atributo == p.atributo and a.alvo == p.alvo
        and (a.alvo == "heroi" or a.alvo in estado.pessoas or a.local == executor.w_state.local)
        for a in estado.aprendizados.values()
    ))
    sucesso = mundo._testar(
        executor, "improvisar", p.alvo, p.atributo,
        {"simples": 10, "arriscada": 15, "dificil": 20}[p.dificuldade], assinatura, bonus + int(preparada),
    )
    if sucesso is None:
        return {"erro": "Esta tentativa já falhou. Mude o meio, as condições ou o efeito pretendido."}
    if preparada:
        estado.preparacao = None  # Consumida no teste, inclusive na falha; propostas inválidas preservam.
    efeitos = p.sucesso if sucesso else p.falha
    descricoes = []
    for efeito in efeitos:
        chave = _chave(executor, efeito.alvo)
        if efeito.tipo == "condicao":
            condicoes = estado.condicoes.setdefault(chave, [])
            if efeito.texto not in condicoes:
                condicoes.append(efeito.texto)
        elif efeito.tipo == "remover_condicao":
            estado.condicoes[chave].remove(efeito.texto)
        elif efeito.tipo == "relacao":
            pessoa = estado.pessoas[efeito.alvo]
            pessoa.confianca = max(-100, min(100, pessoa.confianca + efeito.valor * 5))
            pessoa.lembrancas = [*pessoa.lembrancas, efeito.texto][-40:]
        elif efeito.tipo == "encerrar_consequencia":
            estado.consequencias[efeito.alvo].estado = "encerrada"
        elif efeito.tipo == "informacao":
            mundo.registrar_fato(executor, efeito.texto)
        elif efeito.tipo == "revelar":
            regra = estado.particularidades[efeito.alvo]
            regra.publica = True
            mundo.registrar_fato(executor, regra.regra)
            descricoes.append(regra.regra)
            continue
        elif efeito.tipo == "pista":
            regra = estado.particularidades[efeito.alvo]
            pista = next(p for p in regra.pistas if p.id == efeito.texto)
            if pista.id not in regra.pistas_descobertas:
                regra.pistas_descobertas.append(pista.id)
            mundo.registrar_fato(executor, pista.texto)
            descricoes.append(pista.texto)
            continue
        descricoes.append(efeito.texto or "A iniciativa foi interrompida.")
    descricao = f"{p.intencao}: {'; '.join(descricoes)}"
    executor.eventos.append(descricao)
    return mundo._finalizar(executor, {"sucesso": sucesso, "descricao": descricao}, significativo=True)


def desenvolver_consequencia(executor: "ToolExecutor", consequencia: dict) -> dict:
    proposta = Consequencia.model_validate(consequencia)
    estado = executor.w_state.mundo
    if proposta.id in estado.consequencias:
        return {"existente": estado.consequencias[proposta.id].model_dump()}
    origem = next((a for a in estado.acontecimentos if a.id == proposta.origem), None)
    pessoa = estado.pessoas.get(proposta.agente)
    if not origem or not pessoa or pessoa.local != proposta.local or pessoa.disposicao == "ausente":
        return {"erro": "Vincule um acontecimento real e um agente presente no local da iniciativa."}
    if origem.local != pessoa.local and not any(k.texto == origem.descricao for k in pessoa.conhecimentos):
        return {"erro": "O agente não conhece esse acontecimento distante; a notícia precisa chegar primeiro."}
    if proposta.local not in estado.cenas:
        return {"erro": "Local não registrado."}
    anterior = estado.consequencias.get(proposta.substitui) if proposta.substitui else None
    if proposta.substitui and (
        not anterior or anterior.agente != proposta.agente or anterior.estado == "encerrada"
        or anterior.origem == proposta.origem
    ):
        return {"erro": "Replanejar exige iniciativa ativa do mesmo agente e um novo acontecimento."}
    if len(estado.consequencias) >= 60 or sum(
        c.estado != "encerrada" and c.agente == proposta.agente and c.id != proposta.substitui
        for c in estado.consequencias.values()
    ) >= 2:
        return {"erro": "Este agente já tem iniciativas suficientes; desenvolva as existentes."}
    if any(c.origem == proposta.origem and c.agente == proposta.agente for c in estado.consequencias.values()):
        return {"erro": "Esta reação do agente ao acontecimento já foi registrada."}
    proposta.estado = "pendente"
    proposta.vence_em = estado.minutos + proposta.apos_minutos
    if anterior:
        anterior.estado = "encerrada"
    estado.consequencias[proposta.id] = proposta
    if proposta.local == executor.w_state.local:
        mundo.registrar_fato(executor, proposta.sinal)
        executor.eventos.append(proposta.sinal)
    return {"registrada": proposta.id, "sinal": proposta.sinal, "origem": origem.model_dump()}


def amadurecer_consequencias(executor: "ToolExecutor") -> None:
    estado = executor.w_state.mundo
    for c in estado.consequencias.values():
        if c.estado == "pendente" and estado.minutos >= c.vence_em:
            c.estado = "disponivel"
            # A iniciativa se torna uma situação a interpretar, nunca um resultado imposto.
            if c.local == executor.w_state.local:
                executor.eventos.append(c.sinal)


def propor_aprendizado(executor: "ToolExecutor", aprendizado: dict) -> dict:
    proposta = Aprendizado.model_validate(aprendizado)
    estado = executor.w_state.mundo
    if proposta.id in estado.aprendizados:
        return {"existente": estado.aprendizados[proposta.id].model_dump()}
    origens = {a.id for a in estado.acontecimentos if a.acao == "resolver_intencao"}
    if len(set(proposta.origens)) < 2 or not set(proposta.origens) <= origens:
        return {"erro": "Um aprendizado requer duas experiências distintas de ações livres já resolvidas."}
    if not _presente(executor, proposta.alvo) or len(estado.aprendizados) >= 12:
        return {"erro": "Alvo ausente ou limite de aprendizados atingido."}
    proposta.ativo = False
    proposta.local = executor.w_state.local
    estado.aprendizados[proposta.id] = proposta
    return {"oferta": proposta.model_dump(), "efeito": "+1 no atributo contra este alvo, após sua escolha."}


def escolher_aprendizado(executor: "ToolExecutor", aprendizado: str) -> dict:
    estado = executor.w_state.mundo
    proposta = estado.aprendizados.get(aprendizado)
    if not proposta:
        return {"erro": "Aprendizado não oferecido."}
    if executor.c_state.ativo:
        return {"erro": "Escolha seu aprendizado fora de combate."}
    if proposta.ativo:
        return {"ativo": proposta.id}
    if sum(a.ativo for a in estado.aprendizados.values()) >= max(1, (executor.heroi.nivel or 1) // 3):
        return {"erro": "Limite de aprendizados ativos neste nível atingido."}
    proposta.ativo = True
    executor.eventos.append(f"Você desenvolveu {proposta.nome}: {proposta.descricao}")
    return {"ativo": proposta.id}


def painel_emergente(w_state, privado: bool = False) -> dict:
    estado = w_state.mundo
    particularidades = [p for p in estado.particularidades.values() if p.local == w_state.local]
    pessoas = {p.id for p in estado.pessoas.values() if p.local == w_state.local and p.disposicao != "ausente"}
    prefixo = f"{w_state.local}:"
    return {
        "acontecimentos": [a.model_dump() for a in estado.acontecimentos[-8:]],
        "particularidades": [
            p.model_dump() if privado else {
                "id": p.id, "alvo": p.alvo, "pista": p.pista,
                **({"regra": p.regra} if p.publica else {}),
                "pistas": [pista.texto for pista in p.pistas if pista.id in p.pistas_descobertas],
            }
            for p in particularidades
        ],
        "condicoes": {
            k: v for k, v in estado.condicoes.items() if k == "heroi" or k in pessoas or k.startswith(prefixo)
        },
        "consequencias": [
            c.model_dump() if privado else {"id": c.id, "sinal": c.sinal, "estado": c.estado}
            for c in estado.consequencias.values()
            if c.estado != "encerrada" and (privado or c.local == w_state.local)
        ][-12:],
        "aprendizados": [a.model_dump() for a in estado.aprendizados.values()],
    }
