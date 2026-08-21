"""Cliente da Groq com cadeia de fallback entre modelos (ADR-0008) e retry
com backoff para erro transitório (`tenacity`).

`ErroMestre` mora aqui, não em `services/narrator.py` como antes da Etapa 4:
é o tipo de erro do cliente de LLM, não uma regra de narrativa — outros
serviços (`services/agent_loop.py`) precisam levantá-lo sem importar de
`services/narrator.py`, o que violaria a direção de dependência do
ADR-0003 (routers → services → domain/infra)."""

from collections.abc import Iterator
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
    # max_retries=0 (Etapa 6, evals/): o SDK da Groq retenta 429/5xx sozinho
    # por padrão (max_retries=2), honrando o header Retry-After do servidor
    # ANTES de qualquer exceção chegar ao nosso código — descoberto rodando
    # evals/run_eval.py --bake-off de verdade: uma chamada devolveu com
    # ~3869s de latência (o SDK ficou preso num retry interno enquanto a
    # cota estava esgotada). Isso também neutralizava a cadeia de fallback
    # do ADR-0008 na prática: `chamar_com_fallback` só troca de modelo
    # quando VÊ um `RateLimitError`, mas o SDK engolia esse erro por até
    # ~64 minutos antes de deixá-lo passar. Com max_retries=0, o `tenacity`
    # (rápido, no máx. ~4s) + a troca de modelo é a única política de
    # retry — a que já está documentada e testada.
    return groq.Groq(api_key=settings.groq_api_key, max_retries=0)


client = _build_client()


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type(_ERROS_TRANSITORIOS),
    reraise=True,
)
def _chamar_modelo(
    modelo: str,
    msgs: list[dict],
    tools: list[dict] | None,
    tool_choice: str,
    response_format: dict | None = None,
    stream: bool = False,
) -> Any:
    kwargs: dict[str, Any] = {"model": modelo, "messages": msgs}
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = tool_choice
    if response_format:
        kwargs["response_format"] = response_format
    if stream:
        kwargs["stream"] = True
    return client.chat.completions.create(**kwargs)  # type: ignore[union-attr]


def chamar_modelo_unico(
    modelo: str,
    msgs: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    response_format: dict | None = None,
) -> Any:
    """Chama um único modelo específico, sem a cadeia de fallback — usado
    pelo resumo rolante (Etapa 5, services/memory.py), que aceita usar
    sempre o modelo mais barato e falhar sem alternativa: comprimir memória
    não vale o custo de escalar para um modelo caro, e uma falha aqui não
    derruba o turno (o resumo antigo continua valendo).

    `tools`/`tool_choice` foram adicionados na Etapa 6 (evals/) para o
    bake-off de modelos poder rodar o turno inteiro (com ferramentas) contra
    um modelo específico, em vez de só a cadeia de fallback — que esconde
    qual modelo respondeu de fato."""
    if not client:
        raise ErroMestre(
            "O mestre está sem acesso à IA — falta configurar a chave da Groq no servidor (GROQ_API_KEY)."
        )
    try:
        return _chamar_modelo(modelo, msgs, tools, tool_choice, response_format)
    except _ERROS_TRANSITORIOS as e:
        raise ErroMestre("A cota de uso da IA acabou por agora, ou o serviço demorou demais.") from e
    except groq.APIStatusError as e:
        raise ErroMestre(f"O serviço de IA recusou o pedido (código {e.status_code}).") from e


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


def chamar_stream_com_fallback(
    msgs: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto"
) -> Iterator[Any]:
    """Versão em streaming de `chamar_com_fallback` (Etapa 7, ADR-0012).

    A cadeia de fallback do ADR-0008 troca de modelo depois de um erro —
    seguro quando nada foi mandado pro cliente ainda. Streaming quebra essa
    suposição: depois que o primeiro chunk sai daqui, o chamador (`agent_loop.
    executar_turno_stream`) já pode ter repassado texto pro jogador, e trocar
    de modelo no meio geraria uma resposta costurada de dois "narradores"
    diferentes, incoerente.

    Por isso o fallback aqui só vale **antes do primeiro chunk** — troca de
    modelo se a conexão falhar na hora de abrir o stream (rate limit, 4xx/5xx,
    timeout). Depois do primeiro chunk, a stream está "comprometida" com
    aquele modelo: uma falha a partir daí vira `ErroMestre` (o router traduz
    isso num evento SSE `error`), não uma troca silenciosa."""
    if not client:
        raise ErroMestre(
            "O mestre está sem acesso à IA — falta configurar a chave da Groq no servidor (GROQ_API_KEY)."
        )
    ultimo_erro: Exception | None = None
    for modelo in MODELOS:
        try:
            stream = _chamar_modelo(modelo, msgs, tools, tool_choice, stream=True)
        except _ERROS_TRANSITORIOS as e:
            ultimo_erro = e
            continue
        except groq.APIStatusError as e:
            ultimo_erro = e
            continue

        comprometido = False
        try:
            for chunk in stream:
                comprometido = True
                yield chunk
            return
        except _ERROS_TRANSITORIOS as e:
            if comprometido:
                raise ErroMestre("A conexão com a IA caiu no meio da resposta.") from e
            ultimo_erro = e
            continue

    raise ErroMestre(
        "Todos os modelos configurados falharam ao responder. Tente de novo em instantes."
    ) from ultimo_erro
