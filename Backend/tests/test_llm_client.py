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
    `llm_client.CADEIA` — os testes indexam `comportamento` pelo nome
    (bare) do modelo, não por provedor; o provedor só decide qual entrada
    de `clients` o código de produção resolve, o dublê não precisa
    distinguir isso para os cenários testados aqui."""
    fake = _FakeClient(comportamento)
    provedores = {provedor for provedor, _ in llm_client.CADEIA}
    return dict.fromkeys(provedores, fake), fake


@pytest.fixture(autouse=True)
def _sem_espera_entre_tentativas(monkeypatch):
    # Mesmo backoff exponencial que roda em produção, mas sem esperar de
    # verdade — senão cada teste de fallback esgotado levaria segundos.
    monkeypatch.setattr(llm_client._chamar_modelo.retry, "wait", tenacity.wait_none())  # type: ignore[attr-defined]


def test_sem_client_levanta_erro_mestre_sem_chamar_nada(monkeypatch):
    monkeypatch.setattr(llm_client, "clients", {})
    with pytest.raises(ErroMestre, match="GROQ_API_KEY"):
        chamar_com_fallback([{"role": "user", "content": "oi"}])


def test_primeiro_modelo_esgota_retry_e_cai_para_o_proximo(monkeypatch):
    modelo_1, modelo_2 = llm_client.CADEIA[0][1], llm_client.CADEIA[1][1]
    resultado_ok = object()
    clients, fake = _fake_clients({modelo_1: [_erro_rate_limit(), _erro_rate_limit()], modelo_2: [resultado_ok]})
    monkeypatch.setattr(llm_client, "clients", clients)

    resultado = chamar_com_fallback([{"role": "user", "content": "oi"}])

    assert resultado is resultado_ok
    assert fake.chat.completions.chamadas == [modelo_1, modelo_1, modelo_2]


def test_todos_os_modelos_falhando_levanta_erro_mestre(monkeypatch):
    comportamento = {modelo: [_erro_rate_limit(), _erro_rate_limit()] for _, modelo in llm_client.CADEIA}
    clients, _ = _fake_clients(comportamento)
    monkeypatch.setattr(llm_client, "clients", clients)

    with pytest.raises(ErroMestre, match="Todos os modelos"):
        chamar_com_fallback([{"role": "user", "content": "oi"}])


def test_primeiro_modelo_funciona_sem_tocar_no_fallback(monkeypatch):
    resultado_ok = object()
    modelo_1 = llm_client.CADEIA[0][1]
    clients, fake = _fake_clients({modelo_1: [resultado_ok]})
    monkeypatch.setattr(llm_client, "clients", clients)

    resultado = chamar_com_fallback([{"role": "user", "content": "oi"}])

    assert resultado is resultado_ok
    assert fake.chat.completions.chamadas == [modelo_1]


def test_provedor_sem_chave_e_pulado_sem_contar_como_falha(monkeypatch):
    # `clients` só tem o provedor do 2º elo — o 1º é pulado silenciosamente
    # (não é uma tentativa que falhou, é um provedor nunca configurado).
    provedor_2, modelo_2 = llm_client.CADEIA[1]
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
        modelo_1 = llm_client.CADEIA[0][1]
        clients, fake = _fake_clients({modelo_1: [chunks]})
        monkeypatch.setattr(llm_client, "clients", clients)

        resultado = list(chamar_stream_com_fallback([{"role": "user", "content": "oi"}]))

        assert resultado == chunks
        assert fake.chat.completions.chamadas == [modelo_1]

    def test_falha_antes_do_primeiro_chunk_cai_para_o_proximo_modelo(self, monkeypatch):
        # create() do modelo 1 levanta direto (nunca chega a abrir stream) —
        # nada foi mandado pro cliente ainda, então pode trocar de modelo.
        modelo_1, modelo_2 = llm_client.CADEIA[0][1], llm_client.CADEIA[1][1]
        chunks = ["x", "y"]
        clients, fake = _fake_clients({modelo_1: [_erro_rate_limit(), _erro_rate_limit()], modelo_2: [chunks]})
        monkeypatch.setattr(llm_client, "clients", clients)

        resultado = list(chamar_stream_com_fallback([{"role": "user", "content": "oi"}]))

        assert resultado == chunks
        assert fake.chat.completions.chamadas == [modelo_1, modelo_1, modelo_2]

    def test_falha_no_meio_da_stream_nao_troca_de_modelo(self, monkeypatch):
        # O modelo 1 abre a stream e manda um chunk — comprometido. Se cair
        # depois disso, vira ErroMestre, e o modelo 2 nunca é chamado (uma
        # troca silenciosa costuraria a resposta de dois modelos diferentes).
        modelo_1 = llm_client.CADEIA[0][1]
        stream_quebrada = _StreamQuebrado(["a"], _erro_rate_limit())
        clients, fake = _fake_clients({modelo_1: [stream_quebrada]})
        monkeypatch.setattr(llm_client, "clients", clients)

        gerador = chamar_stream_com_fallback([{"role": "user", "content": "oi"}])
        assert next(gerador) == "a"
        with pytest.raises(ErroMestre, match="caiu no meio"):
            next(gerador)
        assert fake.chat.completions.chamadas == [modelo_1]

    def test_todos_os_modelos_falhando_levanta_erro_mestre(self, monkeypatch):
        comportamento = {modelo: [_erro_rate_limit(), _erro_rate_limit()] for _, modelo in llm_client.CADEIA}
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
