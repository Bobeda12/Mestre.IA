"""Estoque finito e transporte conservam unidades; nenhum relógio fabrica mercadoria."""

from app.domain.economia import Remessa
from app.services import items

ESTOQUE_INICIAL = 3
LIMITE_ITENS = 40


def estoque_atual(pessoa) -> dict[str, int]:
    if pessoa.estoque_inicializado:
        return dict(pessoa.estoque)
    return {n: ESTOQUE_INICIAL for n in pessoa.mercadoria}


def fixar_estoque(pessoa, estoque: dict[str, int]) -> None:
    pessoa.estoque, pessoa.estoque_inicializado = estoque, True


def vitrine(pessoa, inventados=None, desconto: int = 0) -> list[dict]:
    estoque = estoque_atual(pessoa)
    nomes = list(dict.fromkeys([*pessoa.mercadoria, *(n for n, q in estoque.items() if q > 0)]))
    return [{"item": n, "preco": items.preco_compra((items.ficha(n, inventados) or {}).get("preco", 0),
                                                    pessoa.confianca, desconto),
             "quantidade": estoque.get(n, 0)} for n in nomes]


def _passagem(w, origem, passagem, destino):
    cena = w.mundo.cenas.get(origem)
    porta = cena.entidades.get(passagem) if cena else None
    return bool(porta and porta.tipo == "saida" and porta.destino == destino
                and not porta.recolhido and porta.estado not in {"bloqueado", "destruido"})


def despachar_remessa(executor, id: str, remetente: str, destinatario: str, passagem: str,
                     item: str, quantidade: int, acontecimento: str) -> dict:
    w = executor.w_state
    m = w.mundo
    if id in m.remessas:
        return {"existente": m.remessas[id].model_dump()}
    origem, destino = m.pessoas.get(remetente), m.pessoas.get(destinatario)
    fato = next((a for a in m.acontecimentos if a.id == acontecimento), None)
    if (executor.c_state.ativo or not origem or not destino or origem.id == destino.id
            or origem.local != w.local or origem.disposicao == "ausente" or not fato):
        return {"erro": "Vincule comerciantes existentes, remetente presente e um acontecimento real."}
    if fato.local != origem.local and not any(k.texto == fato.descricao for k in origem.conhecimentos):
        return {"erro": "O remetente ainda não conhece esse acontecimento."}
    if not origem.mercadoria or not destino.mercadoria or not _passagem(w, w.local, passagem, destino.local):
        return {"erro": "É necessária uma saída acessível para o local do comerciante destinatário."}
    estoque = estoque_atual(origem)
    nome = items.resolver_nome(item, list(estoque))
    if type(quantidade) is not int or not 1 <= quantidade <= 3 or not nome or estoque.get(nome, 0) < quantidade:
        return {"erro": "Escolha de uma a três unidades realmente disponíveis no estoque de origem."}
    if len(m.remessas) >= 40 or any(r.remetente == remetente and r.estado != "entregue" for r in m.remessas.values()):
        return {"erro": "O remetente já tem carga em trânsito ou o limite de remessas foi atingido."}
    if any(r.remetente == remetente and r.acontecimento == acontecimento for r in m.remessas.values()):
        return {"erro": "Esse acontecimento já motivou uma remessa deste comerciante."}
    r = Remessa(id=id, remetente=remetente, destinatario=destinatario, origem=w.local, destino=destino.local,
                passagem=passagem, item=nome, quantidade=quantidade, acontecimento=acontecimento,
                chegada_em=m.minutos + 120)
    estoque[nome] -= quantidade
    fixar_estoque(origem, estoque)
    m.remessas[r.id] = r
    executor.eventos.append(f"{origem.nome} despacha {quantidade} × {nome} para {destino.nome}; viagem de duas horas.")
    return {"remessa": r.model_dump(), "aviso": "Carga reservada no estoque; bloqueios podem reter a entrega."}


def avancar_remessas(executor) -> None:
    w = executor.w_state
    m = w.mundo
    for r in m.remessas.values():
        if r.estado == "entregue" or m.minutos < r.chegada_em:
            continue
        destino = m.pessoas.get(r.destinatario)
        if (not destino or destino.local != r.destino or destino.disposicao == "ausente"
                or not _passagem(w, r.origem, r.passagem, r.destino)):
            r.estado = "retida"
            continue
        estoque = estoque_atual(destino)
        if r.item not in estoque and len(estoque) >= LIMITE_ITENS:
            r.estado = "retida"
            continue
        estoque[r.item] = estoque.get(r.item, 0) + r.quantidade
        fixar_estoque(destino, estoque)
        r.estado = "entregue"
        if w.local == r.destino:
            executor.eventos.append(f"Chegaram {r.quantidade} × {r.item} ao estoque de {destino.nome}.")


def painel_remessas(w) -> list[dict]:
    # O painel não transmite o estado do destino para um jogador em outro lugar.
    return [r.model_dump() for r in w.mundo.remessas.values() if r.destino == w.local]
