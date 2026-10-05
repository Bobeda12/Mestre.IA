"""Cliente de chat com cadeia de fallback entre modelos e PROVEDORES (ADR-0008,
revisto pelo ADR-0024), com retry por erro transitório (`tenacity`).

Um SDK só (`openai`) fala com todo mundo: Groq, Gemini e outros provedores
compatíveis expõem o mesmo endpoint OpenAI-compatible, só o `base_url` (e a
chave) muda — um `openai.OpenAI(base_url=...)` por provedor, guardados em
`clients` por nome (`"groq"`, `"gemini"`). Cada elo de `settings.cadeia_<papel>`
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
import logging
import threading
import time
import weakref
from collections.abc import Iterator
from typing import Any, Literal

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

_ERROS_TRANSITORIOS = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
    # `InternalServerError` cobre qualquer status >= 500 (500/502/503/504) —
    # o SDK não distingue por código como faz para 4xx. Achado ao vivo: um
    # 503 de alta demanda do Gemini caía direto no `APIStatusError` genérico
    # e quebrava o turno sem nenhum retry.
    openai.InternalServerError,
)


class ErroMestre(Exception):
    """Erro ao consultar a IA, com uma mensagem já pronta para o jogador ler."""

    def __init__(self, mensagem: str) -> None:
        self.mensagem = mensagem
        super().__init__(mensagem)


def _chave_do_provedor(provedor: str) -> str | None:
    return {"groq": settings.groq_api_key, "gemini": settings.gemini_api_key}.get(provedor)


# Tempo limite de quem não passa por uma cadeia (chave do jogador, modelo
# fixo das avaliações). As cadeias usam `settings.timeouts_ia` por papel.
_TIMEOUT_PADRAO = 60.0


def _build_clients() -> dict[str, openai.OpenAI]:
    # max_retries=0 (herdado do ADR-0008, Etapa 6): o SDK retenta 429/5xx
    # sozinho por padrão, honrando Retry-After ANTES de qualquer exceção
    # chegar aqui — o que neutralizava a cadeia de fallback na prática
    # (achado ao vivo: uma chamada com ~3869s de latência presa num retry
    # interno enquanto a cota estava esgotada).
    #
    # `timeout` (05/10/2026): sem ele valia o padrão do SDK, 10 minutos. Uma
    # chamada mínima ao Gemini ficou 293 s pendurada antes de responder —
    # para o jogador, um turno travado.
    return {
        provedor: openai.OpenAI(api_key=chave, base_url=base_url, max_retries=0, timeout=_TIMEOUT_PADRAO)
        for provedor, base_url in _BASE_URLS.items()
        if (chave := _chave_do_provedor(provedor))
    }


clients = _build_clients()

# Pausa por instância de cliente e modelo: nenhuma chave ou texto de jogador é
# armazenado. Válida só neste processo; clientes de outras contas são independentes.
# Cada entrada é (até quando, motivo): "cota" (429) ou "sobrecarga" (5xx, timeout).
_pausas: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_pausas_lock = threading.Lock()

# Sobrecarga do provedor (503 "high demand") ou chamada que estourou o tempo:
# o modelo sai da fila por alguns minutos em vez de ser tentado de novo. No
# plano gratuito do Gemini há relatos de que o 503 também gasta a cota diária
# (20/dia nos Flash), então insistir custa duas vezes.
_PAUSA_SOBRECARGA = 180.0
_PAUSA_TIMEOUT = 60.0
# Cota diária esgotada. O corpo do 429 chegou a dizer "retry in 11h" e o
# mesmo modelo voltou a responder cerca de uma hora depois, então a pausa é
# de minutos: o bastante para não bater de novo a cada turno.
_PAUSA_COTA_DIARIA = 900.0


def _pausa(cliente, modelo: str) -> tuple[float, str]:
    with _pausas_lock:
        return _pausas.get(cliente, {}).get(modelo, (0.0, ""))


def _em_pausa(cliente, modelo: str) -> bool:
    return _pausa(cliente, modelo)[0] > time.monotonic()


def _registrar_pausa(cliente, modelo: str, erro: Exception) -> None:
    if isinstance(erro, openai.RateLimitError):
        motivo = "cota"
        if "PerDay" in str(getattr(erro, "body", "")):
            espera = _PAUSA_COTA_DIARIA
        else:
            try:
                espera = float(erro.response.headers.get("retry-after", "30"))
            except ValueError:
                espera = 30
            espera = max(1, min(120, espera))
    elif isinstance(erro, openai.APITimeoutError):
        motivo, espera = "sobrecarga", _PAUSA_TIMEOUT
    elif isinstance(erro, openai.InternalServerError):
        motivo, espera = "sobrecarga", _PAUSA_SOBRECARGA
    else:
        return
    with _pausas_lock:
        _pausas.setdefault(cliente, {})[modelo] = (time.monotonic() + espera, motivo)


# Contador local de chamadas por cliente e modelo, para a fila pular um
# modelo que já está no limite sem gastar uma chamada para descobrir (o 429
# só chega depois de bater). É uma estimativa: zera quando o processo
# reinicia e não enxerga outros processos com a mesma chave. Por isso ele
# só tira o modelo da frente da fila; o 429 continua sendo a verdade.
# Cada entrada: (momentos das chamadas no último minuto, dia, chamadas no dia).
_uso: weakref.WeakKeyDictionary = weakref.WeakKeyDictionary()
_uso_lock = threading.Lock()


def _dia_da_cota() -> int:
    # A cota diária do Gemini zera à meia-noite do Pacífico. UTC-8 fixo: no
    # horário de verão de lá o dia vira uma hora depois do real, o que só
    # deixa o contador conservador por uma hora.
    return int((time.time() - 8 * 3600) // 86400)


def _uso_atual(cliente, modelo: str) -> tuple[int, int]:
    """(chamadas no último minuto, chamadas no dia) deste cliente neste modelo."""
    with _uso_lock:
        momentos, dia, no_dia = _uso.get(cliente, {}).get(modelo, ((), 0, 0))
        agora = time.monotonic()
        return sum(1 for m in momentos if agora - m < 60), no_dia if dia == _dia_da_cota() else 0


def _contar_chamada(cliente, modelo: str) -> None:
    # Conta a tentativa, não só o sucesso: há relatos de que o 503 do Gemini
    # também desconta da cota diária, e errar para mais só adianta a troca
    # de modelo.
    with _uso_lock:
        momentos, dia, no_dia = _uso.setdefault(cliente, {}).get(modelo, ((), 0, 0))
        agora, hoje = time.monotonic(), _dia_da_cota()
        recentes = (*(m for m in momentos if agora - m < 60), agora)
        _uso[cliente][modelo] = (recentes, hoje, (no_dia if dia == hoje else 0) + 1)


def _no_limite(cliente, modelo: str) -> bool:
    limite = settings.limites_ia.get(modelo)
    if not limite:
        return False
    por_minuto, por_dia = _uso_atual(cliente, modelo)
    return por_minuto >= limite[0] or por_dia >= limite[1]


# Com menos que isto de prazo sobrando, nem vale abrir outra chamada.
_PRAZO_MINIMO = 3.0


def _uso_no_log(cliente, modelo: str) -> str:
    """"3/15min 120/500dia" — o uso contado aqui contra o limite configurado."""
    por_minuto, por_dia = _uso_atual(cliente, modelo)
    limite = settings.limites_ia.get(modelo)
    return f"{por_minuto}/{limite[0]}min {por_dia}/{limite[1]}dia" if limite else f"{por_minuto}min {por_dia}dia"


def _elos_dentro_do_prazo(papel: str) -> Iterator[tuple[str, str, Any, float]]:
    """Percorre `_elos_disponiveis(papel)` enquanto houver prazo total do
    papel (`settings.prazos_ia`), entregando também o tempo limite daquela
    chamada: o do papel ou o que resta do prazo, o que for menor.

    Achado ao vivo (05/10/2026): só com tempo limite por chamada, um prólogo
    levou 201 s — seis modelos falharam em fila e dois deles gastaram os
    60 s inteiros cada. O jogador espera a soma, não cada parcela."""
    limite = time.monotonic() + settings.prazos_ia[papel]
    for provedor, modelo, cliente in _elos_disponiveis(papel):
        restante = limite - time.monotonic()
        if restante < _PRAZO_MINIMO:
            logger.warning("ia papel=%s prazo total esgotado antes de %s", papel, modelo)
            return
        _contar_chamada(cliente, modelo)
        yield provedor, modelo, cliente, min(settings.timeouts_ia[papel], restante)


def _elos_disponiveis(papel: str) -> list[tuple[str, str, Any]]:
    """Elos da cadeia do papel que têm chave configurada, não estão em pausa
    e não chegaram ao limite no contador local (`_no_limite`). Se não sobrar
    NENHUM, devolve os que só estão fora por sobrecarga ou pelo contador:
    tentar um modelo que talvez já tenha voltado (ou cuja contagem local
    esteja errada para mais) é melhor do que falhar sem chamar ninguém. Os
    pausados por cota ficam de fora — ali o provedor já respondeu 429."""
    elos = [(provedor, modelo, clients[provedor]) for provedor, modelo in CADEIAS[papel] if provedor in clients]
    livres = [elo for elo in elos if not _em_pausa(elo[2], elo[1]) and not _no_limite(elo[2], elo[1])]
    if livres:
        return livres
    return [
        elo for elo in elos
        if not _em_pausa(elo[2], elo[1]) or _pausa(elo[2], elo[1])[1] == "sobrecarga"
    ]


def _parse_modelo(espec: str) -> tuple[str, str]:
    provedor, _, modelo = espec.partition(":")
    if not modelo:
        raise ValueError(f"Especificação de modelo inválida (esperado 'provedor:modelo'): {espec!r}")
    return provedor, modelo


logger = logging.getLogger(__name__)

# Um modelo por papel (ADR-0038): "volume" (turno de jogo), "destaque"
# (prólogo, morte, desfechos) e "fundo" (resumo da memória). As listas vêm
# de `settings.cadeia_<papel>`.
Papel = Literal["volume", "destaque", "fundo"]
CADEIAS: dict[str, list[tuple[str, str]]] = {
    "volume": [_parse_modelo(espec) for espec in settings.cadeia_volume],
    "destaque": [_parse_modelo(espec) for espec in settings.cadeia_destaque],
    "fundo": [_parse_modelo(espec) for espec in settings.cadeia_fundo],
}

_SEM_PROVEDOR = (
    "O mestre está sem acesso à IA — falta configurar ao menos uma chave de API "
    "no servidor (GROQ_API_KEY ou GEMINI_API_KEY)."
)


def _chamar_modelo(
    cliente: openai.OpenAI,
    provedor: str,
    modelo: str,
    msgs: list[dict],
    tools: list[dict] | None,
    tool_choice: str | dict,
    response_format: dict | None = None,
    stream: bool = False,
    papel: str | None = None,
    timeout: float | None = None,
) -> Any:
    kwargs: dict[str, Any] = {"model": modelo, "messages": msgs}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if papel is not None:
        # Os Gemini 3.x "pensam" antes de responder e isso não desliga, só
        # diminui. Só o Gemini recebe o parâmetro: nem todo modelo da Groq o aceita.
        esforco = settings.esforco_raciocinio.get(papel)
        if esforco and provedor == "gemini":
            kwargs["reasoning_effort"] = esforco
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


# Quem chama um modelo só (chave do jogador, modelo fixo das avaliações) não
# tem "próximo elo" para onde cair, então mantém o retry curto no mesmo
# modelo. As cadeias não usam isto: lá um erro pausa o modelo e segue a fila.
_chamar_modelo_com_retry = retry(
    stop=stop_after_attempt(2),
    wait=wait_exponential(multiplier=0.5, max=4),
    # 429 não se repete: o mesmo payload não repõe a cota.
    retry=retry_if_exception_type(tuple(e for e in _ERROS_TRANSITORIOS if e is not openai.RateLimitError)),
    reraise=True,
)(_chamar_modelo)


def chamar_modelo_unico(
    modelo_espec: str,
    msgs: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | dict = "auto",
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
        return _chamar_modelo_com_retry(cliente, provedor, modelo, msgs, tools, tool_choice, response_format)
    except _ERROS_TRANSITORIOS as e:
        raise ErroMestre(
            "A cota de uso da IA acabou por agora, o serviço está sobrecarregado, ou demorou demais."
        ) from e
    except openai.APIStatusError as e:
        raise ErroMestre(f"O serviço de IA recusou o pedido (código {e.status_code}).") from e


def chamar_com_fallback(
    msgs: list[dict],
    tools: list[dict] | None = None,
    tool_choice: str | dict = "auto",
    response_format: dict | None = None,
    papel: Papel = "volume",
) -> Any:
    """Tenta cada elo de `CADEIAS[papel]` em ordem, pulando provedor sem chave
    e modelo em pausa (ver `_elos_disponiveis`). Um erro transitório — cota,
    sobrecarga, tempo estourado — pausa aquele modelo e passa para o
    próximo, enquanto couber no prazo total do papel, sem repetir no mesmo: a fila tem vários modelos do mesmo
    provedor, cada um com cota própria, e no plano gratuito do Gemini
    insistir num 503 parece gastar a cota do dia (ADR-0038)."""
    if not clients:
        raise ErroMestre(_SEM_PROVEDOR)
    ultimo_erro: Exception | None = None
    for provedor, modelo, cliente, timeout in _elos_dentro_do_prazo(papel):
        try:
            resp = _chamar_modelo(
                cliente, provedor, modelo, msgs, tools, tool_choice, response_format, papel=papel, timeout=timeout
            )
            # Uma linha por chamada atendida: é o que permite somar, no
            # log, quantas chamadas um turno faz e em qual modelo caíram.
            logger.info(
                "ia papel=%s provedor=%s modelo=%s uso=%s", papel, provedor, modelo, _uso_no_log(cliente, modelo)
            )
            return resp
        except _ERROS_TRANSITORIOS as e:
            # Achado de uso (05/10/2026): este ramo era mudo — o jogador via
            # "todos os modelos falharam" e o log não dizia se era cota do
            # dia (429) ou sobrecarga (503).
            logger.warning(
                "provedor=%s modelo=%s transitorio=%s corpo=%s",
                provedor, modelo, type(e).__name__, str(getattr(e, "body", ""))[:300],
            )
            _registrar_pausa(cliente, modelo, e)
            ultimo_erro = e
            continue
        except openai.APIStatusError as e:
            # Fase 0 do plano "jogo completo" — o log do httpx só mostra o
            # status; o CORPO é o que diz se foi teto de tokens, chave
            # extra na mensagem ou uma chamada de ferramenta malformada
            # que o próprio modelo gerou (`tool_use_failed` na Groq).
            logger.warning(
                "provedor=%s modelo=%s status=%s corpo=%s", provedor, modelo, e.status_code, str(e.body)[:300]
            )
            ultimo_erro = e
            continue
    raise ErroMestre(
        "Todos os modelos configurados falharam ao responder. Tente de novo em instantes."
    ) from ultimo_erro


def _detalhe_erro_gemini(e: openai.APIStatusError) -> str:
    """O corpo de erro do Gemini costuma trazer uma mensagem melhor que a
    genérica do SDK (`e.message`) — por exemplo, qual modelo não foi
    encontrado. Usada só para compor o texto que o jogador lê; nunca para
    decidir o fluxo (isso continua sendo `e.status_code`)."""
    corpo = e.body
    if isinstance(corpo, dict):
        erro = corpo.get("error")
        if isinstance(erro, dict) and isinstance(erro.get("message"), str):
            return erro["message"]
    return e.message


def _mensagem_erro_byok(e: openai.APIStatusError, modelo: str) -> str:
    """Achado ao vivo (Etapa 15/rodada de conserto): a primeira chamada de
    um turno pode autenticar e funcionar, e só a segunda falhar (ver
    `agent_loop.py` — mensagem `content: null` que o Gemini rejeita) — um
    400 quase nunca é "a chave errada". Distinguir por `status_code` em vez
    de tratar todo `APIStatusError` como recusa de chave evita culpar a
    chave por um bug do lado do servidor."""
    if e.status_code in (401, 403):
        return "Sua chave foi recusada pelo Gemini — confira se ela está correta."
    if e.status_code == 404:
        return f"Sua chave não tem acesso ao modelo '{modelo}' (ou o modelo não existe mais no Gemini)."
    return f"O Gemini recusou a chamada (código {e.status_code}): {_detalhe_erro_gemini(e)}"


def validar_chave_usuario(api_key: str) -> None:
    """Rodada de conserto — chamada leve (`GET /models`, sem gerar texto
    nenhum) para o jogador saber, no momento em que cola a chave no menu de
    configurações, se ela é válida — em vez de descobrir no meio de uma
    cena, como acontecia antes (`MenuConfiguracao.tsx` não validava nada).
    Levanta `ErroMestre` pelo mesmo `_mensagem_erro_byok` das chamadas de
    verdade, então a mensagem de erro é consistente nos dois lugares."""
    cliente = openai.OpenAI(api_key=api_key, base_url=_BASE_URLS["gemini"], max_retries=0, timeout=_TIMEOUT_PADRAO)
    try:
        cliente.models.list()
    except _ERROS_TRANSITORIOS as e:
        raise ErroMestre("O Gemini demorou demais para responder, ou está sobrecarregado — tente de novo.") from e
    except openai.APIStatusError as e:
        raise ErroMestre(_mensagem_erro_byok(e, modelo="gemini-3.5-flash")) from e


def chamar_com_chave_usuario(
    msgs: list[dict],
    api_key: str,
    tools: list[dict] | None = None,
    tool_choice: str | dict = "auto",
    modelo: str = "gemini-3.5-flash",
    response_format: dict | None = None,
) -> Any:
    """BYOK (Etapa 15) — mesma forma de `chamar_modelo_unico`, mas o cliente
    é efêmero (chave do jogador, nunca guardada em `clients`) e sem cadeia
    de fallback: é só o Gemini, com a chave que ele forneceu. Erros viram
    `ErroMestre` com mensagens específicas ("sua chave..."), pra o router
    distinguir de uma falha da chave do servidor e não cair num fallback
    silencioso que gastaria a cota do servidor sem o jogador perceber.

    `response_format` (rodada de conserto) — as chamadas de JSON solto do
    prólogo/epitáfio (`services/narrator.py`) passaram a poder usar a
    chave do jogador também; sem este parâmetro elas caíam sempre na conta
    do servidor, mesmo com "Traga sua própria chave" ativado."""
    cliente = openai.OpenAI(api_key=api_key, base_url=_BASE_URLS["gemini"], max_retries=0, timeout=_TIMEOUT_PADRAO)
    try:
        return _chamar_modelo_com_retry(cliente, "gemini", modelo, msgs, tools, tool_choice, response_format)
    except _ERROS_TRANSITORIOS as e:
        raise ErroMestre(
            "Sua chave bateu no limite de uso, o Gemini está sobrecarregado, ou demorou demais para responder."
        ) from e
    except openai.APIStatusError as e:
        raise ErroMestre(_mensagem_erro_byok(e, modelo)) from e


def chamar_stream_com_chave_usuario(
    msgs: list[dict],
    api_key: str,
    tools: list[dict] | None = None,
    tool_choice: str | dict = "auto",
    modelo: str = "gemini-3.5-flash",
) -> Iterator[Any]:
    """Versão em streaming de `chamar_com_chave_usuario`. Sem cadeia pra
    cair — qualquer falha (antes ou depois do primeiro chunk) vira
    `ErroMestre` direto, nunca um fallback silencioso para outro provedor
    ou pra chave do servidor (ver docstring acima)."""
    cliente = openai.OpenAI(api_key=api_key, base_url=_BASE_URLS["gemini"], max_retries=0, timeout=_TIMEOUT_PADRAO)
    try:
        stream = _chamar_modelo_com_retry(cliente, "gemini", modelo, msgs, tools, tool_choice, stream=True)
        yield from stream
    except _ERROS_TRANSITORIOS as e:
        raise ErroMestre(
            "Sua chave bateu no limite de uso, o Gemini está sobrecarregado, ou a conexão caiu no meio da resposta."
        ) from e
    except openai.APIStatusError as e:
        raise ErroMestre(_mensagem_erro_byok(e, modelo)) from e


def chamar_stream_com_fallback(
    msgs: list[dict], tools: list[dict] | None = None, tool_choice: str | dict = "auto", papel: Papel = "volume"
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
    for provedor, modelo, cliente, timeout in _elos_dentro_do_prazo(papel):
        try:
            stream = _chamar_modelo(
                cliente, provedor, modelo, msgs, tools, tool_choice, stream=True, papel=papel, timeout=timeout
            )
        except _ERROS_TRANSITORIOS as e:
            logger.warning(
                "provedor=%s modelo=%s transitorio=%s corpo=%s",
                provedor, modelo, type(e).__name__, str(getattr(e, "body", ""))[:300],
            )
            _registrar_pausa(cliente, modelo, e)
            ultimo_erro = e
            continue
        except openai.APIStatusError as e:
            logger.warning(
                "provedor=%s modelo=%s status=%s corpo=%s", provedor, modelo, e.status_code, str(e.body)[:300]
            )
            ultimo_erro = e
            continue
        logger.info(
            "ia papel=%s provedor=%s modelo=%s uso=%s stream", papel, provedor, modelo, _uso_no_log(cliente, modelo)
        )

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
                _registrar_pausa(cliente, modelo, e)
                if comprometido:
                    raise ErroMestre("A conexão com a IA caiu no meio da resposta.") from e
                ultimo_erro = e
                continue

    raise ErroMestre(
        "Todos os modelos configurados falharam ao responder. Tente de novo em instantes."
    ) from ultimo_erro
