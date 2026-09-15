"""Unidades conservadas entre estoque, inventário e transporte, com cronologia real."""

import pytest

from app.domain.living_world import CenaPersistente, EntidadeCena, PessoaMundo
from app.domain.state import WorldState
from app.services.economia import estoque_atual, vitrine
from app.services.living_world import avancar_tempo
from tests.test_emergencia import chamar, proposta
from tests.test_emergencia import executor as executor


def mercado(ex):
    m = ex.w_state.mundo
    m.pessoas["bela"] = PessoaMundo(id="bela", nome="Bela", local=ex.w_state.local,
                                   objetivo="Abastecer o porto", mercadoria=["Poção de Cura"])
    m.pessoas["lia"] = PessoaMundo(id="lia", nome="Lia", local="Porto", objetivo="Vender",
                                  mercadoria=["Antídoto"])
    m.cenas["Porto"] = CenaPersistente()
    m.cenas[ex.w_state.local].entidades["estrada"] = EntidadeCena(
        id="estrada", nome="Estrada do porto", tipo="saida", destino="Porto",
    )
    ex.heroi.ouro = 1000
    return m.pessoas["bela"], m.pessoas["lia"]


def enviar(ex, **kwargs):
    resultado, _ = chamar(ex, "resolver_intencao", proposta=proposta())
    dados = {"id": "carga", "remetente": "bela", "destinatario": "lia", "passagem": "estrada",
             "item": "Poção de Cura", "quantidade": 2, "acontecimento": resultado["acontecimento_id"], **kwargs}
    resposta, ok = chamar(ex, "despachar_remessa", **dados)
    return dados, resposta, ok


def test_estoque_finito_persistido_e_recadastro_nao_reabastece(executor):
    bela, _ = mercado(executor)
    for _ in range(3):
        assert "erro" not in executor.comerciar("bela", "comprar", "Poção de Cura")
    ouro = executor.heroi.ouro
    assert "erro" in executor.comerciar("bela", "comprar", "Poção de Cura")
    assert executor.heroi.ouro == ouro
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    assert estoque_atual(salvo.mundo.pessoas["bela"])["Poção de Cura"] == 0
    chamar(executor, "registrar_pessoa", pessoa={
        "id": "bela", "nome": "Bela", "local": executor.w_state.local, "objetivo": "Vender",
        "mercadoria": ["Poção de Cura"], "estoque": {"Poção de Cura": 999}, "estoque_inicializado": True,
    })
    avancar_tempo(executor, 1440)
    assert estoque_atual(bela)["Poção de Cura"] == 0


def test_venda_devolve_unidade_ao_comerciante(executor):
    bela, _ = mercado(executor)
    assert "erro" not in executor.comerciar("bela", "vender", "Cimitarra")
    assert estoque_atual(bela)["Cimitarra"] == 1
    assert any(v["item"] == "Cimitarra" and v["quantidade"] == 1 for v in vitrine(bela))
    assert "erro" not in executor.comerciar("bela", "comprar", "Cimitarra")
    assert executor.heroi.inventario.count("Cimitarra") == 1
    assert estoque_atual(bela)["Cimitarra"] == 0


def test_transporte_reserva_entrega_uma_vez_e_pode_ser_comprado(executor):
    bela, lia = mercado(executor)
    dados, _, ok = enviar(executor)
    assert ok and estoque_atual(bela)["Poção de Cura"] == 1
    assert chamar(executor, "despachar_remessa", **dados)[1]
    assert estoque_atual(bela)["Poção de Cura"] == 1
    avancar_tempo(executor, 119)
    assert "Poção de Cura" not in estoque_atual(lia)
    avancar_tempo(executor, 1)
    avancar_tempo(executor, 480)
    assert estoque_atual(lia)["Poção de Cura"] == 2
    assert not chamar(executor, "despachar_remessa", **{**dados, "id": "duplicada"})[1]
    executor.w_state.local = "Porto"
    assert "erro" not in executor.comerciar("lia", "comprar", "Poção de Cura")
    assert estoque_atual(lia)["Poção de Cura"] == 1


def test_bloqueio_retem_carga_sem_perda_e_liberacao_entrega(executor):
    bela, lia = mercado(executor)
    enviar(executor)
    porta = executor.w_state.mundo.cenas[executor.w_state.local].entidades["estrada"]
    porta.estado = "bloqueado"
    avancar_tempo(executor, 120)
    assert executor.w_state.mundo.remessas["carga"].estado == "retida"
    assert "Poção de Cura" not in estoque_atual(lia)
    porta.estado = "intacto"
    avancar_tempo(executor, 10)
    assert estoque_atual(bela)["Poção de Cura"] + estoque_atual(lia)["Poção de Cura"] == 3
    assert executor.w_state.mundo.remessas["carga"].estado == "entregue"


@pytest.mark.parametrize("intervalo,estado", [(30, "retida"), (60, "retida"), (90, "entregue")])
def test_viagem_longa_respeita_ordem_entre_entrega_e_bloqueio(executor, intervalo, estado):
    mercado(executor)
    enviar(executor)
    assert chamar(executor, "registrar_conflito", conflito={
        "id": "fechar", "nome": "Fechar estrada", "agente": "zelador", "local": executor.w_state.local,
        "objetivo": "Inspecionar a estrada", "sinal": "Ivo prepara uma barreira", "consequencia": "Estrada fechada",
        "efeito": "bloquear", "alvo": "estrada", "intervalo": intervalo, "etapas": 2,
    })[1]
    hora = executor.w_state.hora_do_dia
    avancar_tempo(executor, 480)
    assert executor.w_state.mundo.remessas["carga"].estado == estado
    assert executor.w_state.hora_do_dia == (hora + 8) % 24


@pytest.mark.parametrize("mudanca", [{"quantidade": 4}, {"quantidade": True}, {"passagem": "inexistente"},
                                    {"acontecimento": "inventado"}, {"item": "Relíquia"}])
def test_remessa_invalida_nao_reserva_estoque(executor, mudanca):
    bela, lia = mercado(executor)
    _, _, ok = enviar(executor, **mudanca)
    assert not ok and not executor.w_state.mundo.remessas
    assert estoque_atual(bela) == {"Poção de Cura": 3}
    assert estoque_atual(lia) == {"Antídoto": 3}


def test_save_antigo_inicializa_estoque_sem_mutacao_na_leitura(executor):
    bela, _ = mercado(executor)
    dados = executor.w_state.model_dump()
    dados["mundo"].pop("remessas")
    for p in dados["mundo"]["pessoas"].values():
        p.pop("estoque")
        p.pop("estoque_inicializado")
    salvo = WorldState.model_validate(dados)
    assert estoque_atual(salvo.mundo.pessoas["bela"]) == {"Poção de Cura": 3}
    assert not bela.estoque_inicializado
