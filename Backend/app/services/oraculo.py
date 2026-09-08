"""Origem guiada por IA (remaster da criação de personagem, Fase 2) — o
jogador descreve um conceito de uma frase ("um elfo cego que odeia magia") e
o Oráculo devolve raça/classe sugeridas, duas perguntas curtas sobre o
passado do herói, e depois — com as respostas — um documento de origem
pronto para a Ficha do personagem (FichaModal.tsx).

Usa tool calling (ADR-0007), não JSON solto: `raca`/`classe` são um `enum`
no schema com as chaves reais de races.json/classes.json, então o modelo
não tem como sugerir uma raça que não existe no catálogo — diferente de
`narrator.gerar_prologo_missao`, que ainda é JSON solto por não ter esse
tipo de restrição fechada para impor."""

import json
from collections.abc import Callable
from typing import Any

from app.infra import llm_client
from app.infra.data_manager import regras
from app.infra.llm_client import ErroMestre
from app.infra.settings import settings

_SEM_ORACULO = (
    "O Oráculo está sem acesso à IA agora — falta configurar ao menos uma chave de API "
    "no servidor (GROQ_API_KEY ou GEMINI_API_KEY), ou tente de novo com sua própria chave."
)

# Espelha exatamente os 9 `value`s do <select> de Alinhamento em
# CharacterCreation.tsx (Passo "Identidade") — não existe hoje um catálogo
# compartilhado como races.json/classes.json para alinhamento, então mudar um
# lado sem o outro faz a sugestão da IA não bater com nenhuma opção do select.
_ALINHAMENTOS = [
    "Neutro", "Leal e Bom", "Neutro e Bom", "Caótico e Bom",
    "Leal e Neutro", "Caótico e Neutro",
    "Leal e Mau", "Neutro e Mau", "Caótico e Mau",
]


def _chamar_com_ferramenta(
    prompt: str, schema: dict, nome_ferramenta: str, chamar_fn: Callable[..., Any] | None
) -> dict:
    """Força o modelo a chamar exatamente `nome_ferramenta` (`tool_choice`
    específico, não "auto") — um conceito livre do jogador não tem CD nem
    combate para justificar o modelo "narrar" em vez de responder; forçar a
    ferramenta é o que garante o formato sem depender de instrução em
    texto (mesmo raciocínio do ADR-0007 aplicado à criação, não só ao turno)."""
    msgs = [{"role": "user", "content": prompt}]
    tool_choice = {"type": "function", "function": {"name": nome_ferramenta}}
    if chamar_fn is not None:
        resp = chamar_fn(msgs, tools=[schema], tool_choice=tool_choice)
    else:
        if not llm_client.clients:
            raise ErroMestre(_SEM_ORACULO)
        resp = llm_client.chamar_modelo_unico(settings.cadeia_llm[0], msgs, tools=[schema], tool_choice=tool_choice)

    tool_calls = resp.choices[0].message.tool_calls
    if not tool_calls:
        raise ErroMestre("O Oráculo respondeu sem usar a ferramenta esperada — tente de novo.")
    try:
        return json.loads(tool_calls[0].function.arguments)
    except json.JSONDecodeError as e:
        raise ErroMestre("O Oráculo respondeu num formato que não consegui entender.") from e


_SCHEMA_SUGERIR_ORIGEM = {
    "type": "function",
    "function": {
        "name": "sugerir_origem",
        "description": (
            "Sugere a raça e a classe de D&D 5e que melhor encaixam no conceito de personagem "
            "descrito pelo jogador, e propõe duas perguntas curtas sobre o passado dele para "
            "aprofundar a origem."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "raca": {"type": "string", "description": "A raça que melhor encaixa no conceito."},
                "classe": {"type": "string", "description": "A classe que melhor encaixa no conceito."},
                "perguntas": {
                    "type": "array",
                    "items": {"type": "string"},
                    "minItems": 2,
                    "maxItems": 2,
                    "description": (
                        "Duas perguntas curtas (uma frase cada), específicas para ESTE conceito, sobre "
                        "um momento ou vínculo do passado do herói que ainda não foi dito. Nunca perguntas "
                        "genéricas como 'qual seu objetivo' — algo que só faz sentido para este personagem."
                    ),
                },
                "pista_visual_en": {
                    "type": "string",
                    "description": (
                        "Um descritor visual curto, EM INGLÊS, de 4 a 10 palavras, para um gerador de "
                        "imagem (ex: 'blind elf with pale scarred eyes, no staff, plain traveling clothes'). "
                        "Só aparência e objetos visíveis — nunca personalidade ou história."
                    ),
                },
            },
            "required": ["raca", "classe", "perguntas", "pista_visual_en"],
        },
    },
}

_SCHEMA_ESCREVER_HISTORIA = {
    "type": "function",
    "function": {
        "name": "escrever_historia",
        "description": "Escreve o documento de origem do herói a partir do conceito e das respostas do jogador.",
        "parameters": {
            "type": "object",
            "properties": {
                "historia_texto": {
                    "type": "string",
                    "description": (
                        "O documento de origem completo, em 2 a 4 parágrafos separados por uma linha em "
                        "branco (\\n\\n) — vai para a Ficha do personagem, o jogador lê isso. Prosa rica, "
                        "conectando o conceito e as duas respostas numa história coesa, não uma lista."
                    ),
                },
                "background": {
                    "type": "string",
                    "description": "Profissão/origem social do herói em poucas palavras (ex: 'Ex-guarda da guarda real').",
                },
                "resumo_historia": {
                    "type": "string",
                    "description": (
                        "Uma frase-gancho de até 120 caracteres capturando a essência do herói — vai "
                        "aparecer em todo turno do jogo, precisa caber sozinha sem cortar no meio."
                    ),
                },
                "alinhamento": {
                    "type": "string",
                    "enum": _ALINHAMENTOS,
                    "description": (
                        "O alinhamento moral do herói mais coerente com o conceito e as respostas dele. "
                        "Escolha só entre os valores desta lista."
                    ),
                },
                "objetivo": {
                    "type": "string",
                    "description": (
                        "Uma frase curta (até ~15 palavras) com o que o herói busca agora, coerente com "
                        "a história contada — vai para o campo Objetivo de Vida da ficha, que o jogador "
                        "ainda pode editar depois."
                    ),
                },
            },
            "required": ["historia_texto", "background", "resumo_historia", "alinhamento", "objetivo"],
        },
    },
}


def sugerir_origem(conceito: str, chamar_fn: Callable[..., Any] | None = None) -> dict:
    racas = ", ".join(regras.get_races_list())
    classes = ", ".join(regras.get_classes_list())
    prompt = f"""
    {regras.get_biblia()}

    Um jogador está criando um herói para esta campanha e descreveu o conceito abaixo.
    Conceito do jogador: "{conceito}"

    Escolha "raca" EXATAMENTE uma destas (nenhuma outra): {racas}.
    Escolha "classe" EXATAMENTE uma destas (nenhuma outra): {classes}.
    Chame a ferramenta "sugerir_origem" com sua escolha, as duas perguntas e a pista visual.
    """
    dados = _chamar_com_ferramenta(prompt, _SCHEMA_SUGERIR_ORIGEM, "sugerir_origem", chamar_fn)

    racas_validas = regras.get_races_list()
    classes_validas = regras.get_classes_list()
    if dados.get("raca") not in racas_validas:
        dados["raca"] = racas_validas[0]
    if dados.get("classe") not in classes_validas:
        dados["classe"] = classes_validas[0]
    perguntas = dados.get("perguntas")
    if not isinstance(perguntas, list) or len(perguntas) != 2 or not all(isinstance(p, str) and p.strip() for p in perguntas):
        dados["perguntas"] = [
            "O que seu herói perdeu antes desta jornada começar?",
            "Quem, do passado dele, ainda pesa na consciência dele hoje?",
        ]
    pista = dados.get("pista_visual_en")
    dados["pista_visual_en"] = pista.strip() if isinstance(pista, str) and pista.strip() else ""
    return dados


def escrever_historia(
    conceito: str, raca: str, classe: str, perguntas: list[str], respostas: list[str],
    chamar_fn: Callable[..., Any] | None = None,
) -> dict:
    perguntas_respostas = "\n".join(f"- {p}\n  Resposta: {r}" for p, r in zip(perguntas, respostas))
    prompt = f"""
    {regras.get_biblia()}

    Um jogador está criando um {raca} {classe}. Conceito original: "{conceito}"

    Perguntas sobre o passado dele, e as respostas que ele deu:
    {perguntas_respostas}

    Chame a ferramenta "escrever_historia" com o documento de origem completo, o background
    curto, e o resumo de uma frase — tudo baseado SÓ no conceito e nas respostas acima, sem
    inventar fatos que contradigam o que o jogador disse.
    """
    dados = _chamar_com_ferramenta(prompt, _SCHEMA_ESCREVER_HISTORIA, "escrever_historia", chamar_fn)

    historia = dados.get("historia_texto")
    if not isinstance(historia, str) or not historia.strip():
        historia = "\n\n".join(f"{p}\n{r}" for p, r in zip(perguntas, respostas))
    background = dados.get("background")
    if not isinstance(background, str) or not background.strip():
        background = f"{raca} {classe}"
    resumo = dados.get("resumo_historia")
    if not isinstance(resumo, str) or not resumo.strip():
        resumo = f"{historia[:117].rsplit(' ', 1)[0]}..."
    alinhamento = dados.get("alinhamento")
    if alinhamento not in _ALINHAMENTOS:
        alinhamento = _ALINHAMENTOS[0]
    objetivo = dados.get("objetivo")
    if not isinstance(objetivo, str) or not objetivo.strip():
        objetivo = "encontrar seu próprio caminho"

    return {
        "historia_texto": historia.strip()[:4000],
        "background": background.strip()[:500],
        "resumo_historia": resumo.strip()[:150],
        "alinhamento": alinhamento,
        "objetivo": objetivo.strip()[:500],
    }
