"""F2 do plano "Trilha do capítulo + Combate v2" — passos do capítulo: a IA
só redige, o servidor confere pelo estado do jogo."""
# ruff: noqa: F811 — a fixture `executor` é importada de test_living_world e usada como parâmetro

import json
from types import SimpleNamespace

from app.domain.living_world import Arco, CondicaoPasso, Passo
from app.domain.state import WorldState
from app.infra import llm_client
from app.services import capitulo
from app.services import living_world as mundo
from app.services.tools import tools_para
from tests.helpers import RngFixo
from tests.test_living_world import agir, executor  # noqa: F401 — fixture


def _arco(executor) -> Arco:
    arco = mundo.arco_ativo(executor.w_state.mundo)
    assert arco is not None
    return arco


def _passo(executor, tipo: str, alvo: str = "", local: str = "") -> Passo:
    """Troca o passo atual por um de condição conhecida."""
    arco = _arco(executor)
    arco.passos = [p for p in arco.passos if p.estado != "atual"]
    novo = Passo(id=f"p{len(arco.passos) + 1}", texto="Passo de teste.",
                 condicao=CondicaoPasso(tipo=tipo, alvo=alvo, local=local))
    capitulo._fotografar(novo, executor.w_state, arco)
    arco.passos = [*arco.passos, novo]
    return novo


def _resposta_ia(conteudo: dict):
    def chamar(msgs, **_):
        chamar.msgs = msgs
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(conteudo)))])
    return chamar


# -- nascimento -----------------------------------------------------------

def test_garantir_cria_o_primeiro_passo_sem_ia(executor):
    arco = _arco(executor)
    assert arco.passos == []
    assert capitulo.garantir_passo(executor.w_state, executor.heroi) is True
    atual = capitulo.passo_atual(arco)
    assert atual is not None and atual.origem == "servidor" and atual.estado == "atual"
    # o agente do conflito central está na cena: o primeiro passo é ouvi-lo
    assert (atual.condicao.tipo, atual.condicao.alvo) == ("falar_pessoa", "responsavel")
    assert capitulo.garantir_passo(executor.w_state, executor.heroi) is False  # idempotente


def test_migracao_credita_arco_antigo_e_cria_passo(executor):
    arco = _arco(executor)
    executor.w_state.versao_mundo = 1
    executor.w_state.turno = arco.turno_inicio + 9  # já tinha os 8 turnos da regra antiga
    assert capitulo.migrar_capitulo(executor.w_state, executor.heroi) is True
    assert executor.w_state.versao_mundo == 2
    assert sum(p.estado == "feito" for p in arco.passos) == capitulo.MIN_PASSOS_ARCO
    assert capitulo.passo_atual(arco) is not None
    assert capitulo.migrar_capitulo(executor.w_state, executor.heroi) is False


# -- conferência pelo servidor -------------------------------------------

def test_conversar_cumpre_falar_pessoa_e_da_xp(executor):
    capitulo.garantir_passo(executor.w_state, executor.heroi)
    xp = executor.heroi.xp or 0
    r, ok = agir(executor, "agir_no_mundo", acao="conversar", alvo="responsavel")
    assert ok, r
    arco = _arco(executor)
    feito = arco.passos[0]
    assert feito.estado == "feito" and "Íria" in feito.evidencia and feito.turno_fim is not None
    assert (executor.heroi.xp or 0) == xp + capitulo.XP_PASSO
    assert arco.passo_pendente is True
    assert any("Passo cumprido" in str(e) for e in executor.eventos)


def test_conversar_com_outra_pessoa_nao_cumpre(executor):
    capitulo.garantir_passo(executor.w_state, executor.heroi)
    agir(executor, "agir_no_mundo", acao="conversar", alvo="interlocutora")
    assert _arco(executor).passos[0].estado == "atual"


def test_investigar_cumpre_o_passo_da_entidade(executor):
    _passo(executor, "investigar", "registro", executor.w_state.local)
    r, ok = agir(executor, "agir_no_mundo", acao="investigar", alvo="registro")
    assert ok, r
    assert _arco(executor).passos[-1].estado == "feito"


def test_chegar_local_cumpre_ao_mover(executor):
    destino = "A Torre Caída"  # a saída registrada da cena está trancada; este é um lugar novo
    _passo(executor, "chegar_local", destino)
    executor.rng = RngFixo([10] * 10)
    r, ok = agir(executor, "mover", destino=destino, descricao_proposta="Pedras soltas e um arco de entrada.")
    assert ok, r
    assert _arco(executor).passos[-1].estado == "feito"


def test_ganhar_confianca_cumpre_quando_a_pessoa_coopera(executor):
    _passo(executor, "ganhar_confianca", "responsavel")
    executor.w_state.mundo.pessoas["responsavel"].disposicao = "cooperativo"
    capitulo.conferir_passo(executor)
    assert _arco(executor).passos[-1].estado == "feito"


def test_registrar_fato_conta_so_fatos_novos(executor):
    mundo.registrar_fato(executor, "Fato de antes do passo.")
    passo = _passo(executor, "registrar_fato")
    capitulo.conferir_passo(executor)
    assert passo.estado == "atual"
    mundo.registrar_fato(executor, "Fato novo.")
    capitulo.conferir_passo(executor)
    assert passo.estado == "feito"


def test_intervir_conflito_conta_so_intervencao_nova(executor):
    conflito = executor.w_state.mundo.conflitos["distribuicao"]
    conflito.intervencoes = 1
    passo = _passo(executor, "intervir_conflito", "distribuicao")
    capitulo.conferir_passo(executor)
    assert passo.estado == "atual"
    conflito.intervencoes = 2
    capitulo.conferir_passo(executor)
    assert passo.estado == "feito"


def test_enfrentar_chefe_cumpre_pela_vitoria(executor):
    passo = _passo(executor, "enfrentar_chefe")
    mundo.marcar_chefe_enfrentado(executor.w_state)
    capitulo.conferir_passo(executor)
    assert passo.estado == "feito"


def test_passo_impossivel_e_pulado_sem_xp(executor):
    passo = _passo(executor, "falar_pessoa", "responsavel")
    executor.w_state.mundo.pessoas["responsavel"].disposicao = "ausente"
    xp = executor.heroi.xp or 0
    capitulo.conferir_passo(executor)
    assert passo.estado == "pulado" and (executor.heroi.xp or 0) == xp
    assert _arco(executor).passo_pendente is True


def test_nao_confere_passo_durante_combate(executor):
    passo = _passo(executor, "registrar_fato")
    mundo.registrar_fato(executor, "Fato novo.")
    executor.c_state.ativo = True
    capitulo.conferir_passo(executor)
    assert passo.estado == "atual"


# -- próximo passo --------------------------------------------------------

def test_candidatos_sao_verificaveis_falsos_e_sem_nome_do_chefe(executor):
    capitulo.garantir_passo(executor.w_state, executor.heroi)
    agir(executor, "agir_no_mundo", acao="conversar", alvo="responsavel")
    arco = _arco(executor)
    candidatos = capitulo.candidatos_passo(executor.w_state, executor.heroi)
    assert 1 <= len(candidatos) <= capitulo.MAX_CANDIDATOS
    chaves = {(c.condicao.tipo, c.condicao.alvo) for c in candidatos}
    assert ("falar_pessoa", "responsavel") not in chaves  # já feito neste capítulo
    assert ("investigar", "registro") in chaves and ("falar_pessoa", "interlocutora") in chaves
    assert all(arco.chefe.casefold() not in c.texto.casefold() for c in candidatos)


def test_ia_escolhe_o_candidato_e_redige(executor):
    capitulo.garantir_passo(executor.w_state, executor.heroi)
    agir(executor, "agir_no_mundo", acao="conversar", alvo="responsavel")
    candidatos = capitulo.candidatos_passo(executor.w_state, executor.heroi)
    indice = next(i for i, c in enumerate(candidatos) if c.condicao.tipo == "investigar")
    chamar = _resposta_ia({"candidato": indice, "texto": "Descubra o que o livro de registro esconde."})
    passo = capitulo.proximo_passo(executor.w_state, executor.heroi, executor.q_state, chamar_fn=chamar)
    assert passo is not None and passo.origem == "ia"
    assert passo.texto == "Descubra o que o livro de registro esconde."
    assert (passo.condicao.tipo, passo.condicao.alvo) == ("investigar", "registro")
    assert _arco(executor).passo_pendente is False
    assert "Íria" in chamar.msgs[0]["content"]  # o que o jogador fez entra no pedido


def test_resposta_ruim_da_ia_cai_no_molde_do_servidor(executor):
    for ruim in ({"candidato": 99, "texto": "Um passo qualquer."}, {"candidato": 0, "texto": ""},
                 {"candidato": "zero"}, {"candidato": 0, "texto": "Derrote o Bugbear na ponte."}):
        capitulo.garantir_passo(executor.w_state, executor.heroi)
        arco = _arco(executor)
        arco.passos = [p for p in arco.passos if p.estado != "atual"]
        arco.passo_pendente = True
        passo = capitulo.proximo_passo(executor.w_state, executor.heroi, executor.q_state,
                                       chamar_fn=_resposta_ia(ruim))
        assert passo is not None and passo.origem == "servidor", ruim
        assert "bugbear" not in passo.texto.casefold()


def test_ia_fora_do_ar_nao_trava_a_trilha(executor):
    def chamar(msgs, **_):
        raise RuntimeError("cota esgotada")

    arco = _arco(executor)
    arco.passo_pendente = True
    passo = capitulo.proximo_passo(executor.w_state, executor.heroi, executor.q_state, chamar_fn=chamar)
    assert passo is not None and passo.origem == "servidor"


def test_sem_pendencia_nao_gera_nem_chama_a_ia(executor):
    capitulo.garantir_passo(executor.w_state, executor.heroi)

    def chamar(msgs, **_):
        raise AssertionError("não devia chamar a IA")

    assert capitulo.proximo_passo(executor.w_state, executor.heroi, executor.q_state, chamar_fn=chamar) is None


# -- fechamento -----------------------------------------------------------

def _tres_passos_feitos(executor):
    arco = _arco(executor)
    arco.passos = [
        Passo(id=f"p{n}", texto=f"Passo {n}.", condicao=CondicaoPasso(tipo="registrar_fato"), estado="feito")
        for n in range(1, 4)
    ]
    return arco


def test_capitulo_exige_passos_em_vez_de_turnos(executor):
    arco = _arco(executor)
    executor.w_state.mundo.conflitos[arco.conflito_central].estado = "resolvido"
    mundo.registrar_fato(executor, "Um.")
    mundo.registrar_fato(executor, "Dois.")
    executor.w_state.turno = 50
    cond = mundo.condicoes_arco(executor.w_state)
    assert cond["pode_encerrar"] is False and "passos" in cond["motivo_bloqueio"]
    _tres_passos_feitos(executor)
    assert mundo.condicoes_arco(executor.w_state)["pode_encerrar"] is True


def test_quando_pode_encerrar_o_passo_atual_vira_fechar_o_capitulo(executor):
    arco = _tres_passos_feitos(executor)
    pendente = _passo(executor, "falar_pessoa", "interlocutora")
    executor.w_state.mundo.conflitos[arco.conflito_central].estado = "resolvido"
    mundo.registrar_fato(executor, "Um.")
    mundo.registrar_fato(executor, "Dois.")
    capitulo.conferir_passo(executor)
    assert pendente.estado == "pulado"
    atual = capitulo.passo_atual(arco)
    assert atual is not None and atual.condicao.tipo == "encerrar_capitulo" and arco.passo_pendente is False


def test_encerrar_marca_o_ultimo_passo_e_abandonar_nao(executor):
    arco = _tres_passos_feitos(executor)
    executor.w_state.mundo.conflitos[arco.conflito_central].estado = "resolvido"
    mundo.registrar_fato(executor, "Um.")
    mundo.registrar_fato(executor, "Dois.")
    capitulo.conferir_passo(executor)
    executor.rng = RngFixo([3] * 12)
    r, ok = agir(executor, "encerrar_arco")
    assert ok, r
    assert arco.passos[-1].condicao.tipo == "encerrar_capitulo" and arco.passos[-1].estado == "feito"


def test_abrir_arco_deixa_o_primeiro_passo_pendente(executor):
    mundo.encerrar_arco(executor, abandonar=True)
    r, ok = agir(executor, "abrir_arco", titulo="A Segunda Disputa", premissa="p", conflito="distribuicao")
    assert ok, r
    assert _arco(executor).passo_pendente is True


# -- painel e ferramentas -------------------------------------------------

def test_painel_mostra_a_trilha_sem_segredos(executor, monkeypatch):
    monkeypatch.setattr(llm_client, "clients", {})
    capitulo.garantir_passo(executor.w_state, executor.heroi)
    agir(executor, "agir_no_mundo", acao="conversar", alvo="responsavel")
    capitulo.proximo_passo(executor.w_state, executor.heroi, executor.q_state)
    executor.q_state.objetivo_missao = "Encontrar minha irmã"
    painel = capitulo.painel_capitulo(executor.w_state, executor.q_state)
    assert painel["ativo"] and painel["numero"] == 1 and painel["objetivo"] == "Encontrar minha irmã"
    assert [p["estado"] for p in painel["passos"]] == ["feito", "atual"]
    assert set(painel["passos"][0]) == {"texto", "estado", "evidencia"}
    assert "chefe" not in painel and "Bugbear" not in json.dumps(painel, ensure_ascii=False)
    mundo.encerrar_arco(executor, abandonar=True)
    painel = capitulo.painel_capitulo(executor.w_state, executor.q_state)
    assert painel["ativo"] is False
    assert painel["anteriores"] == [{"numero": 1, "titulo": "A disputa por sementes", "resultado": "abandono"}]


def test_painel_de_save_sem_arco_nao_quebra():
    painel = capitulo.painel_capitulo(WorldState(), SimpleNamespace(objetivo_missao=""))
    assert painel["ativo"] is False and painel["passos"] == [] and painel["anteriores"] == []


def _nomes(c_state, acao, w_state):
    return {t["function"]["name"] for t in tools_para(c_state, acao, w_state)}


def test_ferramentas_de_arco_aparecem_pelo_estado_nao_pela_palavra(executor):
    acao = "Olho em volta."  # nenhuma palavra de "progressão"
    assert "encerrar_arco" not in _nomes(executor.c_state, acao, executor.w_state)
    arco = _tres_passos_feitos(executor)
    executor.w_state.mundo.conflitos[arco.conflito_central].estado = "resolvido"
    mundo.registrar_fato(executor, "Um.")
    mundo.registrar_fato(executor, "Dois.")
    assert "encerrar_arco" in _nomes(executor.c_state, acao, executor.w_state)
    mundo.encerrar_arco(executor, abandonar=True)
    executor.w_state.mundo.conflitos["distribuicao"].estado = "ativo"
    assert "abrir_arco" in _nomes(executor.c_state, acao, executor.w_state)


def test_concluir_objetivo_nao_existe_mais(executor):
    # O XP de progresso é o dos passos, conferidos pelo servidor; a ferramenta saiu.
    from app.services.tools import TOOLS_SCHEMA, ToolExecutor

    assert "concluir_objetivo" not in {t["function"]["name"] for t in TOOLS_SCHEMA}
    assert "concluir_objetivo" not in ToolExecutor._DESPACHO


# -- caminho real: clique, conferência, próximo passo, recarga ---------------

def test_clique_fecha_o_passo_e_a_resposta_ja_traz_o_seguinte(monkeypatch):
    from fastapi.testclient import TestClient

    from app.infra.db import Personagem, SessionLocal
    from app.main import app
    from tests.test_smoke import _payload_base

    monkeypatch.setattr(llm_client, "clients", {})  # sem IA: o servidor redige pelo molde
    client = TestClient(app)
    sid = client.post("/create_character", json=_payload_base(nome="Trilheira")).json()["session_id"]
    carga = client.post("/load_game", json={"session_id": sid}).json()
    trilha = carga["capitulo"]
    assert trilha["ativo"] and [p["estado"] for p in trilha["passos"]] == ["atual"]
    with SessionLocal() as db:
        mundo_salvo = db.query(Personagem).filter_by(session_id=sid).one().world_state
    arco = mundo_salvo["mundo"]["arcos"][0]
    assert arco["passos"][0]["condicao"]["tipo"] == "falar_pessoa"  # a migração foi gravada no /load_game
    alvo = arco["passos"][0]["condicao"]["alvo"]
    resposta = client.post("/game/action", json={
        "session_id": sid, "acao": "agir_no_mundo", "operacao": "conversar", "alvo": alvo,
        "turno_esperado": carga["revisao"],
    })
    assert resposta.status_code == 200, resposta.text
    corpo = resposta.json()
    assert [p["estado"] for p in corpo["capitulo"]["passos"]] == ["feito", "atual"]
    assert "Passo cumprido" in corpo["narrativa"]
    recarga = client.post("/load_game", json={"session_id": sid}).json()
    assert recarga["capitulo"]["passos"] == corpo["capitulo"]["passos"]
