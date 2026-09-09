import json
from collections.abc import Callable
from typing import Any

from app.domain.character import CharacterCreationRequest
from app.domain.memoria import ResumoRolante
from app.domain.state import CombatState, QuestLog, WorldState
from app.infra import llm_client
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.infra.llm_client import ErroMestre
from app.infra.settings import settings
from app.services import rules_engine as motor
from app.services.emergent_start import criar_origem, validar_mundo_inicial
from app.services.encounters import painel_cena
from app.services.living_world import painel_mundo
from app.services.progression import painel_progressao

__all__ = ["ErroMestre", "chamar_mestre", "gerar_cronica", "gerar_epitafio", "gerar_prologo_missao", "montar_contexto"]


# Remaster da criação de personagem (Fase 1) — escolha do Passo 0 do wizard.
# Só muda o ESTILO de escrita aqui; o efeito mecânico da dificuldade (CD
# efetiva) é decidido pelo servidor em rules_engine.ajustar_cd_por_dificuldade,
# nunca só pelo prompt (ADR-0006).
TEMPERAMENTO_INSTRUCAO: dict[str, str] = {
    "Justo": (
        "Trate consequências com equilíbrio: nem puna demais, nem poupe o jogador — "
        "o mundo reage de forma justa às escolhas dele, boas e más."
    ),
    "Implacável": (
        "Não suavize falhas: erros custam caro, o perigo de verdade é real e a morte "
        "é uma possibilidade concreta, não um susto de mentira. As consequências são "
        "duras, mas sempre justas às regras — nunca arbitrárias ou cruéis por capricho."
    ),
    "Épico": (
        "Escreva num tom grandioso e dramático: cada ação do herói ganha peso mítico, "
        "como a lenda que ele está se tornando. Mesmo uma cena pequena merece um "
        "momento de grandiosidade."
    ),
}


def secao_tom_mestre(temperamento: str) -> str:
    instrucao = TEMPERAMENTO_INSTRUCAO.get(temperamento, TEMPERAMENTO_INSTRUCAO["Justo"])
    return f"[TOM DO MESTRE] {instrucao}"


def chamar_mestre(msgs: list[dict], chamar_fn: Callable[..., Any] | None = None) -> dict:
    """Chama o LLM e devolve o JSON já decodificado, ou levanta ErroMestre
    (nunca engole o erro em silêncio — ver ADR-0002, Etapa 1). A tradução de
    erro de API para `ErroMestre` mora em `chamar_modelo_unico`
    (app/infra/llm_client.py) — o mesmo caminho usado por qualquer outra
    chamada única do projeto, não uma cópia local.

    `chamar_fn` (rodada de conserto, BYOK) — quando o chamador tem a chave
    do jogador (`ChaveUsuario.chamar_fn`), esta chamada de prólogo/epitáfio
    usa ela em vez da cadeia do servidor. Sem isso, "trouxe minha chave"
    cobria os turnos de jogo mas não a criação de personagem nem a morte."""
    if chamar_fn is not None:
        resp = chamar_fn(msgs, response_format={"type": "json_object"})
    else:
        if not llm_client.clients:
            raise ErroMestre(
                "O mestre está sem acesso à IA — falta configurar ao menos uma chave de API "
                "no servidor (GROQ_API_KEY ou GEMINI_API_KEY)."
            )
        # `gerar_prologo_missao` e `gerar_epitafio` (Fase 7) são os únicos
        # caminhos que ainda usam JSON solto — nenhum dos dois tem estado de
        # jogo pra chamar ferramenta, são chamadas únicas e isoladas. O
        # turno de jogo (routers/game.py) usa services/agent_loop.py + tool
        # calling nativo desde a Etapa 4.
        resp = llm_client.chamar_modelo_unico(settings.cadeia_llm[0], msgs, response_format={"type": "json_object"})

    try:
        return json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError, TypeError, IndexError) as e:
        raise ErroMestre("O mestre respondeu num formato que não consegui entender.") from e


def gerar_prologo_missao(
    char: CharacterCreationRequest, chamar_fn: Callable[..., Any] | None = None, *, semente: int | None = None
) -> dict:
    # A abertura já é jogável sem IA. A mesma premissa permanece se uma
    # chamada falhar; lugares novos só entram no mundo com uma descrição.
    locais_validos = regras.get_locations_list()
    abertura = criar_origem(char, semente)
    local_padrao = abertura["local_inicial"]

    # BYOK (rodada de conserto) — com a chave do jogador, `chamar_clients`
    # do servidor pode estar vazio e mesmo assim o prólogo funciona.
    if chamar_fn is None and not llm_client.clients:
        return abertura


    # Etapa 11 (B-9) — o prólogo não herdava a bíblia (é a única chamada do
    # projeto em modo JSON solto, fora de montar_contexto). Como ele agora
    # é a primeira tela que o jogador vê (Etapa 11, B-7), precisa da mesma
    # voz do resto do jogo — e é, por natureza, um momento de alto impacto:
    # aqui a prosa pode crescer, não precisa do teto de palavras do dia a dia.
    prompt = f"""
    {regras.get_biblia()}
    {secao_tom_mestre(char.temperamento_mestre)}
    Crie condições iniciais para {char.nome} ({char.raca} {char.classe}).
    Passado: {char.background}. Objetivo: {char.objetivo}. História: {char.historia_texto}.
    Não invente lembranças ou decisões do herói.
    Gere uma situação própria para esse personagem: social, exploração, mistério, sobrevivência,
    descoberta, festa interrompida, viagem, dívida ou disputa. Varie o tipo; evite repetir depósitos
    e falta de suprimentos. Não existe missão obrigatória nem sequência de atos ou final predeterminado.
    NPCs têm interesses, medos, limites e informações incompletas, podendo cooperar ou discordar.
    O jogador pode ignorar tudo e seguir seu caminho. Sempre ofereça uma saída sem compromisso.
    Responda APENAS JSON com as mesmas chaves e formato deste exemplo, que é uma referência de
    ESTRUTURA e uma alternativa em caso de falha, NÃO uma cena obrigatória:
    {json.dumps(abertura, ensure_ascii=False)}
    Pode substituir inteiramente lugar, pessoas, objetos, disputa e texto. mundo_inicial.cenas
    usa o NOME do local como chave; entidades usam seu id como chave; pessoas/conflitos também.
    Todo agente de conflito deve existir e todo alvo de bloqueio deve existir na cena correspondente.
    Objetos com propriedades movel/pesado/trancado/mecanismo/investigavel/inflamavel/cobertura/fragil
    permitem ações reais. Saídas têm tipo=saida e destino. Não crie itens recebidos sem ferramenta.
    Máximo 8 locais, 8 pessoas, 4 conflitos e 20 entidades por local. Uma cena pequena é suficiente.
    Escreva intro_narrativa em 3 parágrafos: acontecimento, tensão humana, oportunidades concretas.
    Segredos, objetivos privados e pistas não descobertas NÃO aparecem na introdução.
    As 3 opcoes são sugestões curtas e variadas. Nunca decida pelo jogador.
    """
    try:
        roteiro = chamar_mestre([{"role": "user", "content": prompt}], chamar_fn=chamar_fn)
    except ErroMestre as e:
        print("ERRO NO PRÓLOGO:", e.mensagem)
        return abertura

    if not isinstance(roteiro, dict):
        return abertura
    # Uma resposta truncada nunca produz campanha com título/local/texto ausentes.
    campos_texto = ("local_inicial", "clima_inicial", "nome_missao", "objetivo_missao", "intro_narrativa")
    if any(not isinstance(roteiro.get(campo), str) or not roteiro[campo].strip() for campo in campos_texto):
        return abertura

    # A instrução acima é a primeira linha (ADR-0002); esta checagem é a
    # que vale — pedir com educação não impede o modelo de inventar um
    # nome (já aconteceu ao vivo: "Ruínas de Gralhoth" e "Ruínas de
    # Acheron", nenhum dos dois no catálogo).
    #
    # Rodada de conserto (Parte 2, item J) — antes disto, QUALQUER nome
    # fora do catálogo virava `local_padrao` sem exceção, então toda
    # campanha nova começava (quase sempre) em Phandalin. Agora, um nome
    # novo com descrição de verdade é aceito: mesmo padrão "o modelo
    # propõe, o servidor decide" da Fase 5 (`tools.mover`,
    # `descricao_proposta`) — `routers/character.py` é quem de fato
    # registra em `WorldState.locais_descobertos`, este módulo só decide
    # o que sobrevive no `roteiro` devolvido. Vilas-chave do catálogo
    # continuam disponíveis e continuam sendo a maioria dos casos válidos.
    descricao_local_novo = roteiro.get("local_inicial_descricao")
    if roteiro.get("local_inicial") not in locais_validos:
        if isinstance(descricao_local_novo, str) and descricao_local_novo.strip():
            roteiro["local_inicial_descricao"] = descricao_local_novo.strip()
        else:
            roteiro["local_inicial"] = local_padrao
            roteiro["local_inicial_descricao"] = abertura["local_inicial_descricao"]
    else:
        roteiro["local_inicial_descricao"] = None
    try:
        roteiro["mundo_inicial"] = validar_mundo_inicial(
            roteiro.get("mundo_inicial", abertura["mundo_inicial"]), roteiro["local_inicial"]
        )
    except (ValueError, TypeError):
        return abertura
    opcoes = roteiro.get("opcoes")
    if not isinstance(opcoes, list) or len(opcoes) != 3 or any(
        not isinstance(opcao, str) or not opcao.strip() or len(opcao) > 160 for opcao in opcoes
    ):
        roteiro["opcoes"] = abertura["opcoes"]
    # Identidade/seed são do servidor; não aceite uma campanha diferente vinda do modelo.
    for campo in ("inicio_aventura", "semente_aventura", "hora_do_dia", "chaves", "direcao"):
        roteiro[campo] = abertura[campo]
    roteiro["chaves"] = [f"Chegou a {roteiro['local_inicial']}; seu caminho continua aberto."]
    return roteiro


def gerar_epitafio(
    heroi: Personagem, eventos_marcantes: list[str], resumo: ResumoRolante, chamar_fn: Callable[..., Any] | None = None
) -> dict:
    """Fase 7 da revisão de gameplay (Etapa 12/13) — chamado uma vez por
    morte (`routers/game.py`, quando `c_state.resultado == "morte"` se
    confirma pela primeira vez), nunca regenerado depois. Mesmo padrão de
    `gerar_prologo_missao`: chamada isolada, JSON solto, sem ferramenta —
    é o fechamento da campanha, não um turno de jogo."""
    if chamar_fn is None and not llm_client.clients:
        return {
            "retrospectiva": f"{heroi.nome} caiu, e o mundo seguiu em frente sem contar sua história.",
            "epitafio_curto": f"Aqui jaz {heroi.nome}.",
        }

    eventos_texto = "\n".join(f"- {e}" for e in eventos_marcantes) or "Nenhum evento marcante registrado."
    fatos_texto = "\n".join(f"- {f}" for f in resumo.fatos_estabelecidos) or "Nenhum fato adicional registrado."
    prompt = f"""
    {regras.get_biblia()}

    {heroi.nome} ({heroi.raca} {heroi.classe}) morreu. Escreva o fechamento da jornada dele
    — a retrospectiva de como o mundo vai lembrá-lo, e um epitáfio curto para a lápide.
    Passado: {heroi.background} | Objetivo: {heroi.objetivo}

    Momentos mais marcantes da jornada, na ordem em que aconteceram:
    {eventos_texto}

    Fatos do mundo estabelecidos ao longo do jogo:
    {fatos_texto}

    Siga [A VOZ DO MESTRE] da bíblia acima — isto é o fechamento da campanha, trate como
    [MOMENTO DE ALTO IMPACTO]: pode crescer além do teto de palavras normal. Escreva a
    retrospectiva em segunda pessoa, como o resto do jogo. Baseie-se SÓ no que está
    listado acima — não invente eventos, NPCs ou lugares que não apareceram; se faltar
    material, seja mais breve em vez de inventar.

    Responda APENAS JSON:
    {{
        "retrospectiva": "2 a 3 parágrafos: como o mundo ficou, como ele é lembrado.",
        "epitafio_curto": "Uma linha curta, para a lápide."
    }}
    """
    try:
        resultado = chamar_mestre([{"role": "user", "content": prompt}], chamar_fn=chamar_fn)
    except ErroMestre as e:
        print("ERRO NO EPITÁFIO:", e.mensagem)
        return {
            "retrospectiva": f"{heroi.nome} caiu em batalha. A história de como será lembrado ainda não foi contada.",
            "epitafio_curto": f"Aqui jaz {heroi.nome}.",
        }

    if not isinstance(resultado.get("retrospectiva"), str) or not resultado["retrospectiva"].strip():
        resultado["retrospectiva"] = f"{heroi.nome} caiu, e o mundo seguiu em frente."
    if not isinstance(resultado.get("epitafio_curto"), str) or not resultado["epitafio_curto"].strip():
        resultado["epitafio_curto"] = f"Aqui jaz {heroi.nome}."
    return resultado


# Fase 7 da revisão de gameplay — teto de eventos que entram na Crônica.
# `services/memory.eventos_cronologicos` não tem limite (é o registro
# completo); aqui sim, porque o prompt não pode crescer sem fim numa
# campanha longa. Pega os mais recentes — corte prático, documentado, não
# escondido: uma campanha de 300 turnos não cabe inteira numa chamada só.
LIMITE_EVENTOS_CRONICA = 60


def gerar_desfecho_arco(
    heroi: Personagem, arco: dict, eventos: list[str], chamar_fn: Callable[..., Any] | None = None
) -> dict:
    """Fase 4 (ADR-0035) — chamado uma vez quando `encerrar_arco` passou no
    servidor; molde de `gerar_epitafio`: chamada isolada, JSON solto, só com
    os eventos listados. Sem modelo, o desfecho é a lista de marcos."""
    marcos = "\n".join(f"- {e}" for e in eventos) or "- Nenhum marco registrado."
    padrao = {"titulo": arco["titulo"], "texto": "\n".join(eventos[-6:]) or f"{arco['titulo']} chegou ao fim."}
    if chamar_fn is None and not llm_client.clients:
        return padrao
    rotulo = {"acordo": "um acordo negociado", "consequencia": "as consequências de não agir a tempo",
              "vitoria_chefe": "a queda de quem estava por trás", "abandono": "o abandono pelo herói"}
    prompt = f"""
    {regras.get_biblia()}

    O arco "{arco['titulo']}" da jornada de {heroi.nome} ({heroi.raca} {heroi.classe}) terminou por
    {rotulo.get(arco['resultado'], 'um desfecho')}. Premissa: {arco['premissa']}

    O que aconteceu neste arco, na ordem:
    {marcos}

    Siga [A VOZ DO MESTRE]; é [MOMENTO DE ALTO IMPACTO], pode crescer além do teto normal. Em segunda
    pessoa. Baseie-se SÓ no que está listado — não invente eventos, pessoas ou lugares; se faltar
    material, seja breve. Termine apontando que o mundo segue e o herói continua.

    Responda APENAS JSON: {{"titulo": "título do capítulo, curto", "texto": "2 a 3 parágrafos"}}
    """
    try:
        resultado = chamar_mestre([{"role": "user", "content": prompt}], chamar_fn=chamar_fn)
    except ErroMestre as e:
        print("ERRO NO DESFECHO DO ARCO:", e.mensagem)
        return padrao
    if not isinstance(resultado, dict):
        return padrao
    titulo = str(resultado.get("titulo") or arco["titulo"])
    texto_ok = isinstance(resultado.get("texto"), str) and resultado["texto"].strip()
    texto = resultado["texto"] if texto_ok else padrao["texto"]
    return {"titulo": titulo.strip()[:100] or arco["titulo"], "texto": texto.strip()}


def gerar_cronica(heroi: Personagem, eventos: list[str], chamar_fn: Callable[..., Any] | None = None) -> str:
    """Fase 7 — tece os eventos registrados (`services/memory.
    eventos_cronologicos`) num conto de fantasia em prosa. Diferente de
    `chamar_mestre`/`gerar_prologo_missao`/`gerar_epitafio`: a saída É o
    texto final, não um campo JSON — não há estrutura pra extrair aqui."""
    eventos = eventos[-LIMITE_EVENTOS_CRONICA:]
    if not eventos:
        return f"A jornada de {heroi.nome} ainda não tem nada registrado para contar."
    if chamar_fn is None and not llm_client.clients:
        return "\n\n".join(eventos)

    eventos_texto = "\n".join(f"- {e}" for e in eventos)
    prompt = f"""
    {regras.get_biblia()}

    Transforme os eventos abaixo — o registro cru de uma campanha de RPG vivida por
    {heroi.nome} ({heroi.raca} {heroi.classe}) — num conto de fantasia coeso, em prosa,
    como um capítulo de livro. Não invente eventos que não estão na lista; costure o que
    já aconteceu numa narrativa com começo e meio — a campanha pode não ter terminado, e
    tudo bem que o conto pare em aberto.

    Eventos, na ordem em que aconteceram:
    {eventos_texto}

    Responda só com o texto do conto — prosa corrida em parágrafos, sem JSON, sem
    títulos de seção.
    """
    try:
        msgs = [{"role": "user", "content": prompt}]
        resp = (
            chamar_fn(msgs)
            if chamar_fn is not None
            else llm_client.chamar_modelo_unico(settings.cadeia_llm[0], msgs)
        )
        return resp.choices[0].message.content or "\n\n".join(eventos)
    except ErroMestre as e:
        print("ERRO NA CRÔNICA:", e.mensagem)
        return "\n\n".join(eventos)


def _compacto(obj):
    """Tira campos vazios ("", [], {}, None) do painel do mundo antes de
    ele entrar no prompt — Fase 0 do plano "jogo completo": o bloco pesava
    ~800 tokens com metade em `"lembrancas":[]`, `"pista":""` e afins, e o
    teto de tokens por minuto do provedor gratuito não perdoa."""
    if isinstance(obj, dict):
        return {k: _compacto(v) for k, v in obj.items() if v not in ("", [], {}, None)}
    if isinstance(obj, list):
        return [_compacto(v) for v in obj]
    if isinstance(obj, str) and len(obj) > 160:
        # Descrições longas do modelo ficam inteiras no save; no prompt,
        # 160 caracteres bastam para o narrador lembrar do que se trata.
        return obj[:157].rstrip() + "..."
    return obj


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
        # Fase 3 — aliados em combate (não confundir com o roster fora de
        # combate em [ALIADOS PRESENTES]; aqui é quem de fato entrou nesta
        # luta, via iniciar_combate/recrutar_aliado) têm ação própria.
        aviso_aliado = (
            '\n    Se o jogador dirigir um aliado ("Bob ataca o goblin") ou a cena pedir que ele entre na '
            'luta, chame também "atacar_com_aliado" — ela não substitui a ação do herói, as duas '
            "ferramentas resolvem coisas diferentes na mesma rodada."
            if c_state.aliados
            else ""
        )
        secao_combate = f"""[COMBATE ATIVO] Inimigos vivos: {json.dumps(vivos, ensure_ascii=False)}
    O jogador está em combate. Chame a ferramenta que corresponde à
    INTENÇÃO dele: "atacar" (alvo, e arma se ele escolheu uma), "investir"
    (ataque arriscado: menos precisão, mais dano), "esquivar" (foca em não
    ser atingido), "defender" (postura defensiva), "esconder_se" (tenta
    sumir de vista) ou "fugir" (tenta sair do combate). Nunca resolva o
    combate narrando um resultado sozinho — a ferramenta certa decide o
    número, você só narra a INTENÇÃO da ação, num parágrafo curto. Nunca
    peça ao jogador para rolar um dado ou informar um resultado, e não
    escreva números de ataque, dano ou PV: o resultado real da ferramenta
    aparece automaticamente logo depois da sua narrativa.{aviso_impacto}{aviso_aliado}"""
    else:
        # Fase 0 da revisão de gameplay (Etapa 12/13) — escalonamento de
        # perigo: o servidor decide QUAIS bandas de monstro são compatíveis
        # com o nível do herói (motor.desafio_sugerido); o modelo continua
        # só propondo nomes dentro delas (ADR-0006: dificuldade não é
        # decisão do LLM). `iniciar_combate` também descarta nomes fora do
        # bestiário, então isto é orientação, não a única barreira.
        bandas = motor.desafio_sugerido(heroi.nivel or 1)
        monstros_sugeridos = [n for banda in bandas for n in regras.get_monstros_por_banda(banda)]
        secao_combate = f"""Se a cena pedir um confronto, chame a ferramenta "iniciar_combate" com os
    nomes dos monstros do bestiário que encaixam na cena (ex: ["Goblin"]).
    O servidor confirma que os nomes existem antes de criar o combate.
    [DESAFIO SUGERIDO] Para o nível do herói, prefira: {json.dumps(monstros_sugeridos, ensure_ascii=False)}."""

    # Remaster da criação de personagem (Fase 2/4) — antes disto, cortava
    # historia_texto nos primeiros 150 caracteres, no meio de uma frase
    # qualquer, todo turno. `resumo_historia` é uma frase-gancho pensada
    # pra isso (gerada pelo Oráculo, services/oraculo.py); sem ela, cai
    # para um corte limpo por palavra, não por caractere cru.
    if heroi.resumo_historia:
        historia_resumo = f" | História: {heroi.resumo_historia}"
    elif heroi.historia_texto:
        historia_resumo = f" | História: {heroi.historia_texto[:150].rsplit(' ', 1)[0]}..."
    else:
        historia_resumo = ""

    # Fase 3 da revisão de gameplay (Etapa 12/13, ADR-0027) — companheiros
    # recrutados são parte da cena o tempo todo, não só em combate: o
    # jogador conversa com eles fora de luta, e em combate o modelo precisa
    # saber que "atacar_com_aliado" existe. Um morto (hp 0) some daqui.
    aliados_vivos = [a for a in (heroi.aliados or []) if a["hp"] > 0]
    secao_aliados = (
        "\n    [ALIADOS PRESENTES] "
        + ", ".join(
            f"{a['nome']}, {a.get('raca', 'Humano')} {a['classe']} (HP {a['hp']}/{a['hp_max']})"
            + (" — já agiu nesta rodada" if a["nome"] in c_state.aliados_agiram else "")
            for a in aliados_vivos
        )
        if aliados_vivos
        else ""
    )

    # Rodada de conserto (Parte 2, item H) — antes disto, o narrador recebia
    # só o RÓTULO da raça/classe (heroi.raca/heroi.classe no [HEROI] abaixo)
    # e nunca os traços de verdade de data/races.json e data/classes.json —
    # um Anão Bárbaro narrava igual a um Elfo Mago. O EFEITO mecânico (quando
    # existe) é decidido pelo servidor, não por esta seção — ver
    # `rules_engine.vantagem_por_traco`, acionado pelo `motivo` que a
    # ferramenta `rolar_teste` já recebe; isto aqui é só o narrador sabendo
    # quem o herói É, pra narrar consistente com isso.
    d_raca = regras.get_race_details(heroi.raca)
    d_classe = regras.get_class_details(heroi.classe)
    tracos_txt = ", ".join(d_raca.get("tracos", [])) or "nenhum catalogado"
    proficiencias_txt = ", ".join(d_classe.get("proficiencias", [])) or "nenhuma catalogada"
    secao_tracos = (
        f"\n    [TRAÇOS] {heroi.raca}: {tracos_txt} (visão: {d_raca.get('visao', 'Normal')}) | "
        f"{heroi.classe}: proficiências em {proficiencias_txt}"
    )

    # Fase 1 (ADR-0033) — inventário com tipo/tags e o que está equipado; o
    # narrador nunca escreve número de item, só sabe o que cada coisa É.
    from app.services import items as itens

    partes_inv = []
    for nome in heroi.inventario or []:
        f = itens.ficha(nome, w_state.itens_inventados)
        tags = "/" + ",".join(f["tags"][:2]) if f and f.get("tags") else ""
        partes_inv.append(f"{nome} ({f['tipo']}{tags})" if f else nome)
    eq = heroi.equipamento or {}
    secao_inventario = (
        ", ".join(partes_inv) + f" | EQUIPADO arma={eq.get('arma') or '-'} armadura={eq.get('armadura') or '-'} "
        f"escudo={eq.get('escudo') or '-'} Defesa {heroi.defesa}"
    )
    # Fase 4 (ADR-0035) — o arco atual e o que o servidor exige para fechá-lo.
    from app.services.living_world import condicoes_arco

    cond = condicoes_arco(w_state)
    if cond.get("ativo"):
        secao_arco = (
            f"\n    [ARCO ATUAL] {cond['titulo']} — {cond['premissa'][:200]} | conflito central: "
            f"{cond['conflito']} ({cond['estado_conflito']}) | turnos no arco: {cond['turnos']} | "
            + ("pode encerrar agora: chame encerrar_arco se a cena pedir fechamento." if cond["pode_encerrar"]
               else f"ainda aberto ({cond['motivo_bloqueio']}). Nunca narre o fim do arco antes de "
                    "encerrar_arco devolver encerrado=true.")
        )
    else:
        secao_arco = (
            "\n    [ARCO] Nenhum arco ativo: quando um conflito registrado pedir peso de história, chame abrir_arco."
        )
    secao_mundo = json.dumps(
        _compacto(painel_mundo(w_state, heroi.classe, privado=True)), ensure_ascii=False, separators=(",", ":")
    )
    progressao = painel_progressao(heroi, c_state, w_state)
    # Fase 3 (ADR-0034) — o narrador sabe dos talentos e lembra da escolha
    # pendente; nunca escolhe por ele (não existe ferramenta para isso).
    talentos_txt = ", ".join(t["nome"] for t in progressao["talentos"])
    pendentes = [p["nivel"] for p in progressao["pendencias"]]
    secao_progressao = ""
    if talentos_txt or pendentes:
        secao_progressao = "\n    [PROGRESSÃO] " + (f"talentos: {talentos_txt}. " if talentos_txt else "") + (
            f"Escolha de nível pendente ({', '.join(map(str, pendentes))}): lembre o jogador com uma frase "
            "que a ficha espera uma decisão; nunca escolha por ele." if pendentes else ""
        )
    ficha_tatica = {campo: progressao[campo] for campo in ("estilo", "recurso", "habilidades")}
    cena_tatica = painel_cena(c_state, w_state)
    # Fase 0 do plano "jogo completo" — técnicas de classe e cenário tático
    # só fazem sentido com combate ativo (as ferramentas que os usam nem
    # são enviadas fora dele, ver `tools.tools_para`); fora de combate eram
    # ~550 tokens de painel de exploração e Foco que o modelo não usa.
    secao_tatica_instr = (
        """Se a intenção corresponder a uma técnica, use "usar_habilidade" com o id
    exato e um alvo válido. Respeite nível, Foco e disponibilidade; nunca invente
    técnicas nem efeitos. Use "interagir" com o id de uma interação
    disponível quando a intenção for cobertura, resgate, mecanismo ou negociação.
    Mostre oportunidades do terreno e a intenção anunciada de cada inimigo antes
    da próxima escolha. Objetivos de cenário podem encerrar o conflito com inimigos vivos.
    Uma decisão do jogador corresponde a uma ação principal de combate; não use
    uma técnica e um ataque adicional na mesma rodada. A reação inimiga é do motor."""
        if c_state.ativo
        else ""
    )
    secao_tatica = (
        f"[TÉCNICAS DA CLASSE] {json.dumps(ficha_tatica, ensure_ascii=False)}\n"
        f"    [CENÁRIO INTERATIVO] {json.dumps(cena_tatica, ensure_ascii=False)}"
        if c_state.ativo
        else ""
    )

    return f"""
    {secao_tom_mestre(heroi.temperamento_mestre)}
    {secao_regras}
    {secao_memoria}
    [HEROI] {heroi.nome} ({heroi.raca} {heroi.classe}) | HP: {heroi.hp_atual}/{heroi.hp_max} | \
Ouro: {heroi.ouro}{secao_tracos}
    [PASSADO] Background: {heroi.background} | Objetivo: {heroi.objetivo} | \
Alinhamento: {heroi.alinhamento}{historia_resumo}
    [INVENTÁRIO] {secao_inventario}{secao_aliados}
    [MISSÃO ATUAL] {q_state.nome_missao}: {q_state.objetivo_missao}
    [CENA] {w_state.local} | {w_state.clima} | {motor.periodo_do_dia(w_state.hora_do_dia)}{secao_progressao}{secao_arco}
    [MUNDO PERSISTENTE — INTENÇÕES PRIVADAS NÃO SÃO CONHECIMENTO DO HERÓI]
    {secao_mundo}
    Não há roteiro: a missão é interesse do jogador; aceite partidas, mudanças de lado e soluções
    imprevistas. Registre cena/pessoa/conflito (registrar_*) ANTES de apresentá-los como reais; cadastro
    não apaga alterações nem ressuscita ninguém. Local vazio: registre elementos coerentes, sem recursos
    inventados para garantir sucesso. Intenções livres passam por agir_no_mundo (IDs do estado; meio =
    objeto local ou item). intervir_conflito para apoiar, atrasar ou negociar; o tempo é do motor.
    definir_objetivo SÓ quando o jogador escolher um rumo. Se o jogador procurar comércio, registre a
    pessoa com "mercadoria" (nomes do catálogo: Poção de Cura, Poção de Foco, Antídoto, Frasco de Óleo,
    Óleo de Lâmina, Tocha, Armadura de Couro, Armadura de Escamas, Escudo, Adaga, Espada Curta, Espada
    Longa, Arco Curto...) e negocie por comerciar. Segredos, medos e intenções privadas orientam
    a interpretação sem serem revelados; boatos continuam boatos; pessoas sabem só o que sabem e têm
    limites. Antes de viagem ou descanso, lembre prazos VISÍVEIS sem impedir a partida. Uma falha não
    bloqueia a campanha. Narre resultados reais; nunca reverta uma consequência para salvar a trama.
    {secao_combate}

    {secao_tatica}
    {secao_tatica_instr}
    [ESCOLHAS E CONSEQUÊNCIAS]
    O herói decide intenções e valores: nunca narre que ele aceita, perdoa, mata ou sente algo que o
    jogador não escolheu; opções são sugestões, acolha ações livres. Falha ≠ bloqueio: uma falha custa
    tempo, posição, confiança ou recurso e abre outra pista; não repita o mesmo teste até dar certo; pistas
    essenciais têm pelo menos dois caminhos. Antecipe riscos perceptíveis antes da decisão. NPCs lembram,
    negociam conforme sua agenda, discordam sem virar inimigos, não entregam segredos sem descoberta;
    fatos e escolhas registrados vencem qualquer roteiro. Varie cenas (descoberta, vínculo, dilema,
    tensão, resgate, confronto); nem toda pista é emboscada; combate pode proteger, interromper, convencer
    — matar todos nunca é a única saída; respeite poupar e rendição.

    Toda mudança de estado passa por ferramenta: nunca escreva HP, dano, ouro ou resultado de dado no
    texto (a ferramenta mostra). Item recebido: dar_item ANTES de narrar (fora do catálogo, com
    descricao e tags). Vestir/trocar arma, armadura ou escudo: equipar. Compra ou venda com quem tem
    mercadoria: comerciar — nunca narre preço antes. Ação arriscada e incerta:
    rolar_teste na hora, sempre com "motivo" (e "item_usado" se ele usar algo criativo) — o jogador
    nunca rola dado, só decide. Objetivo cumprido sem combate: concluir_objetivo (única fonte de XP fora
    da luta). NPC que se junta de verdade: recrutar_aliado. Descanso declarado: descansar (nunca cure
    narrando). "mover" com "encontro" (emboscada/achado): é a estrada reagindo, narre na hora.
    "descansar" com "gancho_acampamento": puxe essa fala antes de seguir. Nunca invente recompensa,
    combate, item, inimigo ou habilidade fora das ferramentas.

    Depois das ferramentas, narre em prosa seguindo [A VOZ DO MESTRE]: direto, com peso, um detalhe
    sensorial escolhido. Só texto corrido — sem JSON, título, lista, bloco de código, CAIXA ALTA ou
    itálico; ênfase pela palavra. Única exceção: item, lugar ou achado importante que aparece pela
    primeira vez vai em **negrito**, no máximo uma ou duas vezes, nunca em diálogo nem em nomes já
    conhecidos. Termine SEMPRE com uma linha própria "[OPCOES]: opção 1|opção 2|opção 3" — três ações
    curtas e concretas para AGORA, separadas por "|", sem numeração (ex: "[OPCOES]: Atacar o
    goblin|Recuar para a porta|Examinar o baú"). O servidor transforma essa linha em botões: nunca a
    mencione nem explique, só escreva por último.
    """
