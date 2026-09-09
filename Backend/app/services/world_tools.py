"""As mesmas operações atendem o narrador e os controles visuais."""

from collections.abc import Callable

from app.domain.living_world import ConflitoMundo, EntidadeCena, PessoaMundo
from app.services import living_world as mundo

# Chaves que só o Pydantic usa — o servidor revalida tudo com o modelo de
# verdade em `registrar_*`, então mandá-las ao LLM é só custo de token
# (Fase 0 do plano "jogo completo": o teto de tokens por minuto do provedor
# gratuito fez cada byte de schema contar).
_SO_PYDANTIC = {"$defs", "title", "default", "maxLength", "minLength", "maximum", "minimum", "pattern", "maxItems"}
# Campos que o SERVIDOR preenche ou zera no registro (`registrar_pessoa`
# reseta memória e clampa confiança; relógios e descobertas são estado de
# jogo) — o narrador não decide nenhum deles, então não os enxerga.
_CAMPOS_DO_SERVIDOR = {
    "segredo_revelado", "confianca", "lembrancas", "promessas",  # PessoaMundo
    "progresso", "proximo_avanco", "estado_relogio", "intervencoes", "desfecho",  # ConflitoMundo
    "descoberto", "bloqueado_por", "recolhido",  # EntidadeCena
    "turno",  # Conhecimento
}


def _expandir(schema: dict, raiz: dict | None = None) -> dict:
    raiz = raiz or schema
    if "$ref" in schema:
        return _expandir(raiz["$defs"][schema["$ref"].split("/")[-1]], raiz)
    saida = {
        k: (
            _expandir(v, raiz)
            if isinstance(v, dict)
            else [_expandir(item, raiz) if isinstance(item, dict) else item for item in v]
            if isinstance(v, list)
            else v
        )
        for k, v in schema.items()
        if k not in _SO_PYDANTIC
    }
    propriedades = saida.get("properties")
    if isinstance(propriedades, dict):
        propriedades = {k: v for k, v in propriedades.items() if k not in _CAMPOS_DO_SERVIDOR}
        saida["properties"] = propriedades
        obrigatorios = saida.get("required")
        if isinstance(obrigatorios, list):
            saida["required"] = [k for k in obrigatorios if k in propriedades]
    # `anyOf: [{type: X}, {type: null}]` (Optional) vira só `type: X`
    if isinstance(saida.get("anyOf"), list):
        tipos = [o for o in saida["anyOf"] if o.get("type") != "null"]
        if len(tipos) == 1:
            saida = {**{k: v for k, v in saida.items() if k != "anyOf"}, **tipos[0]}
    return saida


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
    "abrir_arco": mundo.abrir_arco,
    "encerrar_arco": mundo.encerrar_arco,
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
        (
            "Resolve uma intenção livre pelas propriedades reais do alvo (ex: bloquear alvo=porta" 
            "meio=estante; destrancar; negociar com proposta). Use IDs do estado; meio = objeto da cena ou" 
            "item possuído. Examinar/investigar dão informação, não loot; falha mantém alternativas; limites" 
            "do NPC valem."
        ),
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
        "abrir_arco",
        "Quando um conflito registrado ganha peso de história e não há arco ativo, abra um arco com "
        "título e premissa. É o capítulo atual da campanha; o servidor decide quando ele pode encerrar.",
        {"titulo": S, "premissa": S, "conflito": {"type": "string", "description": "id do conflito central"}},
        ["titulo", "premissa", "conflito"],
    ),
    _tool(
        "encerrar_arco",
        "Peça o fechamento do arco atual. Só passa se o servidor confirmar (turnos mínimos, fatos "
        "registrados, conflito central resolvido/concretizado ou chefe enfrentado). Nunca narre um fim de "
        "arco sem esta ferramenta devolver encerrado=true.",
        {"resumo_proposto": S},
        [],
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
