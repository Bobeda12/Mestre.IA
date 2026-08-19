"""Memória de curto prazo. Hoje só o slice das últimas N mensagens
(api.py:168, `historico_chat[-4:]`) — a base sobre a qual a Etapa 5
constrói o sumário rolante e a memória vetorial de longo prazo."""


def contexto_recente(historico: list[dict], n: int = 4) -> list[dict]:
    return list(historico)[-n:]
