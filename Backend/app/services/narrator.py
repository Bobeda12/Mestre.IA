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
from app.services.tools import RELOGIO_MAXIMO, RELOGIO_URGENCIA

__all__ = ["ErroMestre", "chamar_mestre", "gerar_cronica", "gerar_epitafio", "gerar_prologo_missao", "montar_contexto"]


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
    except (json.JSONDecodeError, AttributeError) as e:
        raise ErroMestre("O mestre respondeu num formato que não consegui entender.") from e


# Fase 4 da revisão de gameplay (Etapa 12/13) — esqueleto de campanha
# genérico, usado quando o modelo não está disponível OU quando o que ele
# devolveu não bate no formato esperado (mesmo espírito da checagem de
# `local_inicial` logo abaixo: pedir com educação não garante o formato).
ATOS_PADRAO = [
    {"titulo": "O Chamado", "objetivo": "Descobrir o que está por trás do primeiro incidente."},
    {"titulo": "A Jornada", "objetivo": "Seguir as pistas até a origem da ameaça."},
    {"titulo": "O Confronto", "objetivo": "Enfrentar a raiz do problema, custe o que custar."},
]


def _validar_atos(bruto: object) -> list[dict]:
    """`atos` só é aceito se vier no formato exato — uma lista de 3 a 5
    dicts com `titulo` e `objetivo`, ambos string não-vazia. Qualquer
    desvio (campo faltando, tipo errado, lista vazia ou gigante) cai pro
    esqueleto padrão — mesma fronteira de confiança do `local_inicial`."""
    if not isinstance(bruto, list) or not (3 <= len(bruto) <= 5):
        return ATOS_PADRAO
    atos = []
    for item in bruto:
        if not isinstance(item, dict):
            return ATOS_PADRAO
        titulo, objetivo = item.get("titulo"), item.get("objetivo")
        if not isinstance(titulo, str) or not titulo.strip() or not isinstance(objetivo, str) or not objetivo.strip():
            return ATOS_PADRAO
        atos.append({"titulo": titulo, "objetivo": objetivo})
    return atos


def gerar_prologo_missao(char: CharacterCreationRequest, chamar_fn: Callable[..., Any] | None = None) -> dict:
    # Etapa 11 (B-7, resolve P-5) — o local sempre vem do catálogo real
    # (data/locations.json), nunca inventado. `mover` (services/tools.py)
    # já validava contra esse catálogo; até aqui só o prólogo escapava
    # dessa regra, porque criava o herói ANTES de qualquer ferramenta
    # existir. "Vila de Phandalin" é o default determinístico — um vilarejo
    # é o único tipo de local aqui que faz sentido como ponto de partida
    # neutro, sem pressupor perigo imediato nem viagem já em andamento.
    locais_validos = regras.get_locations_list()
    local_padrao = "Vila de Phandalin" if "Vila de Phandalin" in locais_validos else locais_validos[0]

    # BYOK (rodada de conserto) — com a chave do jogador, `chamar_clients`
    # do servidor pode estar vazio e mesmo assim o prólogo funciona.
    if chamar_fn is None and not llm_client.clients:
        return {
            "local_inicial": local_padrao,
            "local_inicial_descricao": None,
            "clima_inicial": "Nublado",
            "nome_missao": "Jornada Inicial",
            "objetivo_missao": "Chegar à cidade.",
            "intro_narrativa": f"{char.nome} inicia sua jornada na estrada.",
            "atos": ATOS_PADRAO,
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

    "local_inicial" pode ser um destes nomes, exato, sem variação: {", ".join(locais_validos)}.
    Ou, se nenhum encaixar bem na história do herói, PODE inventar um lugar novo — mas só nesse
    caso preencha também "local_inicial_descricao" (2-3 frases: aparência, clima, o que o lugar
    é) — sem essa descrição, um nome fora da lista é ignorado e o jogo cai no local padrão.

    Além da missão imediata, esboce a campanha inteira em 3 a 5 Atos — o
    arco que guia a história por trás das cenas (o jogador nunca vê essa
    lista, só o Ato atual, um de cada vez). Cada Ato é um passo maior que
    "nome_missao"/"objetivo_missao" (ex: Ato 1 pode conter várias missões
    miúdas dentro dele). Ligue os Atos ao objetivo e ao passado do herói.

    Responda APENAS JSON:
    {{
        "local_inicial": "Nome do Local (da lista, exato — ou um nome novo, se justificado)",
        "local_inicial_descricao": "Só se 'local_inicial' for um nome NOVO (2-3 frases). Null se for da lista.",
        "clima_inicial": "Clima atmosférico",
        "nome_missao": "Título da Missão Atual",
        "objetivo_missao": "O que ele deve fazer agora (curto)",
        "intro_narrativa": "Texto narrativo de 3 parágrafos imersivos.",
        "atos": [
            {{"titulo": "Nome curto do Ato 1", "objetivo": "O que precisa acontecer para ele terminar"}},
            {{"titulo": "Nome curto do Ato 2", "objetivo": "..."}},
            {{"titulo": "Nome curto do Ato 3", "objetivo": "..."}}
        ]
    }}
    """
    try:
        roteiro = chamar_mestre([{"role": "user", "content": prompt}], chamar_fn=chamar_fn)
    except ErroMestre as e:
        print("ERRO NO PRÓLOGO:", e.mensagem)
        return {
            "local_inicial": local_padrao,
            "local_inicial_descricao": None,
            "clima_inicial": "Chuvoso",
            "nome_missao": "Desconhecido",
            "objetivo_missao": "Sobreviver",
            "intro_narrativa": "Você acorda...",
            "atos": ATOS_PADRAO,
        }

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
            roteiro["local_inicial_descricao"] = None
    else:
        roteiro["local_inicial_descricao"] = None
    roteiro["atos"] = _validar_atos(roteiro.get("atos"))
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

    historia_resumo = f" | História: {heroi.historia_texto[:150]}..." if heroi.historia_texto else ""

    # Fase 3 da revisão de gameplay (Etapa 12/13, ADR-0027) — companheiros
    # recrutados são parte da cena o tempo todo, não só em combate: o
    # jogador conversa com eles fora de luta, e em combate o modelo precisa
    # saber que "atacar_com_aliado" existe. Um morto (hp 0) some daqui.
    aliados_vivos = [a for a in (heroi.aliados or []) if a["hp"] > 0]
    secao_aliados = (
        "\n    [ALIADOS PRESENTES] "
        + ", ".join(f"{a['nome']}, o(a) {a['classe']} (HP {a['hp']}/{a['hp_max']})" for a in aliados_vivos)
        if aliados_vivos
        else ""
    )

    # Fase 4 da revisão de gameplay (Etapa 12/13) — só o Ato ATUAL entra no
    # prompt, nunca o esqueleto inteiro (mesmo padrão de "não despejar a
    # estrutura" do resto do projeto). `ato_atual` é um índice — clampado
    # aqui porque um `QuestLog` salvo antes desta fase tem `atos=[]`, e
    # `atualizar_missao(avancar_ato=True)` não impede o índice de estourar
    # se chamado mais vezes do que há Atos.
    secao_ato = ""
    aviso_ato = ""
    if q_state.atos:
        idx = max(0, min(q_state.ato_atual, len(q_state.atos) - 1))
        ato = q_state.atos[idx]
        secao_ato = f"\n    [ATO ATUAL] {ato.titulo}: {ato.objetivo}"
        if idx < len(q_state.atos) - 1:
            aviso_ato = (
                ' Quando o objetivo do ATO ATUAL for cumprido de verdade (não a missão miúda, o '
                'Ato inteiro), chame "atualizar_missao" com avancar_ato=true — é o único jeito de a '
                "campanha avançar pro próximo Ato."
            )

    # Fase 6 da revisão de gameplay (Etapa 12/13) — relógio de facção: o
    # script (não o modelo) decide quando a urgência do Ato estourou —
    # `descansar("longo")` é quem avança o contador. Fica "ligado" até o
    # jogador avançar o Ato (`atualizar_missao(avancar_ato=True)` zera),
    # de propósito: o evento global não é uma linha só, é uma pressão que
    # continua até a história responder a ela.
    secao_evento_global = (
        "\n    [EVENTO GLOBAL] O tempo passou demais parado — o que o herói estava tentando evitar "
        "no Ato atual avançou sem ele. Deixe as consequências disso aparecerem na cena agora, "
        "mesmo que o jogador não tenha perguntado."
        if w_state.relogios.get(RELOGIO_URGENCIA, 0) >= RELOGIO_MAXIMO
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

    return f"""
    {secao_regras}
    {secao_memoria}
    [HEROI] {heroi.nome} ({heroi.raca} {heroi.classe}) | HP: {heroi.hp_atual}/{heroi.hp_max} | \
Ouro: {heroi.ouro}{secao_tracos}
    [PASSADO] Background: {heroi.background} | Objetivo: {heroi.objetivo} | \
Alinhamento: {heroi.alinhamento}{historia_resumo}
    [INVENTÁRIO] {heroi.inventario}{secao_aliados}
    [MISSÃO ATUAL] {q_state.nome_missao}: {q_state.objetivo_missao}{secao_ato}{secao_evento_global}
    [CENA] {w_state.local} | {w_state.clima} | {motor.periodo_do_dia(w_state.hora_do_dia)}
    {secao_combate}

    Você tem ferramentas para agir no mundo (dano, item, ouro, movimento,
    teste de atributo, consulta de regra, atualizar missão, concluir objetivo,
    recrutar aliado, descansar). Se o jogador cumprir um objetivo importante sem combate
    (enigma resolvido, NPC convencido, missão fechada por diplomacia), chame
    "concluir_objetivo" — é a única forma de ele ganhar XP fora de combate.
    Se um NPC se junta de verdade à jornada do herói (não uma ajuda de
    passagem), chame "recrutar_aliado" — ele passa a acompanhar e lutar ao
    lado do herói dali em diante.{aviso_ato} Se o jogador declarar que
    descansa, chame "descansar" (nunca cure PV narrando sozinho). Se o
    jogador usar um item/arma de forma criativa num teste de atributo (ex:
    um machado pesado pra arrombar uma porta), passe "item_usado" pra
    "rolar_teste" — o servidor decide se isso ajuda. Sempre passe "motivo"
    também, descrevendo em poucas palavras o que está sendo testado — o
    jogador vê isso no resultado, e pode conceder vantagem se um traço do
    herói (ver [TRAÇOS] acima) se aplicar. Se "mover" devolver
    "encontro" ("emboscada" ou "achado"), narre e aja de acordo na hora —
    é a estrada reagindo, não uma sugestão sua. Se "descansar" devolver
    "gancho_acampamento", puxe essa fala do companheiro antes de seguir.
    Use-as para qualquer mudança de
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
    palavra, nunca pela tipografia. Termine SEMPRE a narrativa com uma
    linha própria no formato "[OPCOES]: opção 1|opção 2|opção 3" — três
    ações curtas e concretas que fazem sentido AGORA, separadas por "|",
    sem numeração própria (ex: "[OPCOES]: Atacar o goblin|Recuar para a
    porta|Examinar o baú"). Essa linha nunca aparece pro jogador como texto
    — o servidor a transforma em botões — então nunca a mencione nem a
    explique na narrativa, só a escreva por último.
    """
