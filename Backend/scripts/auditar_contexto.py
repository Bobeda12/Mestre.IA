"""Benchmark local reproduzível; não chama IA nem abre saves reais."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.domain.living_world import Conhecimento, MundoVivo  # noqa: E402
from app.domain.memoria import ResumoRolante  # noqa: E402
from app.domain.state import CombatState, QuestLog, WorldState  # noqa: E402
from app.infra.db import Personagem  # noqa: E402
from app.services.emergent_start import criar_origem  # noqa: E402
from app.services.narrator import montar_contexto  # noqa: E402
from app.services.rag_regras import _secoes  # noqa: E402
from app.services.tools import tools_para  # noqa: E402


def cenario(longo=False):
    heroi = Personagem(
        nome="Lia", raca="Humano", classe="Guerreiro", nivel=1, xp=0, hp_atual=12, hp_max=15,
        defesa=14, ouro=10, inventario=["Espada Longa", "Tocha"], atributos={"forca": 14},
        dificuldade="Normal", objetivo="Encontrar minha irmã", background="Mensageira",
        historia_texto="Procuro notícias da minha irmã.", resumo_rolante={}, historico_chat=[],
    )
    abertura = criar_origem(heroi, 31)
    estado = WorldState(local=abertura["local_inicial"], mundo=MundoVivo.model_validate(abertura["mundo_inicial"]))
    resumo = ResumoRolante()
    if longo:
        resumo.fatos_estabelecidos = [f"Na viagem {i}, Lia protegeu os documentos do conselho e mudou de rota."
                                     for i in range(160)]
        resumo.promessas_feitas = [f"Lia prometeu investigar o desaparecimento de uma carga em Ponte {i}."
                                  for i in range(60)]
        estado.mundo.conhecimento = [Conhecimento(texto=f"O mensageiro {i} passou pelo porto.",
                                                 fonte="Observação", natureza="fato") for i in range(100)]
    return heroi, estado, CombatState(), QuestLog(), resumo


def medir():
    resultados = []
    for nome, longo in [("inicio", False), ("campanha_longa", True)]:
        h, w, c, q, resumo = cenario(longo)
        prompt = montar_contexto(h, w, c, q, resumo=resumo, regras_relevantes=_secoes()[:5])
        schemas = tools_para(c, "Observo os arredores", w)
        caracteres = len(prompt) + len(json.dumps(schemas, ensure_ascii=False, separators=(",", ":")))
        resultados.append({"cenario": nome, "prompt_chars": len(prompt), "ferramentas": len(schemas),
                           "entrada_chars": caracteres, "tokens_estimados": (caracteres + 2) // 3})
    return resultados


if __name__ == "__main__":
    print(json.dumps(medir(), ensure_ascii=False, indent=2))
