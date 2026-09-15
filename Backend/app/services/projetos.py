"""Primeiro ciclo de construção: escolha → condições → fatos → conquista estável."""

from app.domain.projetos import CondicaoProjeto, Projeto, PropostaProjeto
from app.services.emergencia import _chave, _presente, registrar_acontecimento


def gerir_projeto(executor, operacao: str, ambicao: str = "", projeto: str = "") -> dict:
    w = executor.w_state
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Cuide do perigo imediato antes de decidir o futuro do projeto."}
    if operacao == "iniciar":
        if not ambicao.strip() or len(ambicao) > 500:
            return {"erro": "Descreva sua ambição em até 500 caracteres."}
        if any(p.estado == "ativo" for p in w.mundo.projetos.values()):
            return {"erro": "Já existe um projeto ativo. Conclua ou abandone antes de iniciar outro."}
        if len(w.mundo.projetos) >= 30:
            return {"erro": "Esta campanha atingiu o limite de projetos."}
        p = Projeto(id=f"projeto_{len(w.mundo.projetos) + 1}", ambicao=ambicao.strip(), local=w.local, turno=w.turno)
        w.mundo.projetos[p.id] = p
        executor.eventos.append(f"Sua ambição: {p.ambicao}")
        return {"projeto": p.model_dump(),
                "orientacao": "Carregue projetos para propor condições concretas, sem roteiro."}
    p = w.mundo.projetos.get(projeto)
    if not p or p.estado != "ativo":
        return {"erro": "Escolha um projeto ativo."}
    if operacao == "concluir":
        if not p.condicoes or any(c.estado == "aberta" for c in p.condicoes):
            return {"erro": "Ainda faltam mudanças verificadas para concretizar esta ambição."}
        p.estado = "concluido"
        executor.eventos.append(f"Você concretizou: {p.ambicao}")
    elif operacao == "abandonar":
        p.estado = "abandonado"
        executor.eventos.append(f"Você deixou de perseguir: {p.ambicao}. As mudanças realizadas permanecem.")
    else:
        return {"erro": "Use iniciar, concluir ou abandonar."}
    return {"projeto": p.model_dump()}


def planejar_projeto(executor, projeto: str, condicoes: list[dict]) -> dict:
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Resolva o perigo imediato antes de planejar o projeto."}
    p = executor.w_state.mundo.projetos.get(projeto)
    if not p or p.estado != "ativo":
        return {"erro": "O jogador precisa escolher uma ambição primeiro."}
    if p.condicoes:
        return {"existente": p.model_dump(), "aviso": "Condições preservadas; novos meios podem superá-las."}
    if not 1 <= len(condicoes) <= 5:
        return {"erro": "Proponha de uma a cinco condições de resultado, sem passos obrigatórios."}
    propostas = [CondicaoProjeto.model_validate(c) for c in condicoes]
    if len({c.id for c in propostas}) != len(propostas) or any(not _presente(executor, c.alvo) for c in propostas):
        return {"erro": "Use IDs distintos e pessoas, lugares ou objetos presentes."}
    for c in propostas:
        c.estado, c.origem, c.evidencia = "aberta", "", ""
    p.condicoes = propostas
    return {"projeto": p.model_dump()}


def registrar_avanco_projeto(executor, projeto: str, condicao: str, origem: str,
                            evidencia: str, superada: bool = False) -> dict:
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Resolva o perigo imediato antes de registrar avanço no projeto."}
    w = executor.w_state
    p = w.mundo.projetos.get(projeto)
    c = next((c for c in p.condicoes if c.id == condicao), None) if p else None
    if not p or p.estado != "ativo" or not c:
        return {"erro": "Condição de projeto ativo não encontrada."}
    if c.estado != "aberta":
        return {"existente": c.model_dump()}
    evento = next((a for a in w.mundo.acontecimentos if a.id == origem), None)
    # A IA interpreta relevância; o motor exige uma transformação já executada, não uma promessa.
    if (not evento or evento.sucesso is not True or evento.local != w.local or not _presente(executor, c.alvo)
            or not evidencia.strip() or evidencia not in evento.descricao
            or evidencia not in w.mundo.condicoes.get(_chave(executor, c.alvo), [])):
        return {"erro": "Use uma condição persistente do alvo, produzida por acontecimento bem-sucedido neste local."}
    c.estado = "superada" if superada else "satisfeita"
    c.origem, c.evidencia = origem, evidencia
    executor.eventos.append(f"{p.ambicao}: {evidencia}")
    return {"mudanca": c.model_dump(), "pode_concluir": all(c.estado != "aberta" for c in p.condicoes)}


def painel_projetos(w_state) -> list[dict]:
    return [p.model_dump() for p in w_state.mundo.projetos.values()]


def propor_acordo_projeto(executor, projeto: str, proposta: dict) -> dict:
    w = executor.w_state
    p = w.mundo.projetos.get(projeto)
    a = PropostaProjeto.model_validate(proposta)
    if not p or p.estado != "ativo":
        return {"erro": "Escolha um projeto ativo."}
    existente = next((v for v in p.propostas if v.id == a.id), None)
    if existente:
        return {"existente": existente.model_dump()}
    npc = w.mundo.pessoas.get(a.npc)
    if not npc or not _presente(executor, a.npc) or executor.c_state.ativo:
        return {"erro": "A proposta exige conversa com uma pessoa presente, fora de combate."}
    grupo = w.mundo.organizacoes.get(a.organizacao) if a.organizacao else None
    if a.organizacao and (not grupo or a.npc not in grupo.membros):
        return {"erro": "O representante precisa pertencer à organização registrada."}
    if p.local != npc.local and not any(p.ambicao == c.texto for c in npc.conhecimentos):
        return {"erro": "A notícia desta ambição ainda não chegou ao NPC."}
    if not any(c.id == a.condicao and c.estado == "aberta" for c in p.condicoes):
        return {"erro": "Relacione a proposta a uma condição ainda aberta."}
    if len(p.propostas) >= 8 or any(v.npc == a.npc and v.estado == "oferecida" for v in p.propostas):
        return {"erro": "Desenvolva as propostas existentes antes de acrescentar outra."}
    a.nome_npc, a.estado, a.evidencia, a.origem = npc.nome, "oferecida", "", ""
    a.nome_organizacao = grupo.nome if grupo else ""
    p.propostas.append(a)
    executor.eventos.append(f"{npc.nome} propõe: {a.oferta}. Em troca: {a.contrapartida}.")
    return {"proposta": a.model_dump(), "aviso": "Oferta não é entrega nem aceitação pelo jogador."}


def decidir_acordo_projeto(executor, projeto: str, acordo: str, operacao: str) -> dict:
    w = executor.w_state
    p = w.mundo.projetos.get(projeto)
    a = next((a for a in p.propostas if a.id == acordo), None) if p else None
    if not a or not p:
        return {"erro": "Proposta não encontrada."}
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Resolva o perigo imediato antes de decidir compromissos."}
    npc = w.mundo.pessoas.get(a.npc)
    if not npc or not _presente(executor, a.npc):
        return {"erro": "Converse com a pessoa presente para comunicar sua decisão."}
    if operacao in {"aceitar", "recusar"}:
        if p.estado != "ativo" or a.estado != "oferecida":
            return {"erro": "Esta oferta já foi decidida ou o projeto não está ativo."}
        if operacao == "aceitar":
            if not any(c.id == a.condicao and c.estado == "aberta" for c in p.condicoes):
                return {"erro": "Essa condição já foi resolvida; a oferta perdeu seu propósito."}
            if any(v.id != a.id and v.condicao == a.condicao and v.estado in {"aceita", "cumprida"}
                   and (v.exclusiva or a.exclusiva) for v in p.propostas):
                return {"erro": "Há compromisso incompatível nesta condição. Renuncie a ele antes de escolher outro."}
        a.estado = "aceita" if operacao == "aceitar" else "recusada"
    elif operacao == "renunciar":
        if a.estado not in {"aceita", "cumprida"}:
            return {"erro": "Só é possível renunciar a um compromisso assumido."}
        a.estado = "renunciada"
    else:
        return {"erro": "Use aceitar, recusar ou renunciar."}
    descricao = f"Acordo com {a.nome_npc}: {a.estado}. Oferta: {a.oferta}. Contrapartida: {a.contrapartida}"
    npc.lembrancas = [*npc.lembrancas, descricao][-40:]
    executor.eventos.append(descricao)
    origem = registrar_acontecimento(executor, "decidir_acordo_projeto", {"descricao": descricao})
    return {"acordo": a.model_dump(), "acontecimento_id": origem,
            "aviso": "Nenhum recurso foi entregue automaticamente. Compromissos permanecem após encerrar o projeto."}


def cumprir_acordo_projeto(executor, projeto: str, acordo: str, origem: str, evidencia: str) -> dict:
    if executor.c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Resolva o perigo imediato antes de cumprir o compromisso."}
    w = executor.w_state
    p = w.mundo.projetos.get(projeto)
    a = next((a for a in p.propostas if a.id == acordo), None) if p else None
    if not p or not a or a.estado != "aceita":
        return {"erro": "Identifique um compromisso aceito e ainda não cumprido."}
    c = next(c for c in p.condicoes if c.id == a.condicao)
    evento = next((e for e in w.mundo.acontecimentos if e.id == origem), None)
    if (not evento or evento.sucesso is not True or evento.local != w.local
            or not _presente(executor, c.alvo) or not evidencia.strip() or evidencia not in evento.descricao
            or evidencia not in w.mundo.condicoes.get(_chave(executor, c.alvo), [])):
        return {"erro": "A contrapartida exige evidência de mudança executada no alvo da condição."}
    a.estado, a.evidencia, a.origem = "cumprida", evidencia, origem
    executor.eventos.append(f"Compromisso com {a.nome_npc} cumprido: {evidencia}")
    return {"acordo": a.model_dump(), "aviso": "Exclusividade permanece até renúncia explícita."}
