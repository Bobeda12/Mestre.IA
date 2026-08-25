"""Testa app/infra/embeddings.py — em especial o roteamento de `api_key`
(Etapa 15, BYOK): a memória de longo prazo passa a chave do jogador aqui
quando ele tem uma; sem chave nenhuma (nem do jogador, nem do servidor),
degrada pro vetor zero, igual já fazia antes desta etapa. Nenhum teste
aqui bate na rede de verdade — `httpx.post` é sempre mockado."""

import httpx
import pytest

from app.infra import embeddings
from app.infra.settings import settings

# `tests/conftest.py` tem um fixture autouse (`_embeddings_sem_rede`) que
# substitui `embeddings.embed_um`/`embed` por um dublê hash-based pra nenhum
# outro teste do projeto precisar se importar com embedding real — bom para
# todo o resto da suíte, mas invalidaria justamente o que este arquivo quer
# testar. `embed_um` chama `embed` pelo nome global do próprio módulo (não
# uma referência capturada), então basta reverter os dois pro original
# DEPOIS que o fixture autouse já rodou — `monkeypatch` é a mesma instância
# em toda a árvore de fixtures de um teste, e desfaz tudo sozinho no fim.
_embed_um_original = embeddings.embed_um
_embed_original = embeddings.embed


@pytest.fixture(autouse=True)
def _embeddings_de_verdade(monkeypatch):
    monkeypatch.setattr(embeddings, "embed_um", _embed_um_original)
    monkeypatch.setattr(embeddings, "embed", _embed_original)


class _RespostaFake:
    def __init__(self, valores: list[float]) -> None:
        self._valores = valores

    def raise_for_status(self) -> None:
        pass

    def json(self) -> dict:
        return {"embedding": {"values": self._valores}}


def test_usa_a_chave_do_usuario_quando_informada(monkeypatch):
    headers_recebidos: dict = {}

    def _post_fake(url, headers, json, timeout):
        headers_recebidos.update(headers)
        return _RespostaFake([1.0, 0.0])

    monkeypatch.setattr(httpx, "post", _post_fake)
    monkeypatch.setattr(settings, "gemini_api_key", "chave-do-servidor")

    embeddings.embed_um("um texto qualquer", api_key="chave-do-jogador")

    assert headers_recebidos["x-goog-api-key"] == "chave-do-jogador"


def test_sem_chave_do_usuario_cai_para_a_do_servidor(monkeypatch):
    headers_recebidos: dict = {}

    def _post_fake(url, headers, json, timeout):
        headers_recebidos.update(headers)
        return _RespostaFake([1.0, 0.0])

    monkeypatch.setattr(httpx, "post", _post_fake)
    monkeypatch.setattr(settings, "gemini_api_key", "chave-do-servidor")

    embeddings.embed_um("um texto qualquer")

    assert headers_recebidos["x-goog-api-key"] == "chave-do-servidor"


def test_sem_chave_nenhuma_degrada_pro_vetor_zero_sem_chamar_rede(monkeypatch):
    chamou = False

    def _post_fake(*a, **k):
        nonlocal chamou
        chamou = True
        raise AssertionError("não deveria chamar a rede sem nenhuma chave disponível")

    monkeypatch.setattr(httpx, "post", _post_fake)
    monkeypatch.setattr(settings, "gemini_api_key", None)

    resultado = embeddings.embed_um("um texto qualquer")

    assert not chamou
    assert resultado == embeddings._VETOR_ZERO


def test_falha_da_chave_do_usuario_degrada_pro_vetor_zero(monkeypatch):
    def _post_fake(url, headers, json, timeout):
        req = httpx.Request("POST", url)
        resp = httpx.Response(401, request=req)
        raise httpx.HTTPStatusError("chave inválida", request=req, response=resp)

    monkeypatch.setattr(httpx, "post", _post_fake)
    monkeypatch.setattr(settings, "gemini_api_key", "chave-do-servidor")

    resultado = embeddings.embed_um("um texto qualquer", api_key="chave-do-jogador-invalida")

    assert resultado == embeddings._VETOR_ZERO
