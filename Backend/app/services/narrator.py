import json

import groq

from app.domain.character import CharacterCreationRequest
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.infra.llm_client import MODEL_NAME, client


class ErroMestre(Exception):
    """Erro ao consultar a IA, com uma mensagem já pronta para o jogador ler."""

    def __init__(self, mensagem: str) -> None:
        self.mensagem = mensagem
        super().__init__(mensagem)


def chamar_mestre(msgs: list[dict]) -> dict:
    """Chama o LLM e devolve o JSON já decodificado, ou levanta ErroMestre
    com uma mensagem específica para cada tipo de falha (nunca engole o
    erro em silêncio — ver ADR-0002, Etapa 1)."""
    if not client:
        raise ErroMestre(
            "O mestre está sem acesso à IA — falta configurar a chave da Groq no servidor (GROQ_API_KEY)."
        )
    try:
        # O SDK da Groq espera TypedDicts específicos por papel (system/user/
        # assistant), não dict[str, str] solto. Tipar `msgs` de verdade é
        # trabalho da Etapa 4 (tool calling), quando as mensagens ganham
        # estrutura própria; por ora, silenciamos aqui e não na assinatura.
        resp = client.chat.completions.create(
            model=MODEL_NAME, messages=msgs, response_format={"type": "json_object"}  # type: ignore[call-overload]
        )
    except groq.RateLimitError as e:
        raise ErroMestre("A cota de uso da IA acabou por agora. Espere um pouco e tente de novo.") from e
    except groq.APITimeoutError as e:
        raise ErroMestre("O mestre demorou demais para responder. Tente enviar a ação de novo.") from e
    except groq.APIConnectionError as e:
        raise ErroMestre("Não foi possível conectar ao serviço de IA. Verifique sua internet.") from e
    except groq.APIStatusError as e:
        raise ErroMestre(f"O serviço de IA recusou o pedido (código {e.status_code}).") from e

    try:
        return json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError) as e:
        raise ErroMestre("O mestre respondeu num formato que não consegui entender.") from e


def gerar_prologo_missao(char: CharacterCreationRequest) -> dict:
    if not client:
        return {
            "local_inicial": "Estrada Real",
            "clima_inicial": "Nublado",
            "nome_missao": "Jornada Inicial",
            "objetivo_missao": "Chegar à cidade.",
            "intro_narrativa": f"{char.nome} inicia sua jornada na estrada.",
        }

    tem_historia = char.historia_texto.strip()
    historia_extra = f"\n    História contada pelo próprio jogador: {char.historia_texto}" if tem_historia else ""
    conexao = " e à história que ele contou" if tem_historia else ""

    prompt = f"""
    Crie um prólogo de RPG Dark Fantasy para:
    Nome: {char.nome} ({char.raca} {char.classe})
    Passado: {char.background} | Objetivo: {char.objetivo} | Alinhamento: {char.alinhamento}{historia_extra}

    O prólogo deve começar 'in media res' (já na ação), conectado ao passado dele{conexao}.
    Responda APENAS JSON:
    {{
        "local_inicial": "Nome do Local",
        "clima_inicial": "Clima atmosférico",
        "nome_missao": "Título da Missão Atual",
        "objetivo_missao": "O que ele deve fazer agora (curto)",
        "intro_narrativa": "Texto narrativo de 3 parágrafos imersivos."
    }}
    """
    try:
        return chamar_mestre([{"role": "user", "content": prompt}])
    except ErroMestre as e:
        print("ERRO NO PRÓLOGO:", e.mensagem)
        return {
            "local_inicial": "Taverna",
            "clima_inicial": "Chuvoso",
            "nome_missao": "Desconhecido",
            "objetivo_missao": "Sobreviver",
            "intro_narrativa": "Você acorda...",
        }


def montar_contexto(heroi: Personagem, w_state: WorldState, c_state: CombatState, q_state: QuestLog) -> str:
    combate_txt = ""
    if c_state.ativo:
        vivos = [i.model_dump() for i in c_state.inimigos if i.hp > 0]
        combate_txt = f"[COMBATE ATIVO] Inimigos: {json.dumps(vivos, ensure_ascii=False)}"

    return f"""
    {regras.get_biblia()}
    [HEROI] {heroi.nome} ({heroi.classe}) | HP: {heroi.hp_atual}/{heroi.hp_max}
    [MISSÃO ATUAL] {q_state.nome_missao}: {q_state.objetivo_missao}
    [CENA] {w_state.local} | {w_state.clima}
    {combate_txt}

    Responda JSON:
    {{
        "narrativa": "...",
        "spawn_battle": false,
        "hp_atual": {heroi.hp_atual}
    }}
    """
