"""Conquistas permitem descansar e preparar a próxima expedição, sem bônus inventados."""

from app.domain.instalacoes import Instalacao, Preparacao


def disponivel(w_state, instalacao) -> bool:
    m = w_state.mundo
    if not instalacao.ativa or instalacao.local != w_state.local:
        return False
    cena = m.cenas.get(instalacao.local)
    if not cena:
        return False
    if instalacao.alvo != instalacao.local:
        entidade = cena.entidades.get(instalacao.alvo)
        if not entidade or entidade.recolhido or entidade.estado in {"destruido", "bloqueado"}:
            return False
    chave = f"{instalacao.local}:{instalacao.alvo}"
    return instalacao.evidencia in m.condicoes.get(chave, [])


def propor_instalacao(executor, instalacao: dict) -> dict:
    w = executor.w_state
    m = w.mundo
    i = Instalacao.model_validate(instalacao)
    if i.id in m.instalacoes:
        return {"existente": m.instalacoes[i.id].model_dump()}
    p = m.projetos.get(i.projeto)
    c = next((c for c in p.condicoes if c.id == i.condicao), None) if p else None
    if not p or p.estado != "concluido" or p.local != w.local or not c or not c.evidencia:
        return {"erro": "A melhoria precisa de projeto concluído aqui e uma condição com evidência."}
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Resolva o perigo imediato antes de apresentar uma melhoria."}
    if len(m.instalacoes) >= 30 or any(v.projeto == p.id for v in m.instalacoes.values()):
        return {"erro": "Cada projeto sustenta uma melhoria; limite de trinta por campanha."}
    i.local, i.alvo, i.evidencia = w.local, c.alvo, c.evidencia
    # Valida a instalação física usando os fatos conquistados; campos enviados pela IA não ativam nada.
    i.ativa = True
    if not disponivel(w, i):
        return {"erro": "O lugar ou objeto precisa estar acessível e preservar a mudança conquistada."}
    i.ativa = False
    m.instalacoes[i.id] = i
    return {"oferta": i.model_dump(), "aviso": "O jogador decide inaugurar na Jornada. Sem custos automáticos."}


def usar_instalacao(executor, instalacao: str, operacao: str) -> dict:
    w = executor.w_state
    i = w.mundo.instalacoes.get(instalacao)
    if not i or i.local != w.local or executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "A instalação exige presença no local e ausência de combate."}
    if operacao == "inaugurar":
        if i.ativa:
            return {"erro": "Esta melhoria já foi inaugurada."}
        i.ativa = True
        if not disponivel(w, i):
            i.ativa = False
            return {"erro": "A melhoria perdeu as condições para funcionar."}
        executor.eventos.append(f"Você inaugura {i.nome}: {i.descricao}")
        return {"descricao": f"{i.nome} agora faz parte deste lugar."}
    if operacao != "preparar" or i.tipo != "oficina" or not disponivel(w, i):
        return {"erro": "Use uma oficina inaugurada e acessível para se preparar."}
    if w.mundo.preparacao and w.mundo.preparacao.expira_em > w.mundo.minutos:
        return {"erro": "Você já tem uma preparação. Use-a antes de preparar outra."}
    w.mundo.preparacao = Preparacao(instalacao=i.id, nome=i.nome, atributo=i.atributo,
                                   expira_em=w.mundo.minutos + 60 + 1440)
    descricao = f"Preparação em {i.nome}: +1 no próximo teste livre de {i.atributo}, válido por 24 horas após preparar."
    executor.eventos.append(descricao)
    return {"descricao": descricao, "preparacao": w.mundo.preparacao.model_dump()}


def painel_instalacoes(w_state) -> dict:
    preparacao = w_state.mundo.preparacao
    return {
        "lugares": [{**i.model_dump(), "disponivel": disponivel(w_state, i)}
                    for i in w_state.mundo.instalacoes.values()],
        "preparacao": preparacao.model_dump() if preparacao and preparacao.expira_em > w_state.mundo.minutos else None,
    }
