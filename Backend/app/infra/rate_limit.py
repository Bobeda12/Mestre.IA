"""Rate limit por IP (Etapa 9) — em memória, sem Redis: o Render roda uma
única instância deste app no plano free, então não há estado para
sincronizar entre processos. Não sobrevive a múltiplas instâncias — se o
app crescer para mais de uma máquina, isto precisa virar um backend
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
    """`request.client.host` é o IP do proxy do Render, não do visitante —
    o app roda atrás do edge do Render, que sempre termina a conexão antes
    de repassar pro container. Sem isto, TODOS os jogadores caem no mesmo
    balde de rate limit (foi o que quebrou `/auth/convidado` e
    `/auth/login` pra gente mesmo na Etapa 9, com o Fly.io; achado de novo
    na Etapa 14, migrando pro Render, porque a migração trocou o provedor
    sem trocar o nome do header aqui — o sintoma foi `/auth/convidado`
    parecendo travado, quando na verdade era o balde de todo mundo
    esgotado por poucas chamadas de teste).

    `*.onrender.com` é servido atrás do Cloudflare (confirmado nos headers
    de resposta reais — `Server: cloudflare`, `CF-RAY`), que sempre
    sobrescreve `CF-Connecting-IP` com o IP de quem conectou nele, não pode
    ser forjado pelo cliente (a conexão dele já termina ali) — ao contrário
    de `X-Forwarded-For`, que o Render só ANEXA sem limpar o que já veio no
    pedido, então confiar na primeira entrada dessa lista seria forjável.
    Cai pra `get_remote_address` só como rede de segurança fora desse
    caminho (ex: rodando local)."""
    ip_cloudflare = request.headers.get("CF-Connecting-IP")
    if ip_cloudflare:
        return ip_cloudflare
    return get_remote_address(request)


limiter = Limiter(key_func=_ip_do_cliente)
