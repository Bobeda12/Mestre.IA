"""Testa app/services/rag_regras.py (Etapa 5) — divisão da bíblia em seções
e recuperação das relevantes por busca híbrida. Usa a bíblia real
(Backend/data/biblia_mestre.txt) com um `embed_fn` fake determinístico, para
o teste não depender do modelo de embedding real."""

from app.services import rag_regras


def _embed_fake(texto: str) -> list[float]:
    vocabulario = ["combate", "chuva", "clima", "npc", "reputação", "grosseria"]
    texto_lower = texto.lower()
    return [1.0 if p in texto_lower else 0.0 for p in vocabulario]


def setup_function():
    # Cada teste embeda com um `embed_fn` diferente do de outro módulo de
    # teste — limpa o cache para não misturar vetores de vocabulários
    # incompatíveis entre arquivos de teste.
    rag_regras._documentos_cache.clear()


class TestDividirEmSecoes:
    def test_encontra_pelo_menos_as_secoes_conhecidas_da_biblia(self):
        titulos = {rag_regras._titulo(s) for s in rag_regras._secoes()}
        assert "PROTOCOLO DE ARBITRAGEM" in titulos
        assert "SISTEMA DE CONSEQUÊNCIA SOCIAL" in titulos


class TestRegrasRelevantes:
    def test_sempre_inclui_as_diretrizes_de_narracao(self):
        encontradas = rag_regras.regras_relevantes("o jogador insulta o taverneiro", k=1, embed_fn=_embed_fake)
        titulos = {rag_regras._titulo(s) for s in encontradas}
        assert titulos >= rag_regras._SECOES_SEMPRE

    def test_query_sobre_clima_traz_a_secao_de_clima(self):
        encontradas = rag_regras.regras_relevantes("o clima está com chuva forte", k=1, embed_fn=_embed_fake)
        assert any("GESTÃO DE TEMPO E CLIMA" in rag_regras._titulo(s) for s in encontradas)

    def test_query_sobre_reputacao_traz_a_secao_de_consequencia_social(self):
        encontradas = rag_regras.regras_relevantes(
            "fui rude com o npc, isso muda a reputação", k=1, embed_fn=_embed_fake
        )
        assert any("SISTEMA DE CONSEQUÊNCIA SOCIAL" in rag_regras._titulo(s) for s in encontradas)
