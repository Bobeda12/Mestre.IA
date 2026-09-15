"""Orçamento conservador de payload; estimativa não é tokenização do provedor."""

import logging
import math

from app.infra.llm_client import ErroMestre
from app.infra.settings import settings
from app.services.contexto_ia import serializar

logger = logging.getLogger(__name__)


class OrcamentoTurno:
    def __init__(self):
        self.acumulado = 0
        self.chamadas = 0

    def registrar(self, msgs: list[dict], tools: list[dict]) -> None:
        mensagens = math.ceil(len(serializar(msgs)) / 3)
        ferramentas = math.ceil(len(serializar(tools)) / 3)
        total = mensagens + ferramentas
        if total > settings.agent_limite_entrada_estimado or (
            self.acumulado + total > settings.agent_limite_turno_estimado
        ):
            raise ErroMestre("O Mestre atingiu o orçamento de contexto deste turno. Tente uma ação mais específica.")
        self.acumulado += total
        self.chamadas += 1
        logger.info("contexto_ia chamada=%d mensagens_estimadas=%d ferramentas_estimadas=%d acumulado_estimado=%d",
                    self.chamadas, mensagens, ferramentas, self.acumulado)


def resultado_compacto(resultado: dict, limite: int = 4500) -> str:
    """Mantém campos inteiros e o resultado mecânico; sinaliza detalhes omitidos."""
    completo = serializar(resultado)
    if len(completo) <= limite:
        return completo
    essenciais = {"erro", "sucesso", "descricao", "acontecimento_id", "dano", "hp_atual", "hp_max",
                  "vitoria", "morte", "encerrado", "total", "rolagem", "cd", "critico"}
    reduzido = {k: v for k, v in resultado.items() if k in essenciais}
    omitidos = []
    for k, v in resultado.items():
        if k in reduzido:
            continue
        if len(serializar({**reduzido, k: v})) < limite - 200:
            reduzido[k] = v
        else:
            omitidos.append(k)
    reduzido["detalhes_omitidos"] = omitidos
    reduzido["consulta"] = "Detalhes extensos omitidos; consultar_contexto recupera o estado atual."
    return serializar(reduzido)
