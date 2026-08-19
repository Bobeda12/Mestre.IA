"""Testa app/services/hybrid_search.py (Etapa 5) — busca léxica, densa,
fusão RRF e decaimento por recência, isolados do modelo de embedding real
(que é lento e baixa rede na primeira chamada): `embed_fn` é sempre um fake
determinístico injetado, nunca `app.infra.embeddings.embed_um`."""

from app.services.hybrid_search import (
    Documento,
    busca_densa,
    busca_lexica,
    buscar,
    decaimento_recencia,
    fusao_rrf,
)


def _embed_fake(texto: str) -> list[float]:
    """Um "embedding" de brinquedo: um vetor por palavra-chave conhecida,
    suficiente para diferenciar frases sobre goblin/taverneiro/chuva sem
    carregar nenhum modelo real."""
    vocabulario = ["goblin", "taverneiro", "chuva", "espada", "tesouro"]
    texto_lower = texto.lower()
    return [1.0 if palavra in texto_lower else 0.0 for palavra in vocabulario]


DOCUMENTOS = [
    Documento(id=1, texto="Um goblin ataca da sombra com uma adaga.", embedding=_embed_fake("goblin adaga"), turno=1),
    Documento(
        id=2,
        texto="O taverneiro serve cerveja e resmunga sobre impostos.",
        embedding=_embed_fake("taverneiro"),
        turno=10,
    ),
    Documento(id=3, texto="Chuva forte cai sobre o telhado da estalagem.", embedding=_embed_fake("chuva"), turno=50),
]


class TestBuscaLexica:
    def test_corpus_vazio_nao_lanca(self):
        assert busca_lexica("goblin", []) == []

    def test_query_com_palavra_exclusiva_de_um_documento_o_coloca_primeiro(self):
        ranking = busca_lexica("taverneiro cerveja", DOCUMENTOS)
        assert ranking[0] == 2

    def test_query_sem_nenhum_termo_em_comum_devolve_vazio_em_vez_de_ordem_falsa(self):
        # Nenhuma palavra de "xenomorfo intergaláctico" aparece em nenhum
        # documento — sem o corte, BM25Okapi devolveria zeros para todos e
        # a ordenação por score empataria pela ordem de entrada, fingindo
        # ser um ranking de relevância (o bug real que motivou este teste,
        # ver ADR-0010).
        assert busca_lexica("xenomorfo intergaláctico", DOCUMENTOS) == []


class TestBuscaDensa:
    def test_embedding_identico_fica_em_primeiro(self):
        ranking = busca_densa(_embed_fake("chuva"), DOCUMENTOS)
        assert ranking[0] == 3

    def test_vetor_nulo_nao_lanca_divisao_por_zero(self):
        doc_vazio = Documento(id=99, texto="nada", embedding=[0.0, 0.0, 0.0, 0.0, 0.0])
        ranking = busca_densa(_embed_fake("goblin"), [*DOCUMENTOS, doc_vazio])
        assert 99 in ranking  # não lança, só fica mal ranqueado


class TestFusaoRrf:
    def test_documento_bem_ranqueado_nas_duas_listas_vence(self):
        scores = fusao_rrf([[1, 2, 3], [1, 3, 2]])
        assert max(scores, key=lambda id_: scores[id_]) == 1

    def test_documento_so_numa_lista_ainda_pontua(self):
        scores = fusao_rrf([[5], []])
        assert scores[5] > 0


class TestDecaimentoRecencia:
    def test_evento_recente_pesa_mais_que_antigo_com_mesmo_score_base(self):
        scores = {1: 1.0, 3: 1.0}  # turno=1 (docs) vs turno=50
        ajustado = decaimento_recencia(scores, DOCUMENTOS, turno_atual=51, meia_vida=20)
        assert ajustado[3] > ajustado[1]

    def test_documento_sem_turno_nao_e_penalizado(self):
        doc_sem_turno = Documento(id=7, texto="regra estática", embedding=[0, 0, 0, 0, 0], turno=None)
        ajustado = decaimento_recencia({7: 1.0}, [doc_sem_turno], turno_atual=100)
        assert ajustado[7] == 1.0


class TestBuscar:
    def test_devolve_no_maximo_k_documentos(self):
        encontrados = buscar("goblin", DOCUMENTOS, k=1, embed_fn=_embed_fake)
        assert len(encontrados) == 1

    def test_corpus_vazio_devolve_lista_vazia(self):
        assert buscar("goblin", [], embed_fn=_embed_fake) == []

    def test_query_exata_traz_o_documento_certo_em_primeiro(self):
        encontrados = buscar("taverneiro cerveja impostos", DOCUMENTOS, k=3, embed_fn=_embed_fake)
        assert encontrados[0].id == 2

    def test_recencia_desempata_a_favor_do_mais_recente(self):
        # Mesmo texto, mesmo embedding — léxica e densa empatam os dois
        # exatamente. Só o decaimento por turno consegue separá-los.
        doc_antigo = Documento(id=100, texto="pista sobre o goblin", embedding=_embed_fake("goblin"), turno=1)
        doc_recente = Documento(id=101, texto="pista sobre o goblin", embedding=_embed_fake("goblin"), turno=99)
        encontrados = buscar("goblin", [doc_antigo, doc_recente], turno_atual=100, k=1, embed_fn=_embed_fake)
        assert encontrados[0].id == 101
