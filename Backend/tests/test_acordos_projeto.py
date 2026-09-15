"""Interesses concorrentes sem aceite da IA nem recursos concedidos por promessa."""

import pytest

from app.domain.living_world import PessoaMundo
from app.domain.state import WorldState
from app.services.contexto_ia import registros_mundo
from app.services.tools import tools_para
from tests.test_emergencia import chamar, proposta
from tests.test_emergencia import executor as executor
from tests.test_projetos import iniciar


def oferta(npc="zelador", **kwargs):
    return {"id": npc, "npc": npc, "condicao": "acesso", "oferta": "Ajudo a reparar o sino",
            "contrapartida": "Preserve o acesso gratuito", "motivo_declarado": "O sino pertence à comunidade",
            "exclusiva": True, **kwargs}


def preparar(ex):
    pid = iniciar(ex)
    ex.w_state.mundo.pessoas["mercadora"] = PessoaMundo(
        id="mercadora", nome="Lia", local=ex.w_state.local, objetivo="Financiar a obra",
    )
    for npc in ("zelador", "mercadora"):
        assert chamar(ex, "propor_acordo_projeto", projeto=pid, proposta=oferta(npc))[1]
    return pid


def decidir(ex, pid, acordo, operacao="aceitar"):
    return chamar(ex, "decidir_acordo_projeto", projeto=pid, acordo=acordo, operacao=operacao)


def test_proposta_nao_aceita_sozinha_e_preserva_termos(executor):
    pid = preparar(executor)
    a = executor.w_state.mundo.projetos[pid].propostas[0]
    assert a.estado == "oferecida" and not executor.w_state.mundo.pessoas["zelador"].promessas
    chamar(executor, "propor_acordo_projeto", projeto=pid, proposta=oferta(oferta="Entrega automática"))
    assert a.oferta == "Ajudo a reparar o sino"
    assert "decidir_acordo_projeto" not in {t["function"]["name"] for t in tools_para(executor.c_state)}


def test_exclusividade_renuncia_e_memoria_causal(executor):
    pid = preparar(executor)
    inventario = list(executor.heroi.inventario)
    confianca = executor.w_state.mundo.pessoas["zelador"].confianca
    resultado, ok = decidir(executor, pid, "zelador")
    assert ok and resultado["acontecimento_id"]
    antes = executor.w_state.model_dump_json()
    assert not decidir(executor, pid, "mercadora")[1]
    assert executor.w_state.model_dump_json() == antes
    assert decidir(executor, pid, "zelador", "renunciar")[1]
    assert decidir(executor, pid, "mercadora")[1]
    assert executor.heroi.inventario == inventario
    assert executor.w_state.mundo.pessoas["zelador"].confianca == confianca
    assert "renunciada" in executor.w_state.mundo.pessoas["zelador"].lembrancas[-1]


@pytest.mark.parametrize("caso", ["ausente", "combate", "inconsciente", "decidida"])
def test_decisao_invalida_atomica(executor, caso):
    pid = preparar(executor)
    if caso == "ausente":
        executor.w_state.mundo.pessoas["zelador"].disposicao = "ausente"
    elif caso == "combate":
        executor.c_state.ativo = True
    elif caso == "inconsciente":
        executor.heroi.hp_atual = 0
    else:
        decidir(executor, pid, "zelador", "recusar")
    antes = executor.w_state.model_dump_json()
    assert not decidir(executor, pid, "zelador")[1]
    assert executor.w_state.model_dump_json() == antes


def test_cumprimento_real_exclusividade_e_persistencia_apos_abandono(executor):
    pid = preparar(executor)
    assert decidir(executor, pid, "zelador")[1]
    assert not chamar(executor, "cumprir_acordo_projeto", projeto=pid, acordo="zelador",
                      origem="inventada", evidencia="Prometo cumprir")[1]
    fato = "O sino tem acesso gratuito garantido"
    resultado, _ = chamar(executor, "resolver_intencao", proposta=proposta(
        sucesso=[{"tipo": "condicao", "alvo": "sino", "texto": fato}],
    ))
    assert chamar(executor, "cumprir_acordo_projeto", projeto=pid, acordo="zelador",
                  origem=resultado["acontecimento_id"], evidencia=fato)[1]
    assert not decidir(executor, pid, "mercadora")[1]
    assert chamar(executor, "gerir_projeto", operacao="abandonar", projeto=pid)[1]
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    assert salvo.mundo.projetos[pid].propostas[0].estado == "cumprida"
    assert decidir(executor, pid, "zelador", "renunciar")[1]


def test_contexto_separa_acordos_sem_perder_ambicao(executor):
    pid = preparar(executor)
    registros = registros_mundo(executor.w_state)
    principal = next(r for r in registros if r["ref"] == f"projetos/{pid}")
    assert "propostas" not in principal["dados"]
    assert len([r for r in registros if r["ref"].startswith(f"acordos/{pid}/")]) == 2


def test_npc_distante_nao_conhece_ambicao_por_telepatia(executor):
    pid = iniciar(executor)
    executor.w_state.mundo.projetos[pid].local = "Outro reino"
    assert not chamar(executor, "propor_acordo_projeto", projeto=pid, proposta=oferta())[1]
