"""Rate limit por IP (Etapa 9) — em memória, sem Redis: o Fly.io roda uma
única instância deste app por padrão (ver `fly.toml`), então não há estado
para sincronizar entre processos. Não sobrevive a múltiplas instâncias —
se o app crescer para mais de uma máquina, isto precisa virar um backend
compartilhado (Redis) para continuar valendo.

Existe por dois motivos, ambos citados no `PLANO_MESTRE.md` (§Etapa 9,
§7 "três armadilhas conhecidas"): força bruta em `/auth/login` (a
verificação de senha aceitava tentativas ilimitadas) e a cota da Groq —
compartilhada entre todos os jogadores — sendo drenada por uma única
pessoa martelando `/chat`.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address
from starlette.requests import Request


def _ip_do_cliente(request: Request) -> str:
    """`request.client.host` é o IP do proxy do Fly.io, não do visitante —
    o app roda atrás do edge do Fly, que sempre termina a conexão antes de
    repassar pro container. Sem isto, TODOS os jogadores caem no mesmo
    balde de rate limit (foi o que quebrou `/auth/convidado` e
    `/auth/login` pra gente mesmo, sem estar perto do limite real).

    `Fly-Client-IP` é posto pelo edge do Fly e não pode ser forjado pelo
    cliente (a conexão dele já termina ali). Cai pra `get_remote_address`
    só como rede de segurança fora do Fly (ex: rodando local)."""
    ip_fly = request.headers.get("Fly-Client-IP")
    if ip_fly:
        return ip_fly
    return get_remote_address(request)


limiter = Limiter(key_func=_ip_do_cliente)
