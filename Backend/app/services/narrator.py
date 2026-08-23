import json

import groq

from app.domain.character import CharacterCreationRequest
from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.infra.llm_client import MODEL_NAME, ErroMestre, client

__all__ = ["ErroMestre", "chamar_mestre", "gerar_prologo_missao", "montar_contexto"]


def chamar_mestre(msgs: list[dict]) -> dict:
    """Chama o LLM e devolve o JSON já decodificado, ou levanta ErroMestre
    com uma mensagem específica para cada tipo de falha (nunca engole o
    erro em silêncio — ver ADR-0002, Etapa 1)."""
    if not client:
        raise ErroMestre(
            "O mestre está sem acesso à IA — falta configurar a chave da Groq no servidor (GROQ_API_KEY)."
        )
    try:
        # Só o prólogo (gerar_prologo_missao) ainda usa este caminho em modo
        # JSON solto — não tem estado de jogo para chamar ferramenta nenhuma,
        # é uma chamada única. O turno de jogo (routers/game.py) usa
        # services/agent_loop.py + tool calling nativo desde a Etapa 4.
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
    # Etapa 11 (B-7, resolve P-5) — o local sempre vem do catálogo real
    # (data/locations.json), nunca inventado. `mover` (services/tools.py)
    # já validava contra esse catálogo; até aqui só o prólogo escapava
    # dessa regra, porque criava o herói ANTES de qualquer ferramenta
    # existir. "Vila de Phandalin" é o default determinístico — um vilarejo
    # é o único tipo de local aqui que faz sentido como ponto de partida
    # neutro, sem pressupor perigo imediato nem viagem já em andamento.
    locais_validos = regras.get_locations_list()
    local_padrao = "Vila de Phandalin" if "Vila de Phandalin" in locais_validos else locais_validos[0]

    if not client:
        return {
            "local_inicial": local_padrao,
            "clima_inicial": "Nublado",
            "nome_missao": "Jornada Inicial",
            "objetivo_missao": "Chegar à cidade.",
            "intro_narrativa": f"{char.nome} inicia sua jornada na estrada.",
        }

    tem_historia = char.historia_texto.strip()
    historia_extra = f"\n    História contada pelo próprio jogador: {char.historia_texto}" if tem_historia else ""
    conexao = " e à história que ele contou" if tem_historia else ""

    # Etapa 11 (B-9) — o prólogo não herdava a bíblia (é a única chamada do
    # projeto em modo JSON solto, fora de montar_contexto). Como ele agora
    # é a primeira tela que o jogador vê (Etapa 11, B-7), precisa da mesma
    # voz do resto do jogo — e é, por natureza, um momento de alto impacto:
    # aqui a prosa pode crescer, não precisa do teto de palavras do dia a dia.
    prompt = f"""
    {regras.get_biblia()}

    Crie o prólogo de {char.nome} ({char.raca} {char.classe}) — a primeira cena que
    ele vive, e a primeira coisa que o jogador vai ler no jogo.
    Passado: {char.background} | Objetivo: {char.objetivo} | Alinhamento: {char.alinhamento}{historia_extra}

    O prólogo começa 'in media res' (já na ação), conectado ao passado dele{conexao}.
    Siga [A VOZ DO MESTRE] da bíblia acima, mas trate isto como um [MOMENTO DE ALTO
    IMPACTO]: é a abertura do jogo, pode crescer além do teto de palavras normal.

    "local_inicial" TEM que ser exatamente um destes nomes, sem variação —
    são os únicos locais que o resto do jogo reconhece: {", ".join(locais_validos)}.

    Responda APENAS JSON:
    {{
        "local_inicial": "Nome do Local (um da lista acima, exato)",
        "clima_inicial": "Clima atmosférico",
        "nome_missao": "Título da Missão Atual",
        "objetivo_missao": "O que ele deve fazer agora (curto)",
        "intro_narrativa": "Texto narrativo de 3 parágrafos imersivos."
    }}
    """
    try:
        roteiro = chamar_mestre([{"role": "user", "content": prompt}])
    except ErroMestre as e:
        print("ERRO NO PRÓLOGO:", e.mensagem)
        return {
            "local_inicial": local_padrao,
            "clima_inicial": "Chuvoso",
            "nome_missao": "Desconhecido",
            "objetivo_missao": "Sobreviver",
            "intro_narrativa": "Você acorda...",
        }

    # A instrução acima é a primeira linha (ADR-0002); esta checagem é a
    # que vale — pedir com educação não impede o modelo de inventar um
    # nome (já aconteceu ao vivo: "Ruínas de Gralhoth" e "Ruínas de
    # Acheron", nenhum dos dois no catálogo). Sem isso, `mover` recusaria
    # o próprio local onde o herói nasceu.
    if roteiro.get("local_inicial") not in locais_validos:
        roteiro["local_inicial"] = local_padrao
    return roteiro


def montar_contexto(
    heroi: Personagem,
    w_state: WorldState,
    c_state: CombatState,
    q_state: QuestLog,
    regras_relevantes: list[str] | None = None,
    memorias: list[str] | None = None,
    resumo: ResumoRolante | None = None,
    reputacoes: dict[str, int] | None = None,
) -> str:
    # Etapa 4 (ADR-0007): o modelo não escreve mais nenhum campo de estado
    # em JSON — toda mudança (dano, item, ouro, movimento, combate) passa
    # por uma ferramenta (services/tools.py), chamada via tool calling
    # nativo da Groq. Esta função só monta o texto de sistema; quem oferece
    # `tools=` ao modelo é services/agent_loop.py.
    #
    # Etapa 5 (ADR-0009/ADR-0010): a bíblia inteira não é mais despejada
    # aqui — `regras_relevantes` já vem filtrada por RAG
    # (services/rag_regras.py). `memorias`/`resumo`/`reputacoes` são as
    # camadas de médio e longo prazo (services/memory.py); o parâmetro
    # `hist` de curto prazo continua sendo montado por quem chama (mesmo
    # contrato desde a Etapa 1).
    resumo = resumo or ResumoRolante()
    secao_regras = "\n\n".join(regras_relevantes) if regras_relevantes else ""

    secao_memoria = ""
    if memorias:
        secao_memoria += "[MEMÓRIAS RELEVANTES]\n" + "\n".join(f"- {m}" for m in memorias) + "\n"
    if resumo.fatos_estabelecidos:
        secao_memoria += "[FATOS ESTABELECIDOS]\n" + "\n".join(f"- {f}" for f in resumo.fatos_estabelecidos) + "\n"
    if resumo.npcs_conhecidos:
        secao_memoria += "[NPCS CONHECIDOS]\n" + "\n".join(f"- {n}" for n in resumo.npcs_conhecidos) + "\n"
    if resumo.promessas_feitas:
        secao_memoria += "[PROMESSAS FEITAS]\n" + "\n".join(f"- {p}" for p in resumo.promessas_feitas) + "\n"
    if resumo.mudancas_no_mundo:
        secao_memoria += "[MUDANÇAS NO MUNDO]\n" + "\n".join(f"- {m}" for m in resumo.mudancas_no_mundo) + "\n"
    if reputacoes:
        linhas_reputacao = "\n".join(
            f"- {npc}: {valor:+d} (negativo é hostil, positivo é favorável)" for npc, valor in reputacoes.items()
        )
        secao_memoria += f"[REPUTAÇÃO DO HERÓI COM NPCS PRESENTES]\n{linhas_reputacao}\n"

    if c_state.ativo:
        inimigos_vivos = [i for i in c_state.inimigos if i.hp > 0]
        vivos = [i.model_dump() for i in inimigos_vivos]
        # Etapa 11 (B-9) — gatilhos de "momento de alto impacto": o modelo
        # narra a INTENÇÃO antes de saber o resultado do dado (ver a regra
        # logo abaixo), então o único jeito honesto de avisar "isso é
        # decisivo" é pelo que já está no contexto ANTES da rolagem — HP
        # crítico (de qualquer lado) ou a presença de um chefe do bestiário.
        # Ver [MOMENTOS DE ALTO IMPACTO] na bíblia.
        heroi_critico = heroi.hp_max > 0 and heroi.hp_atual / heroi.hp_max < 0.25
        inimigo_critico = any(i.max_hp > 0 and i.hp / i.max_hp < 0.25 for i in inimigos_vivos)
        e_chefe = any(i.nome in regras.get_monstros_chefe() for i in inimigos_vivos)
        aviso_impacto = (
            "\n    [MOMENTO DE ALTO IMPACTO] Vida por um fio, o golpe que pode "
            "decidir o combate, ou um chefe — deixe a cena crescer aqui (ver "
            "[MOMENTOS DE ALTO IMPACTO] na bíblia)."
            if heroi_critico or inimigo_critico or e_chefe
            else ""
        )
        secao_combate = f"""[COMBATE ATIVO] Inimigos vivos: {json.dumps(vivos, ensure_ascii=False)}
    O jogador está em combate. Chame a ferramenta "atacar" com o alvo (e a
    arma, se o jogador escolheu uma) para resolver a ação dele. Narre só a
    INTENÇÃO da ação, num parágrafo curto — nunca peça ao jogador para rolar
    um dado ou informar um resultado, e não escreva números de ataque, dano
    ou PV: o resultado real da ferramenta aparece automaticamente logo
    depois da sua narrativa.{aviso_impacto}"""
    else:
        secao_combate = """Se a cena pedir um confronto, chame a ferramenta "iniciar_combate" com os
    nomes dos monstros do bestiário que encaixam na cena (ex: ["Goblin"]).
    O servidor confirma que os nomes existem antes de criar o combate."""

    return f"""
    {secao_regras}
    {secao_memoria}
    [HEROI] {heroi.nome} ({heroi.classe}) | HP: {heroi.hp_atual}/{heroi.hp_max} | Ouro: {heroi.ouro}
    [INVENTÁRIO] {heroi.inventario}
    [MISSÃO ATUAL] {q_state.nome_missao}: {q_state.objetivo_missao}
    [CENA] {w_state.local} | {w_state.clima}
    {secao_combate}

    Você tem ferramentas para agir no mundo (dano, item, ouro, movimento,
    teste de atributo, consulta de regra). Use-as para qualquer mudança de
    estado — nunca escreva HP, dano, ouro ou resultado de rolagem no texto,
    a ferramenta já mostra isso ao jogador. Se o jogador encontra ou recebe
    um item (saque, recompensa, presente), chame "dar_item" ANTES de narrar
    — nunca escreva que ele "guarda X no inventário" sem ter chamado a
    ferramenta primeiro, ou o item vira mentira: existe na narrativa, mas
    não no inventário de verdade. Em especial: se a ação do
    jogador é arriscada e incerta (perceber algo, escalar, persuadir,
    resistir a um efeito), chame "rolar_teste" você mesmo, na hora — NUNCA
    escreva "role um teste de X" ou peça ao jogador para rolar um dado; o
    jogador não rola dado nenhum, só decide a ação, e a ferramenta decide o
    resultado. Depois de usar as ferramentas que a cena pedir, narre o
    resultado em prosa seguindo [A VOZ DO MESTRE] da bíblia acima — direto,
    com peso, um detalhe sensorial escolhido, não uma lista de três. Não
    responda em JSON: a resposta final é só o texto da narrativa — prosa
    corrida, sem markdown (sem asterisco, sem cerquilha de título, sem
    lista com marcador, sem bloco de código); ênfase pela escolha da
    palavra, nunca pela tipografia.
    """
