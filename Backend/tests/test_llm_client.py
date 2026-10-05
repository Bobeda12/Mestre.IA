"""Testa app/infra/llm_client.py — a cadeia de fallback entre modelos e
provedores (ADR-0008/ADR-0024) e o retry por erro transitório, sem chamar
nenhuma API de verdade. `httpx.Request`/`Response` reais (sem rede) são o
jeito mais simples de montar um `openai.RateLimitError` de verdade — o SDK
exige os dois no construtor."""

import httpx
import openai
import pytest
import tenacity

from app.infra import llm_client
from app.infra.llm_client import (
    ErroMestre,
    chamar_com_chave_usuario,
    chamar_com_fallback,
    chamar_stream_com_chave_usuario,
    chamar_stream_com_fallback,
    validar_chave_usuario,
)


def _erro_rate_limit() -> Exception:
    req = httpx.Request("POST", "https://example.com/x")
    resp = httpx.Response(429, request=req)
    import openai

    return openai.RateLimitError("cota estourada", response=resp, body=None)


def _erro_autenticacao() -> Exception:
    req = httpx.Request("POST", "https://example.com/x")
    resp = httpx.Response(401, request=req)
    return openai.AuthenticationError("chave inválida", response=resp, body=None)


def _erro_status(codigo: int, body: dict | None = None) -> Exception:
    req = httpx.Request("POST", "https://example.com/x")
    resp = httpx.Response(codigo, request=req)
    return openai.APIStatusError(f"erro {codigo}", response=resp, body=body)


def _erro_servidor(codigo: int = 503) -> Exception:
    # `InternalServerError` é o que o SDK levanta de verdade pra qualquer
    # status >= 500 — usado nos testes que provam que 503 (alta demanda)
    # agora é tratado como erro transitório, não como `APIStatusError` cru.
    req = httpx.Request("POST", "https://example.com/x")
    resp = httpx.Response(codigo, request=req)
    return openai.InternalServerError(f"erro {codigo}", response=resp, body=None)


class _FakeCompletions:
    def __init__(self, comportamento: dict[str, list]) -> None:
        self._comportamento = comportamento
        self.chamadas: list[str] = []

    def create(self, model, messages, **kwargs):
        self.chamadas.append(model)
        fila = self._comportamento.get(model, [])
        if not fila:
            raise AssertionError(f"chamada inesperada para o modelo '{model}'")
        proximo = fila.pop(0)
        if isinstance(proximo, Exception):
            raise proximo
        return proximo


class _FakeClient:
    def __init__(self, comportamento: dict[str, list]) -> None:
        self.chat = type("Chat", (), {"completions": _FakeCompletions(comportamento)})()


def _fake_clients(comportamento: dict[str, list]) -> tuple[dict[str, object], _FakeClient]:
    """Um `_FakeClient` só, registrado sob todo provedor que aparece em
    `llm_client.CADEIAS` — os testes indexam `comportamento` pelo nome
    (bare) do modelo, não por provedor; o provedor só decide qual entrada
    de `clients` o código de produção resolve, o dublê não precisa
    distinguir isso para os cenários testados aqui."""
    fake = _FakeClient(comportamento)
    provedores = {provedor for provedor, _ in llm_client.CADEIAS["volume"]}
    return dict.fromkeys(provedores, fake), fake


@pytest.fixture(autouse=True)
def _sem_espera_entre_tentativas(monkeypatch):
    # Mesmo backoff exponencial que roda em produção, mas sem esperar de
    # verdade — senão cada teste de fallback esgotado levaria segundos.
    monkeypatch.setattr(llm_client._chamar_modelo_com_retry.retry, "wait", tenacity.wait_none())  # type: ignore[attr-defined]


def test_sem_client_levanta_erro_mestre_sem_chamar_nada(monkeypatch):
    monkeypatch.setattr(llm_client, "clients", {})
    with pytest.raises(ErroMestre, match="GROQ_API_KEY"):
        chamar_com_fallback([{"role": "user", "content": "oi"}])


def test_rate_limit_cai_para_proximo_sem_repetir_payload(monkeypatch):
    modelo_1, modelo_2 = llm_client.CADEIAS["volume"][0][1], llm_client.CADEIAS["volume"][1][1]
    resultado_ok = object()
    clients, fake = _fake_clients({modelo_1: [_erro_rate_limit(), _erro_rate_limit()], modelo_2: [resultado_ok]})
    monkeypatch.setattr(llm_client, "clients", clients)

    resultado = chamar_com_fallback([{"role": "user", "content": "oi"}])

    assert resultado is resultado_ok
    assert fake.chat.completions.chamadas == [modelo_1, modelo_2]


def _erro_cota_diaria() -> Exception:
    # Corpo real capturado do Gemini em 05/10/2026 (encurtado).
    import openai

    req = httpx.Request("POST", "https://example.com/x")
    corpo = [{"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "details": [
        {"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]}
    ]}}]
    return openai.RateLimitError("cota do dia", response=httpx.Response(429, request=req), body=corpo)


def _erro_timeout() -> Exception:
    import openai

    return openai.APITimeoutError(request=httpx.Request("POST", "https://example.com/x"))


def test_503_pausa_o_modelo_e_segue_para_o_proximo_sem_repetir(monkeypatch):
    # Antes o 503 era repetido no mesmo modelo. No plano gratuito do Gemini
    # há relatos de que cada 503 gasta a cota do dia (20 nos Flash), então
    # insistir custa duas vezes: o modelo sai da fila por alguns minutos.
    modelo_1, modelo_2 = llm_client.CADEIAS["volume"][0][1], llm_client.CADEIAS["volume"][1][1]
    agora = [100.0]
    monkeypatch.setattr(llm_client.time, "monotonic", lambda: agora[0])
    clients, fake = _fake_clients({modelo_1: [_erro_servidor(503), "voltou"], modelo_2: ["ok", "ok"]})
    monkeypatch.setattr(llm_client, "clients", clients)

    assert chamar_com_fallback([]) == "ok"
    assert chamar_com_fallback([]) == "ok"
    assert fake.chat.completions.chamadas == [modelo_1, modelo_2, modelo_2]

    agora[0] += llm_client._PAUSA_SOBRECARGA + 1
    assert chamar_com_fallback([]) == "voltou"


def test_tempo_estourado_pausa_o_modelo(monkeypatch):
    # Achado ao vivo (05/10/2026): uma chamada mínima ficou 293 s pendurada.
    modelo_1, modelo_2 = llm_client.CADEIAS["volume"][0][1], llm_client.CADEIAS["volume"][1][1]
    clients, fake = _fake_clients({modelo_1: [_erro_timeout()], modelo_2: ["ok", "ok"]})
    monkeypatch.setattr(llm_client, "clients", clients)

    assert chamar_com_fallback([]) == "ok"
    assert chamar_com_fallback([]) == "ok"
    assert fake.chat.completions.chamadas == [modelo_1, modelo_2, modelo_2]


def test_cota_diaria_esgotada_pausa_por_mais_tempo_que_a_do_minuto(monkeypatch):
    agora = [100.0]
    monkeypatch.setattr(llm_client.time, "monotonic", lambda: agora[0])
    cliente = _FakeClient({})
    llm_client._registrar_pausa(cliente, "do-minuto", _erro_rate_limit())
    llm_client._registrar_pausa(cliente, "do-dia", _erro_cota_diaria())

    agora[0] += 121  # a pausa de cota por minuto nunca passa de 120 s
    assert not llm_client._em_pausa(cliente, "do-minuto")
    assert llm_client._em_pausa(cliente, "do-dia")

    agora[0] += llm_client._PAUSA_COTA_DIARIA
    assert not llm_client._em_pausa(cliente, "do-dia")


def test_todos_em_pausa_por_sobrecarga_ainda_sao_tentados(monkeypatch):
    # Se a fila inteira está pausada, tentar um modelo que talvez já tenha
    # voltado é melhor do que falhar sem chamar ninguém.
    monkeypatch.setitem(llm_client.CADEIAS, "volume", [("gemini", "a"), ("gemini", "b")])
    fake = _FakeClient({"a": [_erro_servidor(503), "voltou"], "b": [_erro_servidor(503)]})
    monkeypatch.setattr(llm_client, "clients", {"gemini": fake})

    with pytest.raises(ErroMestre, match="Todos os modelos"):
        chamar_com_fallback([])

    assert chamar_com_fallback([]) == "voltou"
    assert fake.chat.completions.chamadas == ["a", "b", "a"]


def test_todos_em_pausa_por_cota_falham_sem_gastar_chamada(monkeypatch):
    monkeypatch.setitem(llm_client.CADEIAS, "volume", [("gemini", "a")])
    fake = _FakeClient({"a": [_erro_cota_diaria(), "nunca chega aqui"]})
    monkeypatch.setattr(llm_client, "clients", {"gemini": fake})

    for _ in range(2):
        with pytest.raises(ErroMestre, match="Todos os modelos"):
            chamar_com_fallback([])

    assert fake.chat.completions.chamadas == ["a"]


def _cadeia_ab(monkeypatch, limites: dict[str, list[int]], comportamento: dict[str, list]):
    from app.infra.settings import settings

    monkeypatch.setitem(llm_client.CADEIAS, "volume", [("gemini", "a"), ("gemini", "b")])
    monkeypatch.setattr(settings, "limites_ia", limites)
    fake = _FakeClient(comportamento)
    monkeypatch.setattr(llm_client, "clients", {"gemini": fake})
    return fake


def test_contador_pula_modelo_no_limite_por_minuto_sem_gastar_chamada(monkeypatch):
    # Antes o servidor só descobria o limite batendo no 429 — o que gasta
    # uma chamada e, no turno, alguns segundos do jogador.
    agora = [1000.0]
    monkeypatch.setattr(llm_client.time, "monotonic", lambda: agora[0])
    fake = _cadeia_ab(monkeypatch, {"a": [2, 500]}, {"a": ["a1", "a2", "a3"], "b": ["b1"]})

    assert [chamar_com_fallback([]) for _ in range(3)] == ["a1", "a2", "b1"]
    assert fake.chat.completions.chamadas == ["a", "a", "b"]

    agora[0] += 61  # o minuto virou: "a" volta para a frente da fila
    assert chamar_com_fallback([]) == "a3"


def test_contador_pula_modelo_no_limite_do_dia_e_zera_quando_o_dia_vira(monkeypatch):
    dia = [20000]
    monkeypatch.setattr(llm_client, "_dia_da_cota", lambda: dia[0])
    agora = [1000.0]
    monkeypatch.setattr(llm_client.time, "monotonic", lambda: agora[0])
    fake = _cadeia_ab(monkeypatch, {"a": [100, 2]}, {"a": ["a1", "a2", "a3"], "b": ["b1"]})

    for esperado in ("a1", "a2", "b1"):
        assert chamar_com_fallback([]) == esperado
        agora[0] += 120  # espaçadas: o limite por minuto não entra na conta
    assert fake.chat.completions.chamadas == ["a", "a", "b"]

    dia[0] += 1
    assert chamar_com_fallback([]) == "a3"


def test_contador_conta_tentativa_que_falhou(monkeypatch):
    # Há relatos de que o 503 do Gemini desconta da cota diária.
    fake = _cadeia_ab(monkeypatch, {"a": [100, 500]}, {"a": [_erro_servidor(503)], "b": ["b1"]})

    assert chamar_com_fallback([]) == "b1"

    assert llm_client._uso_atual(fake, "a") == (1, 1)
    assert llm_client._uso_atual(fake, "b") == (1, 1)


def test_todos_no_limite_do_contador_ainda_sao_tentados(monkeypatch):
    # O contador é estimativa; se ele tirou todo mundo da fila, vale mais
    # tentar e deixar o provedor responder do que falhar sem chamar ninguém.
    fake = _cadeia_ab(monkeypatch, {"a": [1, 500], "b": [1, 500]}, {"a": ["a1", "a2"], "b": ["b1"]})

    assert [chamar_com_fallback([]) for _ in range(3)] == ["a1", "b1", "a2"]
    assert fake.chat.completions.chamadas == ["a", "b", "a"]


def test_modelo_sem_limite_configurado_nunca_e_pulado_pelo_contador(monkeypatch):
    fake = _cadeia_ab(monkeypatch, {}, {"a": ["x"] * 30, "b": []})

    assert [chamar_com_fallback([]) for _ in range(30)] == ["x"] * 30
    assert set(fake.chat.completions.chamadas) == {"a"}


def test_prazo_total_do_papel_encerra_a_fila(monkeypatch):
    # Achado ao vivo (05/10/2026): seis modelos falhando em fila somaram
    # 201 s num prólogo. O prazo é da fila inteira, não de cada chamada.
    from app.infra.settings import settings

    agora = [0.0]
    monkeypatch.setattr(llm_client.time, "monotonic", lambda: agora[0])
    monkeypatch.setitem(llm_client.CADEIAS, "volume", [("gemini", "a"), ("gemini", "b"), ("gemini", "c")])
    recebidos: list[tuple[str, float]] = []

    class _Completions:
        def create(self, **kwargs):
            recebidos.append((kwargs["model"], kwargs["timeout"]))
            agora[0] += kwargs["timeout"]  # cada modelo consome o tempo limite inteiro
            raise _erro_timeout()

    fake = type("Cliente", (), {"chat": type("Chat", (), {"completions": _Completions()})()})()
    monkeypatch.setattr(llm_client, "clients", {"gemini": fake})

    with pytest.raises(ErroMestre, match="Todos os modelos"):
        chamar_com_fallback([])

    total, por_chamada = settings.prazos_ia["volume"], settings.timeouts_ia["volume"]
    assert recebidos == [("a", por_chamada), ("b", total - por_chamada)]
    assert agora[0] <= total


def test_cada_chamada_da_cadeia_leva_o_tempo_limite_do_papel(monkeypatch):
    from app.infra.settings import settings

    recebidos: list[dict] = []

    class _Completions:
        def create(self, **kwargs):
            recebidos.append(kwargs)
            return "ok"

    fake = type("Cliente", (), {"chat": type("Chat", (), {"completions": _Completions()})()})()
    monkeypatch.setattr(llm_client, "clients", {"gemini": fake})
    monkeypatch.setitem(llm_client.CADEIAS, "volume", [("gemini", "m")])
    monkeypatch.setitem(llm_client.CADEIAS, "destaque", [("gemini", "m")])
    monkeypatch.setattr(settings, "esforco_raciocinio", {"volume": "low"})

    chamar_com_fallback([])
    chamar_com_fallback([], papel="destaque")

    assert recebidos[0]["timeout"] == settings.timeouts_ia["volume"]
    assert recebidos[1]["timeout"] == settings.timeouts_ia["destaque"]
    assert recebidos[0]["reasoning_effort"] == "low"
    assert "reasoning_effort" not in recebidos[1]


def test_todos_os_modelos_falhando_levanta_erro_mestre(monkeypatch):
    comportamento = {modelo: [_erro_rate_limit(), _erro_rate_limit()] for _, modelo in llm_client.CADEIAS["volume"]}
    clients, _ = _fake_clients(comportamento)
    monkeypatch.setattr(llm_client, "clients", clients)

    with pytest.raises(ErroMestre, match="Todos os modelos"):
        chamar_com_fallback([{"role": "user", "content": "oi"}])


def test_primeiro_modelo_funciona_sem_tocar_no_fallback(monkeypatch):
    resultado_ok = object()
    modelo_1 = llm_client.CADEIAS["volume"][0][1]
    clients, fake = _fake_clients({modelo_1: [resultado_ok]})
    monkeypatch.setattr(llm_client, "clients", clients)

    resultado = chamar_com_fallback([{"role": "user", "content": "oi"}])

    assert resultado is resultado_ok
    assert fake.chat.completions.chamadas == [modelo_1]


def test_modelo_com_cota_esgotada_e_pulado_ate_pausa_expirar(monkeypatch):
    modelo_1, modelo_2 = llm_client.CADEIAS["volume"][0][1], llm_client.CADEIAS["volume"][1][1]
    agora = [100.0]
    monkeypatch.setattr(llm_client.time, "monotonic", lambda: agora[0])
    clients, fake = _fake_clients({modelo_1: [_erro_rate_limit(), "recuperado"], modelo_2: ["ok", "ok"]})
    monkeypatch.setattr(llm_client, "clients", clients)
    assert chamar_com_fallback([]) == "ok"
    assert chamar_com_fallback([]) == "ok"
    assert fake.chat.completions.chamadas == [modelo_1, modelo_2, modelo_2]
    agora[0] += 31
    assert chamar_com_fallback([]) == "recuperado"


def test_pausa_de_cota_nao_afeta_outro_cliente():
    cliente_a, cliente_b = _FakeClient({}), _FakeClient({})
    llm_client._registrar_pausa(cliente_a, "modelo", _erro_rate_limit())
    assert llm_client._em_pausa(cliente_a, "modelo")
    assert not llm_client._em_pausa(cliente_b, "modelo")


def test_cada_papel_percorre_a_propria_cadeia(monkeypatch):
    # ADR-0038: o turno de jogo (volume) e o prólogo (destaque) não disputam
    # o mesmo primeiro modelo — cada papel tem a sua lista.
    monkeypatch.setitem(llm_client.CADEIAS, "volume", [("gemini", "modelo-de-volume")])
    monkeypatch.setitem(llm_client.CADEIAS, "destaque", [("gemini", "modelo-de-destaque")])
    ok_volume, ok_destaque = object(), object()
    fake = _FakeClient({"modelo-de-volume": [ok_volume], "modelo-de-destaque": [ok_destaque]})
    monkeypatch.setattr(llm_client, "clients", {"gemini": fake})
    msgs = [{"role": "user", "content": "oi"}]

    assert chamar_com_fallback(msgs) is ok_volume
    assert chamar_com_fallback(msgs, papel="destaque") is ok_destaque
    assert fake.chat.completions.chamadas == ["modelo-de-volume", "modelo-de-destaque"]


def test_cadeias_padrao_poem_o_modelo_de_cota_alta_no_volume():
    # Trava a decisão medida em 05/10/2026: no plano gratuito do Gemini só o
    # 3.5 Flash Lite tem cota diária para sustentar turnos (500/dia contra
    # 20/dia dos Flash). Se alguém reordenar a lista, este teste avisa.
    from app.infra.settings import Settings

    padrao = Settings(_env_file=None)
    assert padrao.cadeia_volume[0] == "gemini:gemini-3.5-flash-lite"
    assert padrao.cadeia_destaque[0] != padrao.cadeia_volume[0]
    assert "gemini:gemini-3.5-flash-lite" in padrao.cadeia_destaque
    assert padrao.cadeia_fundo[0] != padrao.cadeia_volume[0]


def test_provedor_sem_chave_e_pulado_sem_contar_como_falha(monkeypatch):
    # `clients` só tem um provedor que não é o do 1º elo — os elos antes
    # dele são pulados silenciosamente (não é uma tentativa que falhou, é um
    # provedor nunca configurado).
    primeiro_provedor = llm_client.CADEIAS["volume"][0][0]
    provedor_2, modelo_2 = next(elo for elo in llm_client.CADEIAS["volume"] if elo[0] != primeiro_provedor)
    resultado_ok = object()
    fake = _FakeClient({modelo_2: [resultado_ok]})
    monkeypatch.setattr(llm_client, "clients", {provedor_2: fake})

    resultado = chamar_com_fallback([{"role": "user", "content": "oi"}])

    assert resultado is resultado_ok
    assert fake.chat.completions.chamadas == [modelo_2]


class _StreamQuebrado:
    """Um iterador que entrega `chunks` e depois levanta `erro` — simula uma
    stream real que cai no meio (conexão derrubada), diferente de
    `create()` falhar antes de qualquer chunk sair."""

    def __init__(self, chunks: list, erro: Exception) -> None:
        self._chunks = iter(chunks)
        self._erro = erro

    def __iter__(self):
        return self

    def __next__(self):
        try:
            return next(self._chunks)
        except StopIteration:
            raise self._erro from None


class TestChamarStreamComFallback:
    def test_sem_client_levanta_erro_mestre_sem_chamar_nada(self, monkeypatch):
        monkeypatch.setattr(llm_client, "clients", {})
        with pytest.raises(ErroMestre, match="GROQ_API_KEY"):
            list(chamar_stream_com_fallback([{"role": "user", "content": "oi"}]))

    def test_primeiro_modelo_funciona_sem_tocar_no_fallback(self, monkeypatch):
        chunks = ["a", "b", "c"]
        modelo_1 = llm_client.CADEIAS["volume"][0][1]
        clients, fake = _fake_clients({modelo_1: [chunks]})
        monkeypatch.setattr(llm_client, "clients", clients)

        resultado = list(chamar_stream_com_fallback([{"role": "user", "content": "oi"}]))

        assert resultado == chunks
        assert fake.chat.completions.chamadas == [modelo_1]

    def test_falha_antes_do_primeiro_chunk_cai_para_o_proximo_modelo(self, monkeypatch):
        # create() do modelo 1 levanta direto (nunca chega a abrir stream) —
        # nada foi mandado pro cliente ainda, então pode trocar de modelo.
        modelo_1, modelo_2 = llm_client.CADEIAS["volume"][0][1], llm_client.CADEIAS["volume"][1][1]
        chunks = ["x", "y"]
        clients, fake = _fake_clients({modelo_1: [_erro_rate_limit(), _erro_rate_limit()], modelo_2: [chunks]})
        monkeypatch.setattr(llm_client, "clients", clients)

        resultado = list(chamar_stream_com_fallback([{"role": "user", "content": "oi"}]))

        assert resultado == chunks
        assert fake.chat.completions.chamadas == [modelo_1, modelo_2]

    def test_falha_no_meio_da_stream_nao_troca_de_modelo(self, monkeypatch):
        # O modelo 1 abre a stream e manda um chunk — comprometido. Se cair
        # depois disso, vira ErroMestre, e o modelo 2 nunca é chamado (uma
        # troca silenciosa costuraria a resposta de dois modelos diferentes).
        modelo_1 = llm_client.CADEIAS["volume"][0][1]
        stream_quebrada = _StreamQuebrado(["a"], _erro_rate_limit())
        clients, fake = _fake_clients({modelo_1: [stream_quebrada]})
        monkeypatch.setattr(llm_client, "clients", clients)

        gerador = chamar_stream_com_fallback([{"role": "user", "content": "oi"}])
        assert next(gerador) == "a"
        with pytest.raises(ErroMestre, match="caiu no meio"):
            next(gerador)
        assert fake.chat.completions.chamadas == [modelo_1]

    def test_todos_os_modelos_falhando_levanta_erro_mestre(self, monkeypatch):
        comportamento = {modelo: [_erro_rate_limit(), _erro_rate_limit()] for _, modelo in llm_client.CADEIAS["volume"]}
        clients, _ = _fake_clients(comportamento)
        monkeypatch.setattr(llm_client, "clients", clients)

        with pytest.raises(ErroMestre, match="Todos os modelos"):
            list(chamar_stream_com_fallback([{"role": "user", "content": "oi"}]))


class TestChamarComChaveUsuario:
    """BYOK (Etapa 15) — `chamar_com_chave_usuario`/`chamar_stream_com_chave_usuario`
    constroem um `openai.OpenAI` efêmero, fora do dict global `clients`
    (nunca guardado, nunca reaproveitado entre requests) — por isso o dublê
    aqui substitui `openai.OpenAI` em si, não `llm_client.clients`."""

    def _fake_openai(self, monkeypatch, comportamento: dict[str, list]) -> _FakeClient:
        fake = _FakeClient(comportamento)
        monkeypatch.setattr(llm_client.openai, "OpenAI", lambda **kwargs: fake)
        return fake

    def test_chama_o_gemini_com_a_chave_do_usuario_sem_tocar_clients(self, monkeypatch):
        resultado_ok = object()
        fake = self._fake_openai(monkeypatch, {"gemini-3.5-flash": [resultado_ok]})
        # `clients` fica vazio de propósito — o caminho BYOK não depende
        # dele nem o toca.
        monkeypatch.setattr(llm_client, "clients", {})

        resultado = chamar_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave-do-jogador")

        assert resultado is resultado_ok
        assert fake.chat.completions.chamadas == ["gemini-3.5-flash"]

    def test_chave_invalida_vira_erro_mestre_especifico(self, monkeypatch):
        self._fake_openai(monkeypatch, {"gemini-3.5-flash": [_erro_autenticacao()]})

        with pytest.raises(ErroMestre, match="recusada"):
            chamar_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave-invalida")

    def test_falha_transitoria_nao_cai_para_a_chave_do_servidor(self, monkeypatch):
        # Sem cadeia de fallback no caminho BYOK: uma falha (rate limit,
        # timeout) vira ErroMestre direto — nunca um fallback silencioso
        # que gastaria a cota do servidor sem o jogador perceber.
        self._fake_openai(monkeypatch, {"gemini-3.5-flash": [_erro_rate_limit(), _erro_rate_limit()]})

        with pytest.raises(ErroMestre, match="limite de uso"):
            chamar_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave-do-jogador")

    def test_503_esgota_o_retry_embutido_e_vira_erro_mestre(self, monkeypatch):
        # `chamar_com_chave_usuario` não tem `@retry` próprio, mas chama
        # `_chamar_modelo` diretamente — que já é decorada com retry — então
        # o 503 é tentado 2x (stop_after_attempt(2)) antes de virar ErroMestre.
        fake = self._fake_openai(monkeypatch, {"gemini-3.5-flash": [_erro_servidor(503), _erro_servidor(503)]})

        with pytest.raises(ErroMestre, match="sobrecarregado"):
            chamar_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave-do-jogador")

        assert fake.chat.completions.chamadas == ["gemini-3.5-flash", "gemini-3.5-flash"]

    def test_modelo_customizado_e_repassado(self, monkeypatch):
        resultado_ok = object()
        fake = self._fake_openai(monkeypatch, {"gemini-3.5-flash-lite": [resultado_ok]})

        resultado = chamar_com_chave_usuario(
            [{"role": "user", "content": "oi"}], api_key="chave-do-jogador", modelo="gemini-3.5-flash-lite"
        )

        assert resultado is resultado_ok
        assert fake.chat.completions.chamadas == ["gemini-3.5-flash-lite"]

    def test_400_nao_culpa_a_chave(self, monkeypatch):
        # Achado ao vivo (rodada de conserto) — um 400 quase sempre é outra
        # coisa (ex: `content: null` que `agent_loop.py` mandava numa
        # mensagem de tool_call). A mensagem antiga dizia "sua chave foi
        # recusada" para qualquer status; isso é o que passou a diferenciar.
        self._fake_openai(
            monkeypatch, {"gemini-3.5-flash": [_erro_status(400, {"error": {"message": "invalid content field"}})]}
        )

        with pytest.raises(ErroMestre) as exc_info:
            chamar_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave-do-jogador")

        mensagem = str(exc_info.value)
        assert "recusada" not in mensagem
        assert "invalid content field" in mensagem

    def test_404_aponta_para_o_modelo_sem_acesso(self, monkeypatch):
        self._fake_openai(monkeypatch, {"gemini-3.5-flash": [_erro_status(404)]})

        with pytest.raises(ErroMestre, match="não tem acesso ao modelo 'gemini-3.5-flash'"):
            chamar_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave-do-jogador")


class TestChamarStreamComChaveUsuario:
    def _fake_openai(self, monkeypatch, comportamento: dict[str, list]) -> _FakeClient:
        fake = _FakeClient(comportamento)
        monkeypatch.setattr(llm_client.openai, "OpenAI", lambda **kwargs: fake)
        return fake

    def test_stream_da_chave_do_usuario_funciona_de_ponta_a_ponta(self, monkeypatch):
        chunks = ["a", "b", "c"]
        fake = self._fake_openai(monkeypatch, {"gemini-3.5-flash": [chunks]})

        resultado = list(chamar_stream_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave"))

        assert resultado == chunks
        assert fake.chat.completions.chamadas == ["gemini-3.5-flash"]

    def test_falha_no_meio_da_stream_vira_erro_mestre_sem_fallback(self, monkeypatch):
        stream_quebrada = _StreamQuebrado(["a"], _erro_rate_limit())
        self._fake_openai(monkeypatch, {"gemini-3.5-flash": [stream_quebrada]})

        gerador = chamar_stream_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave")
        assert next(gerador) == "a"
        with pytest.raises(ErroMestre, match="limite de uso"):
            next(gerador)

    def test_chave_invalida_vira_erro_mestre_antes_do_primeiro_chunk(self, monkeypatch):
        self._fake_openai(monkeypatch, {"gemini-3.5-flash": [_erro_autenticacao()]})

        with pytest.raises(ErroMestre, match="recusada"):
            list(chamar_stream_com_chave_usuario([{"role": "user", "content": "oi"}], api_key="chave-invalida"))


class _FakeModels:
    def __init__(self, resultado: object) -> None:
        self._resultado = resultado

    def list(self):
        if isinstance(self._resultado, Exception):
            raise self._resultado
        return self._resultado


class _FakeClientComModels:
    def __init__(self, resultado: object) -> None:
        self.models = _FakeModels(resultado)


class TestValidarChaveUsuario:
    """Rodada de conserto — `MenuConfiguracao.tsx` valida a chave assim
    que o jogador cola ela, em vez de só descobrir no meio de uma cena."""

    def test_chave_valida_nao_levanta(self, monkeypatch):
        monkeypatch.setattr(llm_client.openai, "OpenAI", lambda **kwargs: _FakeClientComModels(object()))
        validar_chave_usuario("chave-boa")  # não levanta

    def test_chave_invalida_vira_erro_mestre(self, monkeypatch):
        monkeypatch.setattr(llm_client.openai, "OpenAI", lambda **kwargs: _FakeClientComModels(_erro_autenticacao()))

        with pytest.raises(ErroMestre, match="recusada"):
            validar_chave_usuario("chave-ruim")

    def test_falha_transitoria_vira_erro_mestre_especifico(self, monkeypatch):
        monkeypatch.setattr(llm_client.openai, "OpenAI", lambda **kwargs: _FakeClientComModels(_erro_rate_limit()))

        with pytest.raises(ErroMestre, match="demorou"):
            validar_chave_usuario("chave-de-teste")
