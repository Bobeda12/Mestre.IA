"""Cliente da Groq com cadeia de fallback entre modelos (ADR-0008) e retry
com backoff para erro transitório (`tenacity`).

`ErroMestre` mora aqui, não em `services/narrator.py` como antes da Etapa 4:
é o tipo de erro do cliente de LLM, não uma regra de narrativa — outros
serviços (`services/agent_loop.py`) precisam levantá-lo sem importar de
`services/narrator.py`, o que violaria a direção de dependência do
ADR-0003 (routers → services → domain/infra)."""

from typing import Any

import groq
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infra.settings import settings

MODEL_NAME = settings.model_name
MODELOS = [settings.model_name, *settings.modelos_fallback]

_ERROS_TRANSITORIOS = (groq.RateLimitError, groq.APITimeoutError, groq.APIConnectionError)


class ErroMestre(Exception):
    """Erro ao consultar a IA, com uma mensagem já pronta para o jogador ler."""

    def __init__(self, mensagem: str) -> None:
        self.mensagem = mensagem
        super().__init__(mensagem)


def _build_client() -> groq.Groq | None:
    if not settings.groq_api_key:
        return None
    return groq.Groq(api_key=settings.groq_api_key)


client = _build_client()


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type(_ERROS_TRANSITORIOS),
    reraise=True,
)
def _chamar_modelo(
    modelo: str, msgs: list[dict], tools: list[dict] | None, tool_choice: str
) -> Any:
    kwargs: dict[str, Any] = {"model": modelo, "messages": msgs}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    return client.chat.completions.create(**kwargs)  # type: ignore[union-attr]


def chamar_com_fallback(msgs: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto") -> Any:
    """Tenta cada modelo de `MODELOS` em ordem. Por modelo, `tenacity` cobre
    até 2 tentativas com backoff curto para erro transitório (rate limit,
    timeout, conexão) antes de desistir dele e cair para o próximo — é isto
    que transforma o limite de free tier por modelo da Groq numa vantagem de
    arquitetura em vez de um turno perdido (ADR-0008)."""
    if not client:
        raise ErroMestre(
            "O mestre está sem acesso à IA — falta configurar a chave da Groq no servidor (GROQ_API_KEY)."
        )
    ultimo_erro: Exception | None = None
    for modelo in MODELOS:
        try:
            return _chamar_modelo(modelo, msgs, tools, tool_choice)
        except _ERROS_TRANSITORIOS as e:
            ultimo_erro = e
            continue
        except groq.APIStatusError as e:
            ultimo_erro = e
            continue
    raise ErroMestre(
        "Todos os modelos configurados falharam ao responder. Tente de novo em instantes."
    ) from ultimo_erro
