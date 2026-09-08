"""As mesmas operações atendem o narrador e os controles visuais."""

from collections.abc import Callable

from app.domain.living_world import ConflitoMundo, EntidadeCena, PessoaMundo
from app.services import living_world as mundo


def _expandir(schema: dict, raiz: dict | None = None) -> dict:
    raiz = raiz or schema
    if "$ref" in schema:
        return _expandir(raiz["$defs"][schema["$ref"].split("/")[-1]], raiz)
    return {
        k: (
            _expandir(v, raiz)
            if isinstance(v, dict)
            else [_expandir(item, raiz) if isinstance(item, dict) else item for item in v]
            if isinstance(v, list)
            else v
        )
        for k, v in schema.items()
        if k not in {"$defs", "title"}
    }


def _tool(nome, descricao, propriedades, obrigatorios):
    return {
        "type": "function",
        "function": {
            "name": nome,
            "description": descricao,
            "parameters": {"type": "object", "properties": propriedades, "required": obrigatorios},
        },
    }


S = {"type": "string"}
WORLD_DISPATCH: dict[str, Callable] = {
    "registrar_cena": mundo.registrar_cena,
    "registrar_pessoa": mundo.registrar_pessoa,
    "registrar_conflito": mundo.registrar_conflito,
    "agir_no_mundo": mundo.agir_no_mundo,
    "intervir_conflito": mundo.intervir_conflito,
    "definir_objetivo": mundo.definir_objetivo,
    "escolher_especializacao": mundo.escolher_especializacao,
    "registrar_vinculo": mundo.registrar_vinculo,
}
WORLD_TOOLS = [
    _tool(
        "registrar_cena",
        "Registre objetos e saídas que existem na cena ANTES de narrar sua presença. "
        "Aditivo: nunca restaura o estado anterior. Não crie recursos só para garantir sucesso do jogador.",
        {"descricao": S, "entidades": {"type": "array", "items": _expandir(EntidadeCena.model_json_schema())}},
        ["descricao", "entidades"],
    ),
    _tool(
        "registrar_pessoa",
        "Registre uma pessoa apresentada na cena: desejos, medo, limite, necessidade concreta "
        "e conhecimento separado em fato/boato/suspeita. Segredos nunca são expostos ao jogador automaticamente.",
        {"pessoa": _expandir(PessoaMundo.model_json_schema())},
        ["pessoa"],
    ),
    _tool(
        "registrar_conflito",
        "Registre uma iniciativa do NPC presente, com sinal perceptível, prazo em minutos "
        "e consequência causal. No máximo 2 conflitos novos por cena. Sem roteiro obrigatório ou morte automática.",
        {"conflito": _expandir(ConflitoMundo.model_json_schema())},
        ["conflito"],
    ),
    _tool(
        "agir_no_mundo",
        "Resolva a intenção livre pelas propriedades reais do alvo. Exemplos: bloquear porta "
        "usando meio=estante; destrancar fechadura; negociar com pessoa e proposta concreta. "
        "Falha mantém alternativas; examinar/investigar dão informações, não inventam loot. "
        "Use IDs registrados; negociações preservam limites do NPC. Meio é ID de objeto local ou item possuído.",
        {"acao": {"type": "string", "enum": list(mundo.ACOES)}, "alvo": S, "meio": S, "proposta": S},
        ["acao", "alvo"],
    ),
    _tool(
        "intervir_conflito",
        "Apoie, atrase ou resolva um conflito atual por proposta concreta do jogador. "
        "Resolver exige agente cooperativo e duas intervenções bem-sucedidas; recompensa única.",
        {"conflito": S, "abordagem": {"type": "string", "enum": ["apoiar", "atrasar", "resolver"]}, "proposta": S},
        ["conflito", "abordagem", "proposta"],
    ),
    _tool(
        "definir_objetivo",
        "Registre o objetivo que o JOGADOR decidiu perseguir, inclusive abandonar a missão. "
        "Nunca use para impor uma missão nova sem escolha dele.",
        {"objetivo": S},
        ["objetivo"],
    ),
    _tool(
        "registrar_vinculo",
        "Registre uma promessa explícita do jogador ou um boato/suspeita comunicado "
        "na conversa atual. Não transforma alegações em fatos; a pessoa deve estar presente.",
        {"npc": S, "natureza": {"type": "string", "enum": ["promessa", "boato", "suspeita"]}, "texto": S},
        ["npc", "natureza", "texto"],
    ),
    _tool(
        "escolher_especializacao",
        "Aplique a escolha explícita de especialização do jogador. "
        "Disponível nos níveis 3 e 7, trocável fora de combate; nunca escolhe por ele.",
        {
            "marco": {"type": "string", "enum": ["3", "7"]},
            "escolha": {"type": "string", "enum": ["explorador", "diplomata", "combatente"]},
        },
        ["marco", "escolha"],
    ),
]
