"""Token assinado para o modo "Rolar Dados" da criação de personagem
(remaster da criação, Fase 3).

O cliente PROPÕE quais atributos ele quer alocar, mas os seis valores
rolados em si têm que vir só do servidor — se o jogador pudesse mandar
qualquer array de 6 números, "rolar dados" viraria só uma segunda forma de
point-buy sem limite. Sem criar tabela nova no banco, o valor rolado viaja
num token HMAC-SHA256 assinado à mão (mesmo esquema de
`services/auth.py:_assinar`/`_verificar`, duplicado aqui de propósito — são
só ~10 linhas, e os dois módulos não precisam depender um do outro para
compartilhar um detalhe de implementação tão pequeno).

`POST /gerar_atributos` (routers/character.py) emite o token; `create_character`
confere com `ler_token_atributos` antes de aceitar `modo_atributos="dados"`.
Rolagem é ilimitada (decisão de produto): cada chamada ao endpoint emite um
token novo, o anterior simplesmente nunca é usado."""

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta

from app.infra.settings import settings

# Tempo generoso: o jogador pode rolar, ler a ficha, trocar de aba pra
# pensar, e só depois terminar a criação — 30 min cobre isso sem deixar um
# token válido por dias.
_TTL_TOKEN_ATRIBUTOS = timedelta(minutes=30)


def _b64(dados: bytes) -> str:
    return base64.urlsafe_b64encode(dados).rstrip(b"=").decode("ascii")


def _b64_decode(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _assinar(payload: dict) -> str:
    corpo = _b64(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    assinatura = hmac.new(settings.session_secret.encode("utf-8"), corpo.encode("ascii"), hashlib.sha256).digest()
    return f"{corpo}.{_b64(assinatura)}"


def _verificar(valor: str) -> dict | None:
    try:
        corpo, assinatura = valor.split(".", 1)
    except ValueError:
        return None
    esperada = hmac.new(settings.session_secret.encode("utf-8"), corpo.encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(_b64(esperada), assinatura):
        return None
    try:
        return json.loads(_b64_decode(corpo))
    except (ValueError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def criar_token_atributos(valores: list[int]) -> str:
    return _assinar({"valores": valores, "emitido_em": datetime.now(UTC).isoformat()})


def ler_token_atributos(token: str) -> list[int] | None:
    """`None` se o token for inválido, adulterado ou expirado — quem chama
    trata isso como "os valores não vieram daqui", não tenta adivinhar."""
    dados = _verificar(token)
    if dados is None:
        return None
    valores, emitido_em_str = dados.get("valores"), dados.get("emitido_em")
    if not isinstance(valores, list) or not all(isinstance(v, int) for v in valores) or not isinstance(
        emitido_em_str, str
    ):
        return None
    try:
        emitido_em = datetime.fromisoformat(emitido_em_str)
    except ValueError:
        return None
    if datetime.now(UTC) - emitido_em > _TTL_TOKEN_ATRIBUTOS:
        return None
    return valores
