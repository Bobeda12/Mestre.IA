"""Mundo aberto: registro aditivo, ações compostas, conhecimento e agendas causais."""

import json
from typing import TYPE_CHECKING

from pydantic import ValidationError

from app.domain.eventos import DadosRolagem, EventoRolagem
from app.domain.living_world import (
    SAIDA_LIVRE,
    CenaPersistente,
    ConflitoMundo,
    Conhecimento,
    EntidadeCena,
    PessoaMundo,
)
from app.domain.state import LocalDescoberto
from app.infra.data_manager import regras
from app.services import rules_engine as motor

if TYPE_CHECKING:
    from app.services.tools import ToolExecutor


APTIDOES = {
    "Guerreiro": ("Engenharia de campanha", ["bloquear", "desbloquear", "quebrar"], "forca"),
    "Bárbaro": ("Força indomável", ["quebrar", "mover", "intimidar"], "forca"),
    "Ladino": ("Mãos e passos leves", ["destrancar", "ocultar", "investigar"], "destreza"),
    "Monge": ("Corpo e percepção", ["atravessar", "ocultar", "acalmar"], "sabedoria"),
    "Patrulheiro": ("Leitura do terreno", ["investigar", "acalmar", "ocultar"], "sabedoria"),
    "Paladino": ("Presença do juramento", ["ajudar", "negociar", "intimidar"], "carisma"),
    "Mago": ("Compreensão arcana", ["investigar", "acender", "apagar"], "inteligencia"),
    "Feiticeiro": ("Vontade elemental", ["acender", "apagar", "distrair"], "carisma"),
    "Bruxo": ("Influência inquietante", ["intimidar", "investigar", "distrair"], "carisma"),
    "Druida": ("Linguagem da natureza", ["acalmar", "investigar", "apagar"], "sabedoria"),
    "Clérigo": ("Amparo e discernimento", ["ajudar", "acalmar", "negociar"], "sabedoria"),
    "Bardo": ("Palavra e improviso", ["negociar", "distrair", "acalmar"], "carisma"),
}
ACOES = {
    "examinar": "Examinar",
    "investigar": "Investigar",
    "mover": "Mover",
    "bloquear": "Bloquear",
    "desbloquear": "Remover bloqueio",
    "abrir": "Abrir",
    "destrancar": "Destrancar",
    "quebrar": "Quebrar",
    "acender": "Acender",
    "apagar": "Apagar",
    "atravessar": "Atravessar",
    "ocultar": "Ocultar-se",
    "acalmar": "Acalmar",
    "conversar": "Conversar",
    "negociar": "Negociar",
    "ajudar": "Oferecer ajuda",
    "intimidar": "Intimidar",
    "distrair": "Distrair",
    "pegar": "Recolher",
}


def migrar_mundo(w_state, heroi) -> bool:
    """Backfill para saves anteriores ao Mundo Vivo (Fase 0 do plano "jogo
    completo", 08/09/2026): um personagem criado antes tem `mundo` vazio e o
    painel mostraria "observe este lugar" pra sempre se o narrador nunca
    chamasse `registrar_cena`. Cria a cena do local atual com a descrição
    do catálogo (ou do local descoberto) e uma saída livre, registra o
    objetivo do herói e marca `versao_mundo = 1`. Devolve True se mudou
    algo — quem chama decide se precisa gravar."""
    if w_state.versao_mundo >= 1:
        return False
    mundo = w_state.mundo
    local = w_state.local
    if local and local not in mundo.cenas:
        descoberto = w_state.locais_descobertos.get(local)
        catalogo = regras.get_location(local) or {}
        descricao = (descoberto.descricao if descoberto else catalogo.get("descricao", "")) or ""
        mundo.cenas[local] = CenaPersistente(
            descricao=descricao[:1200],
            entidades={
                "estrada": EntidadeCena(
                    id="estrada",
                    nome="Estrada para fora",
                    tipo="saida",
                    destino=SAIDA_LIVRE,
                    descricao="A estrada continua. Você pode partir quando quiser.",
                )
            },
            visitas=1,
        )
    objetivo = (getattr(heroi, "objetivo", "") or "").strip()
    if objetivo and objetivo not in mundo.objetivos:
        mundo.objetivos.append(objetivo)
    w_state.versao_mundo = 1
    return True


def registrar_fato(
    executor: "ToolExecutor", texto: str, fonte: str = "Observação direta", natureza: str = "fato"
) -> None:
    mundo = executor.w_state.mundo
    if any(f.texto == texto and f.natureza == natureza for f in mundo.conhecimento):
        return
    registro = Conhecimento.model_validate(
        {"texto": texto[:600], "natureza": natureza, "fonte": fonte, "turno": executor.w_state.turno}
    )
    mundo.conhecimento = [*mundo.conhecimento, registro][-150:]
    if natureza == "fato":
        executor.w_state.marcos = [*executor.w_state.marcos, texto][-60:]


def registrar_cena(executor: "ToolExecutor", descricao: str, entidades: list[dict]) -> dict:
    mundo = executor.w_state.mundo
    if len(entidades) > 20 or not descricao.strip() or len(descricao) > 1200:
        return {"erro": "Registre uma descrição e no máximo 20 entidades por chamada."}
    try:
        propostas = [EntidadeCena.model_validate(e) for e in entidades]
    except ValidationError as erro:
        return {"erro": str(erro)}
    if len({e.id for e in propostas}) != len(propostas):
        return {"erro": "IDs repetidos na cena."}
    local = executor.w_state.local
    if local not in mundo.cenas and len(mundo.cenas) >= 100:
        return {"erro": "Limite de locais desta campanha atingido."}
    cena = mundo.cenas.get(local, CenaPersistente(descricao=descricao, visitas=1))
    if len(set(cena.entidades) | {e.id for e in propostas}) > 30:
        return {"erro": "A cena comporta até 30 entidades."}
    for entidade in propostas:
        # Reapresentar o local jamais restaura portas, destrói evidências ou recria objetos.
        if entidade.id not in cena.entidades:
            entidade.estado = "intacto"
            entidade.descoberto = False
            entidade.bloqueado_por = None
            entidade.recolhido = False
            cena.entidades[entidade.id] = entidade
    mundo.cenas[local] = cena
    return {"registrado": True, "local": local, "entidades": list(cena.entidades)}


def registrar_pessoa(executor: "ToolExecutor", pessoa: dict) -> dict:
    try:
        npc = PessoaMundo.model_validate(pessoa)
    except ValidationError as erro:
        return {"erro": str(erro)}
    mundo = executor.w_state.mundo
    mercadoria_nova = [c for c in (regras.nome_canonico(n) for n in npc.mercadoria) if c][:8]

    def _atualizar_mercadoria(existente: PessoaMundo) -> dict:
        # Fase 1 (ADR-0033) — a única coisa que um recadastro pode mudar numa
        # pessoa conhecida é o que ela vende (achado ao vivo: o modelo quis
        # fazer de uma NPC da origem a mercadora da cena). Relações, memória
        # e segredo continuam intocados.
        if mercadoria_nova:
            existente.mercadoria = mercadoria_nova
            return {"mercadoria": mercadoria_nova}
        return {}

    if npc.id in mundo.pessoas:
        return {
            "existente": True, "aviso": "Memória e personalidade preservadas; use ações para mudar relações.",
            **_atualizar_mercadoria(mundo.pessoas[npc.id]),
        }
    # Achado ao vivo (Fase 0 do plano "jogo completo"): o modelo registrou
    # o mesmo NPC da origem com outro id ("ravi" vs "responsavel") e ele
    # apareceu duas vezes no painel. Nome igual no mesmo local é a mesma
    # pessoa — a existente vence, com as relações que já conquistou.
    nome_normalizado = npc.nome.strip().lower()
    repetida = next(
        (p for p in mundo.pessoas.values() if p.nome.strip().lower() == nome_normalizado and p.local == npc.local),
        None,
    )
    if repetida is not None:
        aviso = f"{repetida.nome} já está registrada como '{repetida.id}'."
        return {"existente": True, "id": repetida.id, "aviso": aviso, **_atualizar_mercadoria(repetida)}
    if len(mundo.pessoas) >= 100:
        return {"erro": "Limite de 100 pessoas por campanha."}
    if npc.local != executor.w_state.local:
        # Achado ao vivo (Fase 1): o modelo registrou o lojista com local
        # "Loja de Suprimentos" — um lugar DENTRO da vila onde o herói está.
        # Uma pessoa apresentada agora está aqui, por definição; o nome do
        # cantinho vai para a descrição, não para o registro de local.
        if npc.local and npc.local not in npc.descricao:
            npc.descricao = f"{npc.descricao} ({npc.local})".strip()[:500]
        npc.local = executor.w_state.local
    # O cadastro cria a pessoa, não resultados de ações ou relações conquistadas.
    if npc.raca not in regras.get_races_list():
        npc.raca = "Humano"  # o retrato do painel vem de /assets/races/<raca>.png
    # Mercadoria só com nomes do catálogo (nome canônico); o resto é descartado.
    npc.mercadoria = mercadoria_nova
    npc.confianca = max(-30, min(30, (executor.heroi.reputacao_npcs or {}).get(npc.nome, 0)))
    npc.segredo_revelado = False
    npc.lembrancas = []
    npc.promessas = []
    mundo.pessoas[npc.id] = npc
    return {"registrado": npc.id}


def registrar_conflito(executor: "ToolExecutor", conflito: dict) -> dict:
    try:
        novo = ConflitoMundo.model_validate(conflito)
    except ValidationError as erro:
        return {"erro": str(erro)}
    mundo = executor.w_state.mundo
    if novo.id in mundo.conflitos:
        return {"existente": True, "aviso": "O relógio existente foi preservado."}
    pessoa = mundo.pessoas.get(novo.agente)
    if not pessoa or novo.local != pessoa.local or novo.local != executor.w_state.local:
        return {"erro": "O agente do conflito deve estar registrado e presente no local atual."}
    if len(mundo.conflitos) >= 40:
        return {"erro": "Limite de conflitos desta campanha atingido."}
    if novo.efeito == "bloquear":
        cena = mundo.cenas.get(novo.local)
        if not cena or novo.alvo not in cena.entidades:
            return {"erro": "O alvo do bloqueio precisa existir no cenário."}
    novo.progresso = novo.intervencoes = 0
    novo.estado = "ativo"
    novo.desfecho = ""
    novo.proximo_avanco = mundo.minutos + novo.intervalo
    mundo.conflitos[novo.id] = novo
    executor.eventos.append(f"Um conflito se anuncia: {novo.sinal}")
    return {"registrado": novo.id, "sinal": novo.sinal, "minutos_por_etapa": novo.intervalo}


def avancar_tempo(executor: "ToolExecutor", minutos: int, atualizar_hora: bool = True) -> None:
    mundo = executor.w_state.mundo
    antes = mundo.minutos
    mundo.minutos += minutos
    if atualizar_hora:
        horas = mundo.minutos // 60 - antes // 60
        executor.w_state.hora_do_dia = (executor.w_state.hora_do_dia + horas) % 24
    for conflito in mundo.conflitos.values():
        if conflito.estado != "ativo":
            continue
        while mundo.minutos >= conflito.proximo_avanco and conflito.progresso < conflito.etapas:
            conflito.progresso += 1
            conflito.proximo_avanco += conflito.intervalo
        if conflito.progresso < conflito.etapas:
            continue
        conflito.estado = "concretizado"
        conflito.desfecho = conflito.consequencia
        if conflito.efeito == "bloquear":
            entidade = mundo.cenas[conflito.local].entidades[conflito.alvo]
            if entidade.estado != "destruido":
                entidade.estado = "bloqueado"
        elif conflito.efeito == "partir":
            mundo.pessoas[conflito.agente].disposicao = "ausente"
        if conflito.local == executor.w_state.local:
            registrar_fato(executor, conflito.consequencia, mundo.pessoas[conflito.agente].nome)
            executor.eventos.append(f"⏳ {conflito.consequencia}")


def bonus_aptidao(classe: str, acao: str, especializacoes: dict[str, str]) -> int:
    bonus = 2 if acao in APTIDOES.get(classe, ("", [], ""))[1] else 0
    sociais = {"negociar", "ajudar", "acalmar", "intimidar", "distrair"}
    caminho = "diplomata" if acao in sociais else "explorador"
    return bonus + sum(1 for escolha in especializacoes.values() if escolha == caminho)


def _testar(
    executor: "ToolExecutor", acao: str, alvo: str, atributo: str, cd: int, assinatura: str, bonus_extra: int = 0
) -> bool | None:
    mundo = executor.w_state.mundo
    chave = f"{executor.w_state.local}:{alvo}:{acao}"
    if mundo.tentativas.get(chave) == assinatura:
        return None
    bonus = motor.calcular_modificador(executor.heroi.atributos.get(atributo, 10))
    bonus += motor.bonus_proficiencia(executor.heroi.nivel or 1)
    bonus += bonus_aptidao(executor.heroi.classe, acao, mundo.especializacoes) + bonus_extra
    cd = motor.ajustar_cd_por_dificuldade(cd, executor.heroi.dificuldade)
    resultado = motor.resolver_teste_atributo(bonus, cd, executor.rng)
    executor.eventos.append(
        EventoRolagem(
            f"{ACOES.get(acao, acao)}: {resultado.total} vs CD {cd} — "
            f"{'sucesso' if resultado.sucesso else 'falha; tente outra abordagem ou altere a situação'}.",
            DadosRolagem(
                tipo="teste",
                quem="heroi",
                alvo=alvo,
                d20=resultado.rolagem,
                bonus=bonus,
                total=resultado.total,
                cd=cd,
                sucesso=resultado.sucesso,
                atributo=atributo,
                motivo=acao,
            ),
        )
    )
    if not resultado.sucesso:
        mundo.tentativas[chave] = assinatura
    return resultado.sucesso


def _finalizar(executor: "ToolExecutor", resultado: dict, significativo: bool = False) -> dict:
    if significativo:
        registrar_fato(executor, resultado["descricao"])
    if executor.c_state.ativo:
        resultado.update(executor._resolver_reacao_inimiga())
    return resultado


def agir_no_mundo(executor: "ToolExecutor", acao: str, alvo: str, meio: str | None = None, proposta: str = "") -> dict:
    if acao not in ACOES:
        return {"erro": "Combine ações conhecidas: " + ", ".join(ACOES)}
    mundo, local = executor.w_state.mundo, executor.w_state.local
    pessoa = mundo.pessoas.get(alvo)
    if pessoa:
        return _agir_pessoa(executor, pessoa, acao, proposta, meio)
    cena = mundo.cenas.get(local)
    entidade = cena.entidades.get(alvo) if cena else None
    if entidade is None or entidade.recolhido:
        return {"erro": "Esse alvo não existe no local atual. Registre a cena observada antes de agir."}
    if acao == "examinar":
        return {
            "descricao": entidade.descricao,
            "estado": entidade.estado,
            "propriedades": entidade.propriedades,
            "pista": entidade.pista if entidade.descoberto else None,
        }
    if executor.heroi.hp_atual <= 0:
        return {"erro": "Um herói inconsciente não pode agir."}
    if entidade.estado == "destruido" and acao not in {"atravessar", "investigar"}:
        return {"erro": "Esse objeto já foi destruído."}
    props = entidade.propriedades
    material = cena.entidades.get(meio or "") if cena else None
    item = meio if meio in (executor.heroi.inventario or []) else None
    if meio and not material and not item:
        return {"erro": "O meio escolhido precisa estar na cena ou no inventário."}
    if material and (material.estado in {"destruido", "movido"} or material.recolhido):
        return {"erro": "Esse material já foi destruído ou empregado em outra alteração."}
    restricoes = {
        "mover": "movel",
        "destrancar": "trancado",
        "acender": "inflamavel",
        "ocultar": "cobertura",
        "pegar": "coletavel",
    }
    if acao in restricoes and restricoes[acao] not in props:
        return {"erro": f"O alvo não possui a propriedade {restricoes[acao]}."}
    if acao == "bloquear" and (entidade.tipo != "saida" or not material or "movel" not in material.propriedades):
        return {"erro": "Escolha uma saída e um objeto móvel da cena para bloqueá-la."}
    if acao == "acalmar" and entidade.tipo != "animal":
        return {"erro": "Acalmar exige uma pessoa ou animal."}
    if acao in {"conversar", "negociar", "ajudar", "intimidar", "distrair"}:
        return {"erro": "Essa ação exige uma pessoa presente."}
    if acao == "acender" and not item and executor.heroi.classe not in {"Mago", "Feiticeiro", "Bruxo"}:
        return {"erro": "Use uma Tocha do inventário, ou uma classe com manipulação arcana."}
    if acao == "acender" and item and item != "Tocha":
        return {"erro": "Este item não é uma fonte de fogo reconhecida."}
    if acao == "atravessar":
        if entidade.tipo != "saida" or not entidade.destino:
            return {"erro": "O alvo não é uma saída com destino conhecido."}
        if executor.c_state.ativo:
            return {"erro": "Escape do combate antes de viajar."}
        if entidade.estado == "bloqueado" or ("trancado" in props and entidade.estado != "destruido"):
            return {"erro": "A passagem está bloqueada ou trancada. Você pode buscar outra solução."}
        executor.w_state.local = entidade.destino
        executor.w_state.locais_descobertos.setdefault(
            entidade.destino, LocalDescoberto(descricao=f"Destino de {entidade.nome}, vindo de {local}.")
        )
        destino = mundo.cenas.setdefault(entidade.destino, CenaPersistente())
        destino.visitas += 1
        if not destino.entidades:
            destino.entidades["retorno"] = EntidadeCena(
                id="retorno",
                nome=f"Voltar para {local}",
                tipo="saida",
                destino=local,
                descricao="O caminho por onde você chegou.",
            )
        for conflito in mundo.conflitos.values():
            if conflito.local == entidade.destino and conflito.estado == "concretizado":
                registrar_fato(executor, conflito.desfecho)
        return {"descricao": f"Você atravessa {entidade.nome} e chega a {entidade.destino}."}
    if acao == "abrir":
        if "trancado" in props or entidade.estado == "bloqueado":
            return {"erro": "Primeiro remova o bloqueio ou a tranca."}
        if entidade.estado == "aberto":
            return {"erro": "Já está aberto."}
    if acao == "desbloquear" and entidade.estado != "bloqueado":
        return {"erro": "Não há bloqueio para remover."}
    if acao == "apagar" and entidade.estado != "aceso":
        return {"erro": "Não há fogo neste alvo."}
    if acao == "acender" and entidade.estado == "aceso":
        return {"erro": "O alvo já está aceso."}
    if acao == "investigar" and entidade.descoberto:
        return {"descricao": entidade.pista or "Você já examinou todos os detalhes deste objeto.", "repetida": True}
    atributo = {
        "destrancar": "destreza",
        "investigar": "inteligencia",
        "acalmar": "sabedoria",
        "ocultar": "destreza",
        "acender": "inteligencia",
        "apagar": "sabedoria",
    }.get(acao, "forca")
    cd = 14 if "pesado" in props or "trancado" in props else 10
    assinatura = json.dumps([entidade.estado, props, meio, executor.heroi.nivel, mundo.especializacoes], sort_keys=True)
    teste = (
        True
        if acao in {"abrir", "acender", "apagar", "investigar", "pegar"}
        else _testar(
            executor,
            acao,
            alvo,
            atributo,
            cd,
            assinatura,
        )
    )
    if teste is None:
        return {"erro": "Essa tentativa já falhou nestas condições. Mude os meios ou escolha outra abordagem."}
    if not teste:
        return _finalizar(executor, {"sucesso": False, "descricao": "A tentativa falhou; a situação continua aberta."})
    descricao = f"{ACOES[acao]}: {entidade.nome}."
    if acao == "investigar":
        entidade.descoberto = True
        descricao = entidade.pista or (
            f"Você conhece a estrutura de {entidade.nome}: {', '.join(props) or 'sem mecanismo oculto'}."
        )
        if entidade.pista:
            chave = f"descoberta:{local}:{entidade.id}"
            if chave not in executor.w_state.objetivos_concluidos:
                executor.w_state.objetivos_concluidos.append(chave)
                executor._aplicar_xp(20 + 10 * (executor.heroi.nivel or 1))
    elif acao == "pegar":
        entidade.recolhido = True
        executor.heroi.inventario = [*executor.heroi.inventario, entidade.nome]
        descricao = f"Você recolheu {entidade.nome}. O objeto saiu da cena e está na sua mochila."
    elif acao == "bloquear":
        assert material is not None
        entidade.estado, entidade.bloqueado_por = "bloqueado", material.id
        material.estado = "movido"
        descricao = f"{entidade.nome} foi bloqueada com {material.nome}."
    elif acao == "desbloquear":
        bloqueio = cena.entidades.get(entidade.bloqueado_por or "") if cena else None
        if bloqueio:
            bloqueio.estado = "intacto"
        entidade.estado, entidade.bloqueado_por = "intacto", None
    elif acao == "destrancar":
        entidade.propriedades = [p for p in props if p != "trancado"]
        entidade.estado = "aberto"
    elif acao == "ocultar":
        executor.c_state.heroi_escondido = True
    elif acao == "acalmar":
        entidade.descoberto = True
        descricao = f"{entidade.nome} se acalma e permite sua aproximação."
    else:
        if acao == "abrir":
            entidade.estado = "aberto"
        elif acao == "mover":
            entidade.estado = "movido"
        elif acao == "quebrar":
            entidade.estado = "destruido"
        elif acao == "acender":
            entidade.estado = "aceso"
        elif acao == "apagar":
            entidade.estado = "apagado"
    executor.eventos.append(descricao)
    return _finalizar(executor, {"sucesso": True, "descricao": descricao}, significativo=True)


def _agir_pessoa(executor: "ToolExecutor", pessoa: PessoaMundo, acao: str, proposta: str, meio: str | None) -> dict:
    mundo = executor.w_state.mundo
    if pessoa.local != executor.w_state.local or pessoa.disposicao == "ausente":
        return {"erro": "Essa pessoa não está presente."}
    if acao == "examinar":
        return {"descricao": pessoa.descricao, "disposicao": pessoa.disposicao}
    if acao == "conversar":
        fala = f"{pessoa.nome} quer {pessoa.objetivo}."
        if pessoa.disposicao == "hostil":
            fala = f"{pessoa.nome} recusa a conversa. Você pode mudar a situação ou seguir outro caminho."
        else:
            for conhecimento in pessoa.conhecimentos:
                if conhecimento.publico:
                    registrar_fato(executor, conhecimento.texto, pessoa.nome, conhecimento.natureza)
            if pessoa.confianca >= 25 and pessoa.segredo:
                pessoa.segredo_revelado = True
                registrar_fato(executor, pessoa.segredo, pessoa.nome, "suspeita")
                fala += f" Em confiança, conta: {pessoa.segredo} (depoimento ainda não verificado)."
        executor.eventos.append(fala)
        return _finalizar(executor, {"descricao": fala, "necessidade": pessoa.necessidade})
    if acao not in {"negociar", "ajudar", "intimidar", "distrair", "acalmar"}:
        return {"erro": "Use conversar, negociar, ajudar, intimidar, distrair ou acalmar para interagir com pessoas."}
    if not proposta.strip():
        return {"erro": "Descreva sua proposta ou intenção; o personagem precisa de algo concreto a que reagir."}
    if meio and meio not in (executor.heroi.inventario or []):
        return {"erro": "Você não possui o item oferecido."}
    # Limites não são apagados por um d20 alto. Satisfazer necessidade concreta abre cooperação maior.
    oferta_util = bool(pessoa.necessidade and meio == pessoa.necessidade)
    assinatura = json.dumps([pessoa.confianca, pessoa.disposicao, meio, executor.heroi.nivel, mundo.especializacoes])
    resultado = _testar(
        executor,
        acao,
        pessoa.id,
        "carisma",
        12 + (3 if pessoa.disposicao == "hostil" else 0),
        assinatura,
        bonus_extra=(4 if oferta_util else 0) + pessoa.confianca // 20,
    )
    if resultado is None:
        return {"erro": "A mesma abordagem já falhou. Ofereça um recurso diferente ou obtenha outra relação."}
    delta = (10 if oferta_util else 5) if resultado else -3
    if acao == "intimidar":
        delta = -10
    pessoa.confianca = max(-100, min(100, pessoa.confianca + delta))
    reputacoes = dict(executor.heroi.reputacao_npcs or {})
    reputacoes[pessoa.nome] = pessoa.confianca
    executor.heroi.reputacao_npcs = reputacoes
    if resultado and oferta_util:
        inventario = list(executor.heroi.inventario)
        inventario.remove(meio)
        executor.heroi.inventario = inventario
    if resultado and acao in {"negociar", "ajudar", "acalmar"}:
        pessoa.disposicao = "cooperativo"
    if pessoa.confianca <= -20:
        pessoa.disposicao = "hostil"
    if resultado and acao == "distrair":
        executor.c_state.heroi_vantagem_inimiga = False
    if not resultado:
        chave = f"{executor.w_state.local}:{pessoa.id}:{acao}"
        mundo.tentativas[chave] = json.dumps(
            [
                pessoa.confianca,
                pessoa.disposicao,
                meio,
                executor.heroi.nivel,
                mundo.especializacoes,
            ]
        )
    descricao = (
        f"{pessoa.nome}: {'aceita uma cooperação limitada' if resultado else 'recusa a proposta'} — {proposta[:180]}."
    )
    if resultado and pessoa.limite:
        descricao += f" Seu limite permanece: {pessoa.limite}."
    if resultado and acao in {"negociar", "acalmar"} and pessoa.confianca >= 10:
        for inimigo in executor.c_state.inimigos:
            if inimigo.nome == pessoa.nome and inimigo.hp > 0:
                inimigo.afastado = True
                inimigo.intencao = "cessou hostilidade"
                descricao += " Interrompe a hostilidade sem perder pontos de vida."
        vitoria = executor._verificar_vitoria()
    else:
        vitoria = {}
    pessoa.lembrancas = [*pessoa.lembrancas, descricao][-40:]
    executor.eventos.append(descricao)
    return _finalizar(
        executor,
        {
            "sucesso": resultado,
            "descricao": descricao,
            "limite": pessoa.limite,
            "confianca": pessoa.confianca,
            **vitoria,
        },
        significativo=True,
    )


def registrar_vinculo(executor: "ToolExecutor", npc: str, natureza: str, texto: str) -> dict:
    pessoa = executor.w_state.mundo.pessoas.get(npc)
    if not pessoa or pessoa.local != executor.w_state.local or pessoa.disposicao == "ausente":
        return {"erro": "O interlocutor precisa estar presente."}
    if natureza not in {"promessa", "boato", "suspeita"} or not 1 <= len(texto.strip()) <= 500:
        return {"erro": "Registre promessa, boato ou suspeita em até 500 caracteres."}
    registro = Conhecimento.model_validate(
        {"texto": texto.strip(), "natureza": natureza, "fonte": pessoa.nome, "turno": executor.w_state.turno}
    )
    if not any(c.texto == registro.texto and c.natureza == natureza for c in pessoa.conhecimentos):
        pessoa.conhecimentos = [*pessoa.conhecimentos, registro][-40:]
    if natureza == "promessa" and texto not in pessoa.promessas:
        pessoa.promessas = [*pessoa.promessas, texto][-20:]
    registrar_fato(executor, texto, pessoa.nome, natureza)
    return {"registrado": natureza, "aviso": "Este registro não comprova a verdade do conteúdo."}


def intervir_conflito(executor: "ToolExecutor", conflito: str, abordagem: str, proposta: str) -> dict:
    mundo = executor.w_state.mundo
    alvo = mundo.conflitos.get(conflito)
    if not alvo or alvo.estado != "ativo" or alvo.local != executor.w_state.local:
        return {"erro": "O conflito precisa estar ativo e acessível no local atual."}
    if abordagem not in {"apoiar", "atrasar", "resolver"} or not proposta.strip():
        return {"erro": "Escolha apoiar, atrasar ou resolver e descreva como."}
    pessoa = mundo.pessoas[alvo.agente]
    if abordagem == "resolver" and pessoa.disposicao != "cooperativo":
        return {"erro": "Uma solução negociada exige primeiro conquistar a cooperação do agente."}
    assinatura = json.dumps([alvo.progresso, alvo.intervencoes, pessoa.confianca])
    sucesso = _testar(executor, "negociar", alvo.id, "carisma", 12, assinatura)
    if sucesso is None:
        return {"erro": "A intervenção já falhou nesta situação; mude as condições antes de repetir."}
    if not sucesso:
        return _finalizar(executor, {"sucesso": False, "descricao": "A intervenção não convenceu o agente."})
    if abordagem == "apoiar":
        alvo.proximo_avanco = min(alvo.proximo_avanco, mundo.minutos + 1)
    elif abordagem == "atrasar":
        alvo.proximo_avanco += alvo.intervalo
    else:
        alvo.intervencoes += 1
        if alvo.intervencoes >= 2:
            alvo.estado = "resolvido"
            alvo.desfecho = f"{alvo.nome}: acordo com {pessoa.nome}; {proposta[:250]}."
            registrar_fato(executor, alvo.desfecho)
            # Recompensa única atrelada ao conflito, nunca à repetição de uma fala.
            chave = f"conflito:{alvo.id}"
            if chave not in executor.w_state.objetivos_concluidos:
                executor.w_state.objetivos_concluidos.append(chave)
                executor._aplicar_xp(80 + 20 * (executor.heroi.nivel or 1))
    descricao = alvo.desfecho or f"{alvo.nome}: intervenção registrada ({abordagem})."
    executor.eventos.append(descricao)
    return _finalizar(executor, {"sucesso": True, "descricao": descricao}, significativo=True)


def definir_objetivo(executor: "ToolExecutor", objetivo: str) -> dict:
    if not 1 <= len(objetivo.strip()) <= 500:
        return {"erro": "Descreva seu objetivo em até 500 caracteres."}
    executor.q_state.nome_missao = "Meu caminho"
    executor.q_state.objetivo_missao = objetivo.strip()
    executor.w_state.mundo.objetivos = [*executor.w_state.mundo.objetivos, objetivo.strip()][-20:]
    executor.eventos.append(f"Seu próximo objetivo: {objetivo.strip()}")
    return {"objetivo": objetivo.strip()}


def escolher_especializacao(executor: "ToolExecutor", marco: str, escolha: str) -> dict:
    if marco not in {"3", "7"} or escolha not in {"explorador", "diplomata", "combatente"}:
        return {"erro": "Escolha explorador, diplomata ou combatente nos marcos 3 e 7."}
    if (executor.heroi.nivel or 1) < int(marco) or executor.c_state.ativo:
        return {"erro": "A escolha exige o nível correspondente e deve ser feita fora de combate."}
    executor.w_state.mundo.especializacoes[marco] = escolha
    return {"descricao": f"Especialização do nível {marco}: {escolha}. Pode trocar entre encontros."}


def painel_mundo(w_state, classe: str, privado: bool = False) -> dict:
    mundo = w_state.mundo
    cena = mundo.cenas.get(w_state.local, CenaPersistente())
    entidades = []
    for entidade in cena.entidades.values():
        if entidade.recolhido:
            continue
        dados = entidade.model_dump(exclude={"pista"})
        if privado or entidade.descoberto:
            dados["pista"] = entidade.pista
        entidades.append(dados)
    pessoas = []
    for pessoa in mundo.pessoas.values():
        if pessoa.local != w_state.local or pessoa.disposicao == "ausente":
            continue
        if privado:
            dados = pessoa.model_dump()
            dados["conhecimentos"] = dados["conhecimentos"][-8:]
            dados["lembrancas"] = dados["lembrancas"][-6:]
            dados["promessas"] = dados["promessas"][-4:]
        else:
            dados = pessoa.model_dump(exclude={"segredo", "medo", "objetivo", "limite", "conhecimentos"})
            if pessoa.segredo_revelado:
                dados["depoimento"] = pessoa.segredo
            # Fase 1 — vitrine com preço já calculado pelo servidor.
            from app.services import items as itens

            dados["vitrine"] = [
                {"item": n, "preco": itens.preco_compra((itens.ficha(n) or {}).get("preco", 0), pessoa.confianca)}
                for n in pessoa.mercadoria
            ]
        pessoas.append(dados)
    conflitos = []
    for conflito in mundo.conflitos.values():
        if conflito.local == w_state.local or privado:
            dados = (
                conflito.model_dump()
                if privado
                else conflito.model_dump(exclude={"consequencia", "efeito", "alvo", "objetivo"})
            )
            dados["minutos_restantes"] = max(0, conflito.proximo_avanco - mundo.minutos)
            conflitos.append(dados)
    aptidao = APTIDOES.get(classe, APTIDOES["Guerreiro"])
    return {
        "local": w_state.local,
        "descricao": cena.descricao,
        "entidades": entidades,
        "pessoas": pessoas,
        "conflitos": conflitos,
        "conhecimento": [c.model_dump() for c in mundo.conhecimento if c.publico or privado][-50:],
        "objetivos": mundo.objetivos,
        "especializacoes": mundo.especializacoes,
        "aptidao": {"nome": aptidao[0], "acoes": aptidao[1], "bonus": 2},
        "minutos": mundo.minutos,
    }
