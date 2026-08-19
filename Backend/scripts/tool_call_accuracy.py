"""Mede tool-call accuracy (PLANO_MESTRE.md, Etapa 4): em N cenários fixos,
quantas vezes o modelo chama a ferramenta certa, com os argumentos certos.

Fora de tests/ de propósito — chama a API da Groq de verdade (precisa de
GROQ_API_KEY configurada), não entra no CI. Rodado duas vezes nesta etapa:
uma com as `description` originais de app/services/tools.py, outra depois de
reescrevê-las — os dois números vão para o diário e a Lição 05.

Uso: `uv run python scripts/tool_call_accuracy.py`
"""

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.infra.llm_client import chamar_com_fallback  # noqa: E402
from app.services.tools import TOOLS_SCHEMA  # noqa: E402


@dataclass
class Cenario:
    nome: str
    sistema: str
    acao: str
    ferramenta_esperada: str
    args_esperados: dict = field(default_factory=dict)


CENARIOS = [
    Cenario(
        nome="ataque_com_arma_nomeada",
        sistema='[COMBATE ATIVO] Inimigos vivos: [{"nome": "Goblin", "hp": 7}]. Inventário: ["Cimitarra"].',
        acao="Eu ataco o goblin com minha cimitarra!",
        ferramenta_esperada="atacar",
        args_esperados={"alvo": "goblin", "arma": "cimitarra"},
    ),
    Cenario(
        nome="ataque_sem_citar_arma",
        sistema='[COMBATE ATIVO] Inimigos vivos: [{"nome": "Esqueleto", "hp": 13}]. Inventário: ["Espada Curta"].',
        acao="Eu tento acertar o esqueleto com tudo que tenho!",
        ferramenta_esperada="atacar",
        args_esperados={"alvo": "esqueleto"},
    ),
    Cenario(
        nome="spawn_combate_lobo",
        sistema="[CENA] Floresta das Sombras. Um lobo emerge da neblina, rosnando, pronto para atacar.",
        acao="Eu me preparo para o confronto.",
        ferramenta_esperada="iniciar_combate",
        args_esperados={},
    ),
    Cenario(
        nome="mover_para_local_citado",
        sistema="[CENA] Vila de Phandalin, sem combate.",
        acao="Eu viajo até a Floresta das Sombras.",
        ferramenta_esperada="mover",
        args_esperados={"destino": "floresta das sombras"},
    ),
    Cenario(
        nome="teste_de_forca_para_escalar",
        sistema="[CENA] Masmorra Esquecida, sem combate. Há um muro alto de pedra bloqueando a passagem.",
        acao="Eu tento escalar o muro de pedra.",
        ferramenta_esperada="rolar_teste",
        args_esperados={"atributo": "forca"},
    ),
    Cenario(
        nome="usar_pocao_de_cura",
        sistema='[HEROI] HP: 3/10. Inventário: ["Poção de Cura"].',
        acao="Eu bebo minha poção de cura, estou quase morrendo.",
        ferramenta_esperada="usar_item",
        args_esperados={"item": "poção de cura"},
    ),
    Cenario(
        nome="comprar_item_da_loja",
        sistema="[CENA] Loja Escudo de Leão, sem combate. [HEROI] Ouro: 20.",
        acao="Eu compro uma corda de 15 metros da mercadora por 5 moedas de ouro.",
        ferramenta_esperada="gastar_ouro",
        args_esperados={"qtd": 5},
    ),
    Cenario(
        nome="armadilha_de_fosso",
        sistema="[CENA] Masmorra Esquecida, sem combate. Há uma placa de pressão suspeita no chão.",
        acao="Eu piso direto na placa de pressão, sem pensar duas vezes.",
        ferramenta_esperada="aplicar_dano",
        args_esperados={"alvo": "heroi"},
    ),
    Cenario(
        nome="consulta_meta_de_regra",
        sistema="[CENA] Vila de Phandalin, sem combate.",
        acao="Mestre, só uma dúvida de regra: como funciona o teste de morte quando eu chego a 0 de HP?",
        ferramenta_esperada="consultar_regra",
        args_esperados={},
    ),
    Cenario(
        nome="dar_item_de_recompensa",
        sistema="[CENA] Masmorra Esquecida, sem combate. Você venceu o Goblin, que carregava uma adaga enferrujada.",
        acao="Eu reviro o corpo do goblin em busca de qualquer coisa de valor.",
        ferramenta_esperada="dar_item",
        args_esperados={},
    ),
]


def _bate(valor_modelo, valor_esperado) -> bool:
    if isinstance(valor_esperado, str):
        return isinstance(valor_modelo, str) and valor_esperado.lower() in valor_modelo.lower()
    return valor_modelo == valor_esperado


def rodar() -> None:
    acertos_ferramenta = 0
    acertos_completos = 0
    for cenario in CENARIOS:
        msgs = [
            {"role": "system", "content": f"{cenario.sistema}\nVocê tem ferramentas para agir no mundo. Use-as."},
            {"role": "user", "content": cenario.acao},
        ]
        try:
            resp = chamar_com_fallback(msgs, tools=TOOLS_SCHEMA, tool_choice="auto")
        except Exception as e:  # nunca deixa um cenário derrubar o script inteiro
            print(f"[ERRO] {cenario.nome}: {e}")
            continue

        tool_calls = resp.choices[0].message.tool_calls or []
        if not tool_calls:
            print(f"[MISS] {cenario.nome}: modelo não chamou ferramenta nenhuma (só narrou)")
            continue

        chamada = tool_calls[0]
        nome_ok = chamada.function.name == cenario.ferramenta_esperada
        try:
            args = json.loads(chamada.function.arguments)
        except json.JSONDecodeError:
            args = {}

        args_ok = nome_ok and all(_bate(args.get(k), v) for k, v in cenario.args_esperados.items())

        if nome_ok:
            acertos_ferramenta += 1
        if args_ok:
            acertos_completos += 1

        status = "OK" if args_ok else ("FERRAMENTA CERTA, ARGS ERRADOS" if nome_ok else "FERRAMENTA ERRADA")
        chamado = f"{chamada.function.name!r}({chamada.function.arguments})"
        print(f"[{status}] {cenario.nome}: esperado={cenario.ferramenta_esperada!r}, chamado={chamado}")

    n = len(CENARIOS)
    print(f"\nFerramenta certa: {acertos_ferramenta}/{n} ({100 * acertos_ferramenta / n:.0f}%)")
    print(f"Ferramenta + argumentos certos: {acertos_completos}/{n} ({100 * acertos_completos / n:.0f}%)")


if __name__ == "__main__":
    rodar()
