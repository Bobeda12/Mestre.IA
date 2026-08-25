"""Cliente de chat com cadeia de fallback entre modelos e PROVEDORES (ADR-0008,
revisto pelo ADR-0024), com retry por erro transitório (`tenacity`).

Um SDK só (`openai`) fala com todo mundo: Groq, Gemini e outros provedores
compatíveis expõem o mesmo endpoint OpenAI-compatible, só o `base_url` (e a
chave) muda — um `openai.OpenAI(base_url=...)` por provedor, guardados em
`clients` por nome (`"groq"`, `"gemini"`). Cada elo de `settings.cadeia_llm`
é uma string `"provedor:modelo"` (ver `_parse_modelo`); atravessar provedores
é o que transforma a cota diária *por conta* de cada um numa soma, não uma
disputa pelo mesmo teto — o objetivo original do ADR-0008 ("por que não um
segundo provedor ainda"), agora resolvido.

`ErroMestre` mora aqui, não em `services/narrator.py` como antes da Etapa 4:
é o tipo de erro do cliente de LLM, não uma regra de narrativa — outros
serviços (`services/agent_loop.py`) precisam levantá-lo sem importar de
`services/narrator.py`, o que violaria a direção de dependência do
ADR-0003 (routers → services → domain/infra)."""

import contextlib
import time
from collections.abc import Iterator
from typing import Any

import openai
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.infra.settings import settings
from app.infra.tracing import langfuse_client

# Cada provedor compatível com o formato OpenAI só precisa de um base_url —
# a chave (se configurada) decide se ele entra em `clients` abaixo.
_BASE_URLS: dict[str, str] = {
    "groq": "https://api.groq.com/openai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai/",
}

_ERROS_TRANSITORIOS = (openai.RateLimitError, openai.APITimeoutError, openai.APIConnectionError)


class ErroMestre(Exception):
    """Erro ao consultar a IA, com uma mensagem já pronta para o jogador ler."""

    def __init__(self, mensagem: str) -> None:
        self.mensagem = mensagem
        super().__init__(mensagem)


def _chave_do_provedor(provedor: str) -> str | None:
    return {"groq": settings.groq_api_key, "gemini": settings.gemini_api_key}.get(provedor)


def _build_clients() -> dict[str, openai.OpenAI]:
    # max_retries=0 (herdado do ADR-0008, Etapa 6): o SDK retenta 429/5xx
    # sozinho por padrão, honrando Retry-After ANTES de qualquer exceção
    # chegar aqui — o que neutralizava a cadeia de fallback na prática
    # (achado ao vivo: uma chamada com ~3869s de latência presa num retry
    # interno enquanto a cota estava esgotada). `tenacity` (rápido, no
    # máx. ~4s) + a troca de modelo/provedor é a única política de retry.
    return {
        provedor: openai.OpenAI(api_key=chave, base_url=base_url, max_retries=0)
        for provedor, base_url in _BASE_URLS.items()
        if (chave := _chave_do_provedor(provedor))
    }


clients = _build_clients()


def _parse_modelo(espec: str) -> tuple[str, str]:
    provedor, _, modelo = espec.partition(":")
    if not modelo:
        raise ValueError(f"Especificação de modelo inválida (esperado 'provedor:modelo'): {espec!r}")
    return provedor, modelo


CADEIA: list[tuple[str, str]] = [_parse_modelo(espec) for espec in settings.cadeia_llm]

_SEM_PROVEDOR = (
    "O mestre está sem acesso à IA — falta configurar ao menos uma chave de API "
    "no servidor (GROQ_API_KEY ou GEMINI_API_KEY)."
)


@retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, max=4),
    retry=retry_if_exception_type(_ERROS_TRANSITORIOS),
    reraise=True,
)
def _chamar_modelo(
    cliente: openai.OpenAI,
    provedor: str,
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
        # Sem `stream_options={"include_usage": True}` aqui de propósito: o
        # SDK (0.37 da Groq, achado que sobrevive à troca pro `openai`) não
        # aceitava esse parâmetro contra o endpoint da Groq — quebrava toda
        # chamada em streaming com TypeError, só apareceu testando ao vivo
        # contra a API de verdade, não em teste nenhum.
        # `chamar_stream_com_fallback` não reporta tokens ao Langfuse por
        # isso; o resto da trace (modelo, provedor, texto, latência)
        # continua valendo.
        kwargs["stream"] = True
        return cliente.chat.completions.create(**kwargs)

    # Etapa 9: uma trace por chamada de verdade ao modelo — não por turno,
    # porque um turno com ferramentas encadeia várias chamadas (ADR-0007).
    # `app/infra/tracing.py` é `None` sem conta no Langfuse configurada,
    # aqui só isso já desliga o tracing (mesmo padrão de `clients`/chaves).
    if langfuse_client is None:
        return cliente.chat.completions.create(**kwargs)

    inicio = time.monotonic()
    with langfuse_client.start_as_current_observation(
        as_type="generation", name=f"{provedor}-chat", model=modelo, input=msgs
    ) as geracao:
        resp = cliente.chat.completions.create(**kwargs)
        uso = getattr(resp, "usage", None)
        geracao.update(
            output=resp.choices[0].message.content if resp.choices else None,
            usage_details={"input": uso.prompt_tokens, "output": uso.completion_tokens} if uso else None,
            # `provedor` na metadata (não só no nome da observação) é o que
            # permite somar tokens/custo POR PROVEDOR no Langfuse — a
            # medição que falta hoje para `teto_turnos_conta` deixar de ser
            # um chute (ver ADR-0024, "Como saber que erramos").
            metadata={"latencia_s": round(time.monotonic() - inicio, 3), "provedor": provedor},
        )
    return resp


def chamar_modelo_unico(
    modelo_espec: str,
    msgs: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    response_format: dict | None = None,
) -> Any:
    """Chama um único modelo específico (`"provedor:modelo"`), sem a cadeia
    de fallback — usado pelo resumo rolante e pelo LLM-as-judge
    (`settings.modelo_barato`), que aceitam usar sempre o mesmo modelo
    barato e falhar sem alternativa: nenhum dos dois vale o custo de
    escalar para o resto da cadeia, e uma falha aqui não derruba o turno
    (o resumo antigo continua valendo; o juiz conta como parse inválido).

    `tools`/`tool_choice` foram adicionados na Etapa 6 (evals/) para o
    bake-off de modelos poder rodar o turno inteiro (com ferramentas) contra
    um modelo específico, em vez de só a cadeia de fallback — que esconde
    qual modelo respondeu de fato."""
    provedor, modelo = _parse_modelo(modelo_espec)
    cliente = clients.get(provedor)
    if cliente is None:
        raise ErroMestre(
            f"O provedor '{provedor}' não está configurado (falta a chave de API correspondente no servidor)."
        )
    try:
        return _chamar_modelo(cliente, provedor, modelo, msgs, tools, tool_choice, response_format)
    except _ERROS_TRANSITORIOS as e:
        raise ErroMestre("A cota de uso da IA acabou por agora, ou o serviço demorou demais.") from e
    except openai.APIStatusError as e:
        raise ErroMestre(f"O serviço de IA recusou o pedido (código {e.status_code}).") from e


def chamar_com_fallback(msgs: list[dict], tools: list[dict] | None = None, tool_choice: str = "auto") -> Any:
    """Tenta cada elo de `CADEIA` em ordem, pulando qualquer provedor sem
    chave configurada. Por elo, `tenacity` cobre até 2 tentativas com
    backoff curto para erro transitório (rate limit, timeout, conexão)
    antes de desistir dele e cair para o próximo — é isto que transforma o
    limite de free tier de CADA PROVEDOR numa vantagem de arquitetura em
    vez de um turno perdido (ADR-0008/ADR-0024)."""
    if not clients:
        raise ErroMestre(_SEM_PROVEDOR)
    ultimo_erro: Exception | None = None
    for provedor, modelo in CADEIA:
        cliente = clients.get(provedor)
        if cliente is None:
            continue  # provedor sem chave configurada — pulado, não é uma falha
        try:
            return _chamar_modelo(cliente, provedor, modelo, msgs, tools, tool_choice)
        except _ERROS_TRANSITORIOS as e:
            ultimo_erro = e
            continue
        except openai.APIStatusError as e:
            ultimo_erro = e
            continue
    raise ErroMestre(
        "Todos os modelos configurados falharam ao responder. Tente de novo em instantes."
    ) from ultimo_erro


def chamar_com_chave_usuario(
    msgs: list[dict],
    api_key: str,
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    modelo: str = "gemini-3.5-flash",
) -> Any:
    """BYOK (Etapa 15) — mesma forma de `chamar_modelo_unico`, mas o cliente
    é efêmero (chave do jogador, nunca guardada em `clients`) e sem cadeia
    de fallback: é só o Gemini, com a chave que ele forneceu. Erros viram
    `ErroMestre` com mensagens específicas ("sua chave..."), pra o router
    distinguir de uma falha da chave do servidor e não cair num fallback
    silencioso que gastaria a cota do servidor sem o jogador perceber."""
    cliente = openai.OpenAI(api_key=api_key, base_url=_BASE_URLS["gemini"], max_retries=0)
    try:
        return _chamar_modelo(cliente, "gemini", modelo, msgs, tools, tool_choice)
    except openai.AuthenticationError as e:
        raise ErroMestre("Sua chave foi recusada pelo Gemini — confira se ela está correta.") from e
    except _ERROS_TRANSITORIOS as e:
        raise ErroMestre("Sua chave bateu no limite de uso, ou o Gemini demorou demais para responder.") from e
    except openai.APIStatusError as e:
        raise ErroMestre(f"Sua chave foi recusada pelo Gemini (código {e.status_code}).") from e


def chamar_stream_com_chave_usuario(
    msgs: list[dict],
    api_key: str,
    tools: list[dict] | None = None,
    tool_choice: str = "auto",
    modelo: str = "gemini-3.5-flash",
) -> Iterator[Any]:
    """Versão em streaming de `chamar_com_chave_usuario`. Sem cadeia pra
    cair — qualquer falha (antes ou depois do primeiro chunk) vira
    `ErroMestre` direto, nunca um fallback silencioso para outro provedor
    ou pra chave do servidor (ver docstring acima)."""
    cliente = openai.OpenAI(api_key=api_key, base_url=_BASE_URLS["gemini"], max_retries=0)
    try:
        stream = _chamar_modelo(cliente, "gemini", modelo, msgs, tools, tool_choice, stream=True)
        yield from stream
    except openai.AuthenticationError as e:
        raise ErroMestre("Sua chave foi recusada pelo Gemini — confira se ela está correta.") from e
    except _ERROS_TRANSITORIOS as e:
        raise ErroMestre("Sua chave bateu no limite de uso, ou a conexão caiu no meio da resposta.") from e
    except openai.APIStatusError as e:
        raise ErroMestre(f"Sua chave foi recusada pelo Gemini (código {e.status_code}).") from e


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
    modelo (ou provedor) se a conexão falhar na hora de abrir o stream (rate
    limit, 4xx/5xx, timeout). Depois do primeiro chunk, a stream está
    "comprometida" com aquele modelo: uma falha a partir daí vira `ErroMestre`
    (o router traduz isso num evento SSE `error`), não uma troca silenciosa."""
    if not clients:
        raise ErroMestre(_SEM_PROVEDOR)
    ultimo_erro: Exception | None = None
    for provedor, modelo in CADEIA:
        cliente = clients.get(provedor)
        if cliente is None:
            continue
        try:
            stream = _chamar_modelo(cliente, provedor, modelo, msgs, tools, tool_choice, stream=True)
        except _ERROS_TRANSITORIOS as e:
            ultimo_erro = e
            continue
        except openai.APIStatusError as e:
            ultimo_erro = e
            continue

        comprometido = False
        pedacos: list[str] = []
        uso: Any = None
        inicio = time.monotonic()
        # Etapa 9: mesma trace por chamada de `_chamar_modelo`, só que aqui a
        # chamada só termina quando o stream inteiro é consumido — por isso
        # o `with` envolve o `for` (e não só a abertura da conexão).
        gerenciador = (
            langfuse_client.start_as_current_observation(
                as_type="generation", name=f"{provedor}-chat-stream", model=modelo, input=msgs
            )
            if langfuse_client is not None
            else contextlib.nullcontext()
        )
        with gerenciador as geracao:
            try:
                for chunk in stream:
                    comprometido = True
                    # `getattr` em cascata (Etapa 9): evita depender do
                    # formato exato do objeto de chunk — os testes usam
                    # dublês simples (strings) no lugar do chunk real da
                    # API, e a extração de texto/uso é só para a trace,
                    # nunca deve derrubar o turno se o formato não bater.
                    choices = getattr(chunk, "choices", None)
                    delta = getattr(choices[0], "delta", None) if choices else None
                    if delta is not None and getattr(delta, "content", None):
                        pedacos.append(delta.content)
                    if getattr(chunk, "usage", None):
                        uso = chunk.usage
                    yield chunk
                if geracao is not None:
                    geracao.update(
                        output="".join(pedacos),
                        usage_details={"input": uso.prompt_tokens, "output": uso.completion_tokens} if uso else None,
                        metadata={"latencia_s": round(time.monotonic() - inicio, 3), "provedor": provedor},
                    )
                return
            except _ERROS_TRANSITORIOS as e:
                if comprometido:
                    raise ErroMestre("A conexão com a IA caiu no meio da resposta.") from e
                ultimo_erro = e
                continue

    raise ErroMestre(
        "Todos os modelos configurados falharam ao responder. Tente de novo em instantes."
    ) from ultimo_erro
