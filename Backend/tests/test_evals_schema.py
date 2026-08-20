"""Testa evals/schema.py — o golden dataset de verdade (evals/golden/*.yaml)
precisa carregar e validar sem erro, e sem ids duplicados entre arquivos."""

from collections import Counter

from evals.schema import CenarioAvaliacao, carregar_cenarios


def test_golden_dataset_carrega_60_cenarios_validos():
    cenarios = carregar_cenarios()
    assert len(cenarios) == 60
    assert all(isinstance(c, CenarioAvaliacao) for c in cenarios)


def test_golden_dataset_sem_ids_duplicados():
    cenarios = carregar_cenarios()
    ids = [c.id for c in cenarios]
    assert len(ids) == len(set(ids))


def test_golden_dataset_cobre_as_6_categorias_com_10_cada():
    cenarios = carregar_cenarios()
    contagem = Counter(c.categoria for c in cenarios)
    assert contagem == {
        "combate": 10,
        "regra_ambigua": 10,
        "acao_impossivel": 10,
        "memoria_longo_prazo": 10,
        "injecao_prompt": 10,
        "caso_limite": 10,
    }


def test_cenario_com_ferramenta_esperada_ausente_e_valido():
    cenario = CenarioAvaliacao.model_validate(
        {
            "id": "teste_minimo",
            "categoria": "caso_limite",
            "descricao": "cenário mínimo só para validar o schema",
            "estado_inicial": {
                "heroi": {"nome": "X", "classe": "Guerreiro", "hp_atual": 1, "hp_max": 1, "defesa": 10},
                "mundo": {"local": "Teste"},
            },
            "acao_jogador": "eu espero.",
        }
    )
    assert cenario.ferramenta_esperada is None
    assert cenario.estado_inicial.combate.ativo is False
    assert cenario.estado_inicial.eventos_memoria == []
