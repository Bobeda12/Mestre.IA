"""Schema Pydantic do golden dataset (`evals/golden/*.yaml`). Reaproveita os
modelos tipados de `app/domain/state.py` e `app/domain/memoria.py` em vez de
duplicá-los — um cenário é, no fundo, um `WorldState`/`CombatState`/
`ResumoRolante` de partida, mais uma ação de jogador e o resultado
esperado."""

from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel

from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState

GOLDEN_DIR = Path(__file__).parent / "golden"

Categoria = Literal[
    "combate",
    "regra_ambigua",
    "acao_impossivel",
    "memoria_longo_prazo",
    "injecao_prompt",
    "caso_limite",
]


class EventoMemoriaSemente(BaseModel):
    """Um evento de memória de longo prazo pré-existente, para cenários da
    categoria `memoria_longo_prazo` — vira um `hybrid_search.Documento` em
    memória no harness, sem precisar de banco real (ver evals/harness.py)."""

    turno: int
    texto: str


class EstadoInicialCenario(BaseModel):
    # Subconjunto de campos de app.infra.db.Personagem — só os que
    # montar_contexto/ToolExecutor de fato leem (mesmo padrão de
    # tests/test_tools.py::_heroi: um Personagem() solto, nunca persistido).
    heroi: dict[str, Any]
    combate: CombatState = CombatState()
    mundo: WorldState
    missao: QuestLog = QuestLog()
    resumo_rolante: ResumoRolante = ResumoRolante()
    eventos_memoria: list[EventoMemoriaSemente] = []


class CenarioAvaliacao(BaseModel):
    id: str
    categoria: Categoria
    descricao: str
    estado_inicial: EstadoInicialCenario
    acao_jogador: str
    # Nem toda categoria espera uma ferramenta específica (ex: injecao_prompt
    # quer justamente ver se o modelo NÃO chama nada indevido) — None significa
    # "não avaliar tool-call accuracy para este cenário", não "erro".
    ferramenta_esperada: str | None = None
    args_esperados: dict[str, Any] = {}
    resultado_mecanico_esperado: str = ""
    notas_rubrica: str = ""


def carregar_cenarios(diretorio: Path | None = None) -> list[CenarioAvaliacao]:
    """Carrega e valida todo `evals/golden/*.yaml`. Cada arquivo é uma
    categoria (o campo `categoria` de cada cenário continua sendo a fonte de
    verdade, não o nome do arquivo). O YAML de cada arquivo é uma lista de
    cenários OU um mapa com uma chave `cenarios:` — a segunda forma existe
    para o arquivo poder ter uma âncora `&heroi_padrao` como vizinha da
    lista, reaproveitada via `<<: *heroi_padrao` em cada cenário, sem repetir
    os mesmos 8 campos do herói 60 vezes. IDs duplicados entre arquivos são
    um erro de dataset, não silenciado."""
    diretorio = diretorio or GOLDEN_DIR
    cenarios: list[CenarioAvaliacao] = []
    vistos: set[str] = set()
    for caminho in sorted(diretorio.glob("*.yaml")):
        bruto = yaml.safe_load(caminho.read_text(encoding="utf-8")) or []
        lista = bruto.get("cenarios", []) if isinstance(bruto, dict) else bruto
        for item in lista:
            cenario = CenarioAvaliacao.model_validate(item)
            if cenario.id in vistos:
                raise ValueError(f"id de cenário duplicado: '{cenario.id}' (em {caminho.name})")
            vistos.add(cenario.id)
            cenarios.append(cenario)
    return cenarios
