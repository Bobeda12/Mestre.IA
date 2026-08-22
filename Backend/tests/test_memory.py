"""Testa app/services/memory.py (Etapa 5) — registro e recuperação de
memória de longo prazo, e o sumário rolante de médio prazo. `embed_fn` é
sempre um fake determinístico (mesmo padrão de test_hybrid_search.py);
`chamar_modelo_unico` do resumo rolante é mockado como em
test_llm_client.py — nenhum teste aqui toca rede."""

import json

import pytest

from app.infra import llm_client
from app.infra.db import EventoMemoria, Personagem, SessionLocal
from app.services import memory


def _embed_fake(texto: str) -> list[float]:
    vocabulario = ["goblin", "taverneiro", "ferreiro"]
    texto_lower = texto.lower()
    return [1.0 if p in texto_lower else 0.0 for p in vocabulario]


@pytest.fixture
def db():
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()


def _resumo_com(fatos: list[str]) -> dict:
    return {"fatos_estabelecidos": fatos, "npcs_conhecidos": [], "promessas_feitas": [], "mudancas_no_mundo": []}


def _personagem(db, session_id: str) -> Personagem:
    heroi = Personagem(
        usuario_id=1,
        session_id=session_id,
        nome="TesteMemoria",
        raca="Humano",
        classe="Guerreiro",
        alinhamento="Neutro",
        background="",
        objetivo="",
        hp_atual=10,
        hp_max=10,
        defesa=15,
        atributos={},
        inventario=[],
    )
    db.add(heroi)
    db.commit()
    db.refresh(heroi)
    return heroi


class TestRegistrarEvento:
    def test_grava_e_devolve_o_evento(self, db):
        heroi = _personagem(db, "sessao-1")
        evento = memory.registrar_evento(
            db, heroi.id, turno=1, tipo="turno", texto="O goblin ataca.", embed_fn=_embed_fake
        )
        assert evento.id is not None
        assert db.query(EventoMemoria).filter(EventoMemoria.personagem_id == heroi.id).count() == 1


class TestMemoriasRelevantes:
    def test_filtra_por_personagem_nunca_vaza_entre_sessoes(self, db):
        heroi_a = _personagem(db, "sessao-a")
        heroi_b = _personagem(db, "sessao-b")
        memory.registrar_evento(db, heroi_a.id, 1, "turno", "O ferreiro forja uma espada.", embed_fn=_embed_fake)
        memory.registrar_evento(db, heroi_b.id, 1, "turno", "O taverneiro serve cerveja.", embed_fn=_embed_fake)

        encontrados = memory.memorias_relevantes(db, heroi_a.id, "ferreiro", turno_atual=2, embed_fn=_embed_fake)

        assert any("ferreiro" in texto for texto in encontrados)
        assert all("taverneiro" not in texto for texto in encontrados)

    def test_sem_eventos_devolve_lista_vazia(self, db):
        heroi = _personagem(db, "sessao-vazia")
        assert memory.memorias_relevantes(db, heroi.id, "qualquer coisa", turno_atual=1, embed_fn=_embed_fake) == []

    def test_query_nao_traz_mais_eventos_que_o_teto(self, db, monkeypatch):
        # Etapa 10 (A-6) — antes desta correção, todo evento do personagem
        # (com embedding) vinha do banco a cada turno; a sessão longa que
        # motivou o A-6 tinha centenas. Aqui o teto vem apertado (3) pra não
        # precisar criar centenas de linhas só pra provar o comportamento.
        from app.infra.settings import settings

        monkeypatch.setattr(settings, "limite_eventos_memoria", 3)
        heroi = _personagem(db, "sessao-muitos-eventos")
        for i in range(10):
            memory.registrar_evento(db, heroi.id, turno=i, tipo="turno", texto=f"evento {i}", embed_fn=_embed_fake)

        # `hybrid_search.buscar` só pode devolver o que a query trouxe do
        # banco — com teto 3, só os turnos mais recentes (7, 8, 9) entram
        # na disputa, mesmo pedindo k=10 (mais do que existe candidato).
        encontrados = memory.memorias_relevantes(
            db, heroi.id, "evento", turno_atual=10, k=10, embed_fn=_embed_fake
        )
        assert len(encontrados) == 3
        assert all(texto in ("evento 7", "evento 8", "evento 9") for texto in encontrados)


class TestAtualizarResumoRolante:
    def test_nao_atualiza_antes_do_limiar_de_turnos(self, db):
        heroi = _personagem(db, "sessao-resumo-1")
        heroi.historico_chat = [{"role": "user", "content": "oi"}, {"role": "assistant", "content": "olá"}]
        assert memory.atualizar_resumo_rolante(heroi, k_turnos=8) is False

    def test_mescla_resumo_novo_com_o_existente(self, db, monkeypatch):
        heroi = _personagem(db, "sessao-resumo-2")
        heroi.historico_chat = [{"role": "user", "content": f"ação {i}"} for i in range(4)]
        heroi.resumo_rolante = _resumo_com(["o céu é escuro"])

        resposta_fake = json.dumps(
            {
                "fatos_estabelecidos": ["o herói encontrou um mapa"],
                "npcs_conhecidos": ["Taverneiro Gundren"],
                "promessas_feitas": [],
                "mudancas_no_mundo": [],
            }
        )

        class _Resp:
            choices = [type("C", (), {"message": type("M", (), {"content": resposta_fake})()})]

        monkeypatch.setattr(llm_client, "chamar_modelo_unico", lambda *a, **k: _Resp())

        atualizou = memory.atualizar_resumo_rolante(heroi, k_turnos=2)

        assert atualizou is True
        assert "o céu é escuro" in heroi.resumo_rolante["fatos_estabelecidos"]
        assert "o herói encontrou um mapa" in heroi.resumo_rolante["fatos_estabelecidos"]
        assert heroi.turno_resumido_ate == 4

    def test_falha_do_modelo_nao_derruba_e_preserva_resumo_antigo(self, db, monkeypatch):
        heroi = _personagem(db, "sessao-resumo-3")
        heroi.historico_chat = [{"role": "user", "content": f"ação {i}"} for i in range(4)]
        heroi.resumo_rolante = _resumo_com(["fato preservado"])

        def _levanta(*a, **k):
            raise llm_client.ErroMestre("falhou")

        monkeypatch.setattr(llm_client, "chamar_modelo_unico", _levanta)

        atualizou = memory.atualizar_resumo_rolante(heroi, k_turnos=2)

        assert atualizou is False
        assert heroi.resumo_rolante["fatos_estabelecidos"] == ["fato preservado"]
        assert heroi.turno_resumido_ate == 0
