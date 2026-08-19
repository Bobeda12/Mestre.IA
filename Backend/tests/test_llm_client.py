"""Testa app/infra/llm_client.py — a cadeia de fallback entre modelos
(ADR-0008) e o retry por erro transitório, sem chamar a API da Groq de
verdade. `httpx.Request`/`Response` reais (sem rede) são o jeito mais simples
de montar um `groq.RateLimitError` de verdade — o SDK exige os dois no
construtor."""

import httpx
import pytest
import tenacity

from app.infra import llm_client
from app.infra.llm_client import ErroMestre, chamar_com_fallback


def _erro_rate_limit() -> Exception:
    req = httpx.Request("POST", "https://api.groq.com/x")
    resp = httpx.Response(429, request=req)
    import groq

    return groq.RateLimitError("cota estourada", response=resp, body=None)


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


@pytest.fixture(autouse=True)
def _sem_espera_entre_tentativas(monkeypatch):
    # Mesmo backoff exponencial que roda em produção, mas sem esperar de
    # verdade — senão cada teste de fallback esgotado levaria segundos.
    monkeypatch.setattr(llm_client._chamar_modelo.retry, "wait", tenacity.wait_none())  # type: ignore[attr-defined]


def test_sem_client_levanta_erro_mestre_sem_chamar_nada(monkeypatch):
    monkeypatch.setattr(llm_client, "client", None)
    with pytest.raises(ErroMestre, match="GROQ_API_KEY"):
        chamar_com_fallback([{"role": "user", "content": "oi"}])


def test_primeiro_modelo_esgota_retry_e_cai_para_o_proximo(monkeypatch):
    modelo_1, modelo_2 = llm_client.MODELOS[0], llm_client.MODELOS[1]
    resultado_ok = object()
    fake = _FakeClient({modelo_1: [_erro_rate_limit(), _erro_rate_limit()], modelo_2: [resultado_ok]})
    monkeypatch.setattr(llm_client, "client", fake)

    resultado = chamar_com_fallback([{"role": "user", "content": "oi"}])

    assert resultado is resultado_ok
    assert fake.chat.completions.chamadas == [modelo_1, modelo_1, modelo_2]


def test_todos_os_modelos_falhando_levanta_erro_mestre(monkeypatch):
    comportamento = {modelo: [_erro_rate_limit(), _erro_rate_limit()] for modelo in llm_client.MODELOS}
    fake = _FakeClient(comportamento)
    monkeypatch.setattr(llm_client, "client", fake)

    with pytest.raises(ErroMestre, match="Todos os modelos"):
        chamar_com_fallback([{"role": "user", "content": "oi"}])


def test_primeiro_modelo_funciona_sem_tocar_no_fallback(monkeypatch):
    resultado_ok = object()
    fake = _FakeClient({llm_client.MODELOS[0]: [resultado_ok]})
    monkeypatch.setattr(llm_client, "client", fake)

    resultado = chamar_com_fallback([{"role": "user", "content": "oi"}])

    assert resultado is resultado_ok
    assert fake.chat.completions.chamadas == [llm_client.MODELOS[0]]
