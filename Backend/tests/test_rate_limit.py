"""Testa app/infra/rate_limit.py:_ip_do_cliente — a extração do IP real do
visitante por trás do proxy do Render. Regressão direta da Etapa 14: a
migração Fly.io -> Render (ADR-0022) trocou de provedor sem trocar o nome
do header aqui (`Fly-Client-IP` -> `CF-Connecting-IP`), o que fez todo
visitante em produção cair no mesmo balde de rate limit (`request.client.host`
vira o IP do proxy, não do visitante) sem nenhum teste pegar isso."""

from starlette.requests import Request

from app.infra.rate_limit import _ip_do_cliente


def _request(headers: list[tuple[bytes, bytes]], client_host: str = "10.0.0.1") -> Request:
    scope = {
        "type": "http",
        "headers": headers,
        "client": (client_host, 12345),
    }
    return Request(scope)


def test_usa_cf_connecting_ip_quando_presente():
    req = _request([(b"cf-connecting-ip", b"203.0.113.7")])
    assert _ip_do_cliente(req) == "203.0.113.7"


def test_cai_para_o_ip_da_conexao_sem_o_header():
    # Sem CF-Connecting-IP (ex.: rodando local, fora do Render/Cloudflare).
    req = _request([], client_host="127.0.0.1")
    assert _ip_do_cliente(req) == "127.0.0.1"


def test_ignora_x_forwarded_for_forjavel():
    # Render só ANEXA em X-Forwarded-For, sem limpar o que o cliente mandou
    # — confiar nele sem CF-Connecting-IP deixaria o visitante forjar o
    # próprio IP e escapar do rate limit de outra pessoa.
    req = _request(
        [(b"x-forwarded-for", b"1.2.3.4, 10.0.0.1")],
        client_host="10.0.0.1",
    )
    assert _ip_do_cliente(req) == "10.0.0.1"
