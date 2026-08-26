"""Testa GET /regras (rodada de conserto, Parte 2 item K) — a aba de regras
gerada do motor. O que importa aqui não é o CONTEÚDO exato de cada texto
(isso é edição de copy), é que os NÚMEROS batem com o motor de verdade —
se `rules_engine`/`ToolExecutor` mudarem, este endpoint muda junto sem
precisar editar nada nele."""

from fastapi.testclient import TestClient

from app.main import app
from app.services import rules_engine as motor
from app.services.tools import ToolExecutor

client = TestClient(app)


def test_get_regras_devolve_200():
    resp = client.get("/regras")
    assert resp.status_code == 200


def test_niveis_batem_com_o_motor_de_verdade():
    resp = client.get("/regras")
    niveis = resp.json()["niveis"]
    assert len(niveis) == len(motor.XP_POR_NIVEL)
    for entrada in niveis:
        assert entrada["xp_necessario"] == motor.XP_POR_NIVEL[entrada["nivel"]]
        assert entrada["bonus_proficiencia"] == motor.bonus_proficiencia(entrada["nivel"])


def test_niveis_vem_em_ordem_crescente():
    resp = client.get("/regras")
    niveis = [n["nivel"] for n in resp.json()["niveis"]]
    assert niveis == sorted(niveis)


def test_aliado_padrao_bate_com_toolexecutor():
    resp = client.get("/regras")
    aliado = resp.json()["aliado_padrao"]
    assert aliado["ca"] == ToolExecutor.CA_ALIADO_PADRAO
    assert aliado["bonus_ataque"] == ToolExecutor.BONUS_ATAQUE_ALIADO_PADRAO
    assert aliado["dano_dado"] == ToolExecutor.DANO_ALIADO_PADRAO


def test_bonus_item_com_tag_bate_com_toolexecutor():
    resp = client.get("/regras")
    assert resp.json()["bonus_item_com_tag"] == ToolExecutor.BONUS_ITEM_COM_TAG


def test_escala_de_dificuldade_tem_cinco_degraus_crescentes():
    resp = client.get("/regras")
    escala = resp.json()["escala_dificuldade"]
    cds = [e["cd"] for e in escala]
    assert cds == sorted(cds)
    assert len(cds) == 5


def test_armas_vem_do_catalogo_de_verdade():
    resp = client.get("/regras")
    armas = resp.json()["armas"]
    assert "Simples" in armas
    assert "Marciais" in armas
    assert "Adaga" in armas["Simples"]


def test_nao_serve_a_biblia_do_mestre():
    # Cuidado deliberado do plano — isto NÃO pode virar um jeito de vazar o
    # prompt de sistema. Nenhuma chave da resposta expõe texto de
    # `data/biblia_mestre.txt`.
    resp = client.get("/regras")
    corpo = str(resp.json()).lower()
    assert "verossimilhança" not in corpo
    assert "proteja o jogador" not in corpo
