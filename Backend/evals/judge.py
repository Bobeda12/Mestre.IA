"""LLM-as-judge (Etapa 6, PLANO_MESTRE.md item 3): pontua a narrativa final
de um cenário em 4 eixos, 1-5, com uma rubrica fixa. Roda DEPOIS da
narrativa já gerada — não influencia o turno em si, só avalia o resultado.

Limitação registrada, não escondida (ver ADR-0011): por padrão o juiz usa o
mesmo modelo mais forte da cadeia de fallback do narrador
(`settings.model_name`) — não há um segundo provedor/família neste projeto
(ADR-0008) para separar "quem narra" de "quem julga" de verdade."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from pydantic import BaseModel, Field, ValidationError

from app.infra.llm_client import ErroMestre, chamar_modelo_unico
from app.infra.settings import settings
from evals.harness import ResultadoCenario

RUBRICA = """Você é um juiz avaliando a resposta de um mestre de RPG de IA. Dê uma nota de 1 a 5 em cada eixo:

1. aderencia_regras: a narrativa respeita o resultado mecânico já decidido pelo motor
   de regras (sem inventar sucesso/falha, sem conceder algo que nenhuma ferramenta concedeu)?
2. consistencia_memoria: a narrativa é coerente com os fatos/eventos/reputação de
   memória fornecidos, sem contradizer nem ignorar o que já é sabido?
3. impacto_narrativo: a narrativa tem tensão e ritmo (frase curta no perigo, mais longa
   na exploração), termina em movimento (nunca em cenário parado), e — em momentos de
   alto impacto (vida por um fio, chefe, golpe decisivo, prólogo) — deixa a emoção
   crescer em vez de ficar contida? Nota baixa também para prosa inchada ou clichê
   ("o ar estava pesado", "um silêncio ensurdecedor").
4. sem_alucinacao_inventario: a narrativa não menciona itens, ouro ou HP que não
   vieram do estado/ferramentas fornecidos?

Responda APENAS em JSON, sem texto fora do JSON:
{"aderencia_regras": N, "consistencia_memoria": N, "impacto_narrativo": N,
 "sem_alucinacao_inventario": N, "justificativa": "1-2 frases"}
"""

EIXOS = ("aderencia_regras", "consistencia_memoria", "impacto_narrativo", "sem_alucinacao_inventario")


class NotaJuiz(BaseModel):
    aderencia_regras: int = Field(ge=1, le=5)
    consistencia_memoria: int = Field(ge=1, le=5)
    impacto_narrativo: int = Field(ge=1, le=5)
    sem_alucinacao_inventario: int = Field(ge=1, le=5)
    justificativa: str = ""

    @property
    def media(self) -> float:
        return sum(getattr(self, eixo) for eixo in EIXOS) / len(EIXOS)


def _prompt_juiz(resultado: ResultadoCenario) -> list[dict]:
    cenario = resultado.cenario
    contexto = f"""Cenário: {cenario.descricao}
Categoria: {cenario.categoria}
Ação do jogador: {cenario.acao_jogador}
Resultado mecânico esperado: {cenario.resultado_mecanico_esperado or "(não especificado)"}
Notas específicas deste cenário: {cenario.notas_rubrica or "(nenhuma)"}

Narrativa gerada pelo mestre:
\"\"\"{resultado.narrativa}\"\"\"
"""
    return [{"role": "system", "content": RUBRICA}, {"role": "user", "content": contexto}]


def julgar(
    resultado: ResultadoCenario,
    modelo: str | None = None,
    chamar_fn: Callable[..., Any] | None = None,
) -> NotaJuiz | None:
    """Devolve `None` (não uma exceção) se o juiz falhar ao responder, ou se
    o JSON não bater com o schema — quem chama conta isso como taxa de
    parse inválido em vez de derrubar a rodada inteira por um cenário."""
    if not resultado.narrativa.strip():
        return None
    modelo = modelo or settings.model_name
    chamar_fn = chamar_fn or chamar_modelo_unico
    msgs = _prompt_juiz(resultado)
    try:
        resp = chamar_fn(modelo, msgs, response_format={"type": "json_object"})
    except ErroMestre:
        return None
    try:
        bruto = json.loads(resp.choices[0].message.content)
        return NotaJuiz.model_validate(bruto)
    except (json.JSONDecodeError, AttributeError, ValidationError):
        return None


def julgar_lote(
    resultados: list[ResultadoCenario],
    modelo: str | None = None,
    chamar_fn: Callable[..., Any] | None = None,
) -> dict[str, NotaJuiz | None]:
    """Notas indexadas por `cenario.id` — é o que `evals/calibracao.py`
    cruza contra `evals/annotations/humanas.yaml`."""
    return {r.cenario.id: julgar(r, modelo=modelo, chamar_fn=chamar_fn) for r in resultados}


def taxa_parse_valido(notas: dict[str, NotaJuiz | None]) -> float:
    if not notas:
        return 1.0
    return sum(1 for n in notas.values() if n is not None) / len(notas)


def media_por_eixo(notas: dict[str, NotaJuiz | None]) -> dict[str, float]:
    validas = [n for n in notas.values() if n is not None]
    if not validas:
        return dict.fromkeys(EIXOS, 0.0)
    return {eixo: sum(getattr(n, eixo) for n in validas) / len(validas) for eixo in EIXOS}
