import json
import random

import pytest
from fastapi.testclient import TestClient

from app.domain.living_world import Conhecimento, MundoVivo
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra import llm_client
from app.infra.db import Personagem, SessionLocal
from app.main import app
from app.services.emergent_start import criar_origem, validar_mundo_inicial
from app.services.living_world import avancar_tempo, painel_mundo
from app.services.tools import ToolExecutor
from tests.helpers import RngFixo
from tests.test_smoke import _payload_base

client = TestClient(app)


@pytest.fixture
def executor():
    heroi = Personagem(
        nome="Lia",
        raca="Humano",
        classe="Guerreiro",
        nivel=1,
        xp=0,
        hp_atual=30,
        hp_max=30,
        defesa=15,
        atributos={"forca": 16, "destreza": 14, "inteligencia": 12, "carisma": 14},
        inventario=["Tocha", "Poção de Cura"],
        dificuldade="Normal",
        reputacao_npcs={},
        monstros_derrotados={},
        objetivo="Encontrar minha irmã",
        background="Mensageira",
        historia_texto="Procuro notícias da minha irmã.",
    )
    abertura = criar_origem(heroi, 31)
    estado = WorldState(
        local=abertura["local_inicial"], mundo=MundoVivo.model_validate(abertura["mundo_inicial"]), versao_progressao=1
    )
    return ToolExecutor(heroi, CombatState(), estado, QuestLog(), random.Random(5))


def agir(executor, nome, **args):
    turno = ToolExecutor(executor.heroi, executor.c_state, executor.w_state, executor.q_state, executor.rng)
    resultado, valido = turno.executar(nome, json.dumps(args, ensure_ascii=False))
    executor.eventos = turno.eventos
    return resultado, valido


def test_bloquear_recarregar_e_registrar_nao_restaura_porta(executor):
    executor.rng = RngFixo([20])
    resultado, valido = agir(executor, "agir_no_mundo", acao="bloquear", alvo="passagem", meio="estante")
    assert valido and resultado["sucesso"]
    local = executor.w_state.local
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    executor.w_state = salvo
    porta = salvo.mundo.cenas[local].entidades["passagem"]
    assert porta.estado == "bloqueado" and porta.bloqueado_por == "estante"
    _, valido = agir(
        executor,
        "registrar_cena",
        descricao="A sala novamente",
        entidades=[
            {"id": "passagem", "nome": "Porta nova", "tipo": "saida", "estado": "aberto"},
        ],
    )
    assert valido
    assert porta.estado == "bloqueado"
    resultado, valido = agir(executor, "agir_no_mundo", acao="atravessar", alvo="passagem")
    assert not valido and "bloqueada" in resultado["erro"]
    assert executor.w_state.local == local


def test_meio_inexistente_nao_altera_estado_nem_tempo(executor):
    antes = executor.w_state.model_dump_json()
    resultado, valido = agir(executor, "agir_no_mundo", acao="bloquear", alvo="passagem", meio="dragao")
    assert not valido and "meio" in resultado["erro"]
    assert antes == executor.w_state.model_dump_json()


def test_falha_nao_permite_repeticao_identica_mas_permite_outro_caminho(executor):
    executor.rng = RngFixo([1])
    resultado, valido = agir(executor, "agir_no_mundo", acao="destrancar", alvo="passagem")
    assert valido and not resultado["sucesso"]
    tempo = executor.w_state.mundo.minutos
    _, valido = agir(executor, "agir_no_mundo", acao="destrancar", alvo="passagem")
    assert not valido and executor.w_state.mundo.minutos == tempo
    _, valido = agir(executor, "agir_no_mundo", acao="atravessar", alvo="estrada")
    assert valido and executor.w_state.local == "Estrada livre"


def test_ignorar_conflito_sair_voltar_preserva_consequencias(executor):
    local = executor.w_state.local
    _, valido = agir(executor, "agir_no_mundo", acao="atravessar", alvo="estrada")
    assert valido
    avancar_tempo(executor, 1000)
    conflito = executor.w_state.mundo.conflitos["distribuicao"]
    assert conflito.estado == "concretizado"
    assert executor.w_state.mundo.cenas[local].entidades["passagem"].estado == "bloqueado"
    assert not any(f.texto == conflito.consequencia for f in executor.w_state.mundo.conhecimento)
    _, valido = agir(executor, "agir_no_mundo", acao="atravessar", alvo="retorno")
    assert valido and executor.w_state.local == local
    assert any(f.texto == conflito.consequencia for f in executor.w_state.mundo.conhecimento)


def test_exploracao_tem_recompensa_unica_sem_rolar_por_pista_essencial(executor):
    resultado, valido = agir(executor, "agir_no_mundo", acao="investigar", alvo="registro")
    assert valido and resultado["sucesso"]
    assert executor.heroi.xp > 0
    xp = executor.heroi.xp
    agir(executor, "agir_no_mundo", acao="investigar", alvo="registro")
    assert executor.heroi.xp == xp
    assert any(f.natureza == "fato" for f in executor.w_state.mundo.conhecimento)


def test_segredos_e_consequencias_futuras_nao_vazam_no_painel(executor):
    npc = executor.w_state.mundo.pessoas["responsavel"]
    npc.segredo = "SEGREDO_UNICO"
    npc.medo = "MEDO_UNICO"
    painel = json.dumps(painel_mundo(executor.w_state, "Guerreiro"), ensure_ascii=False)
    assert "SEGREDO_UNICO" not in painel and "MEDO_UNICO" not in painel
    assert "consequencia" not in painel
    privado = json.dumps(painel_mundo(executor.w_state, "Guerreiro", privado=True))
    assert "SEGREDO_UNICO" in privado


def test_boato_de_npc_nao_vira_fato_e_promessa_persiste(executor):
    npc = executor.w_state.mundo.pessoas["responsavel"]
    npc.conhecimentos = [Conhecimento(texto="O prefeito roubou a carga", fonte=npc.nome, natureza="boato")]
    agir(executor, "agir_no_mundo", acao="conversar", alvo=npc.id)
    assert executor.w_state.mundo.conhecimento[-1].natureza == "boato"
    agir(executor, "registrar_vinculo", npc=npc.id, natureza="promessa", texto="Voltarei com notícias.")
    salvo = WorldState.model_validate_json(executor.w_state.model_dump_json())
    assert "Voltarei com notícias." in salvo.mundo.pessoas[npc.id].promessas


def test_negociar_preserva_limite_e_relembra_proposta(executor):
    executor.rng = RngFixo([20])
    npc = executor.w_state.mundo.pessoas["responsavel"]
    resultado, valido = agir(
        executor,
        "agir_no_mundo",
        acao="negociar",
        alvo=npc.id,
        proposta="Vamos ouvir a outra parte antes de fechar o depósito.",
    )
    assert valido and resultado["sucesso"]
    assert resultado["limite"] == npc.limite
    assert npc.disposicao == "cooperativo" and npc.lembrancas


def test_acordo_resolve_conflito_e_da_xp_uma_vez(executor):
    executor.rng = RngFixo([20, 20, 6])
    npc = executor.w_state.mundo.pessoas["responsavel"]
    npc.disposicao = "cooperativo"
    for _ in range(2):
        resultado, valido = agir(
            executor,
            "intervir_conflito",
            conflito="distribuicao",
            abordagem="resolver",
            proposta="Dividir o acesso e preservar as pessoas protegidas.",
        )
        assert valido and resultado["sucesso"]
    assert executor.w_state.mundo.conflitos["distribuicao"].estado == "resolvido"
    xp = executor.heroi.xp
    assert xp > 0
    _, valido = agir(executor, "intervir_conflito", conflito="distribuicao", abordagem="resolver", proposta="Repetir")
    assert not valido and executor.heroi.xp == xp


def test_especializacao_exige_nivel_e_fora_de_combate(executor):
    _, valido = agir(executor, "escolher_especializacao", marco="3", escolha="diplomata")
    assert not valido
    executor.heroi.nivel = 3
    _, valido = agir(executor, "escolher_especializacao", marco="3", escolha="diplomata")
    assert valido
    executor.c_state.ativo = True
    _, valido = agir(executor, "escolher_especializacao", marco="3", escolha="combatente")
    assert not valido
    assert executor.w_state.mundo.especializacoes == {"3": "diplomata"}


def test_uma_acao_principal_por_turno_tambem_para_texto_livre(executor):
    resultado, valido = executor.executar("agir_no_mundo", '{"acao":"investigar","alvo":"registro"}')
    assert valido
    resultado, valido = executor.executar("agir_no_mundo", '{"acao":"atravessar","alvo":"estrada"}')
    assert not valido and "já foi resolvida" in resultado["erro"]


def test_objetivo_do_jogador_substitui_missao_sem_travar_conflito(executor):
    agir(executor, "definir_objetivo", objetivo="Abrir uma taverna na estrada")
    assert executor.q_state.objetivo_missao == "Abrir uma taverna na estrada"
    assert executor.w_state.mundo.conflitos["distribuicao"].estado == "ativo"


def test_origens_reprodutiveis_sem_atos_obrigatorios(executor):
    a = criar_origem(executor.heroi, 5)
    assert a == criar_origem(executor.heroi, 5)
    assert a != criar_origem(executor.heroi, 6)
    assert a["atos"] == []
    assert a["objetivo_missao"] == executor.heroi.objetivo
    assert validar_mundo_inicial(a["mundo_inicial"], a["local_inicial"])
    with pytest.raises(ValueError):
        validar_mundo_inicial(a["mundo_inicial"], "Local inventado sem estado")


def test_api_clique_e_texto_resolvem_mesma_operacao_e_save(monkeypatch):
    monkeypatch.setattr(llm_client, "clients", {})
    resposta = client.post("/create_character", json=_payload_base(nome="MundoPersistente"))
    assert resposta.status_code == 200
    sid = resposta.json()["session_id"]
    antes = client.post("/load_game", json={"session_id": sid}).json()
    assert antes["mundo"]["entidades"]
    resposta = client.post(
        "/game/action",
        json={
            "session_id": sid,
            "acao": "agir_no_mundo",
            "alvo": "registro",
            "operacao": "investigar",
            "turno_esperado": 1,
        },
    )
    assert resposta.status_code == 200, resposta.text
    depois = client.post("/load_game", json={"session_id": sid}).json()
    registro = next(e for e in depois["mundo"]["entidades"] if e["id"] == "registro")
    assert registro["descoberto"] and registro["pista"]
    assert depois["turno_mundo"] == 2 and depois["xp"] > antes["xp"]
    with SessionLocal() as db:
        heroi = db.query(Personagem).filter_by(session_id=sid).one()
        assert heroi.world_state["mundo"]["cenas"][depois["local"]]["entidades"]["registro"]["descoberto"]
