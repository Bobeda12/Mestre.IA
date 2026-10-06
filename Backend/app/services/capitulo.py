"""Trilha do capítulo: os passos em sequência de um arco.

A IA só escolhe e redige o próximo passo entre candidatos que o servidor
montou; quem diz que um passo foi cumprido é o servidor, lendo o estado do
jogo (ADR-0006: a IA propõe, o servidor decide). Só o passo atual existe —
o seguinte nasce quando ele fecha, a partir do que o jogador fez."""

import functools
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.domain.living_world import SAIDA_LIVRE, Arco, CondicaoPasso, Passo
from app.infra import llm_client
from app.services.living_world import MIN_PASSOS_ARCO, arco_ativo, condicoes_arco, fatos_do_arco

if TYPE_CHECKING:
    from app.services.tools import ToolExecutor

logger = logging.getLogger(__name__)

__all__ = ["MIN_PASSOS_ARCO"]

XP_PASSO = 50
MAX_PASSOS = 12
MAX_CANDIDATOS = 8
PRAZO_IA = 8.0
TEXTO_MIN, TEXTO_MAX = 8, 140
TEXTO_ENCERRAR = "Feche este capítulo quando estiver pronto."
TEXTO_CREDITO = "Caminho percorrido antes da trilha."


@dataclass(frozen=True)
class Candidato:
    condicao: CondicaoPasso
    texto: str  # molde do servidor, usado quando a IA não redige


def passo_atual(arco: Arco) -> Passo | None:
    return next((p for p in arco.passos if p.estado == "atual"), None)


def _feitos(arco: Arco) -> int:
    return sum(p.estado == "feito" and p.condicao.tipo != "encerrar_capitulo" for p in arco.passos)


def _fotografar(passo: Passo, w_state, arco: Arco) -> None:
    """Guarda o contador de agora, para o passo só valer com algo NOVO."""
    passo.turno_inicio = w_state.turno
    if passo.condicao.tipo == "registrar_fato":
        passo.base = fatos_do_arco(w_state, arco)
    elif passo.condicao.tipo == "intervir_conflito":
        conflito = w_state.mundo.conflitos.get(passo.condicao.alvo)
        passo.base = conflito.intervencoes if conflito else 0


def _entidade(w_state, condicao: CondicaoPasso):
    cena = w_state.mundo.cenas.get(condicao.local)
    return cena.entidades.get(condicao.alvo) if cena else None


def _cumprido(passo: Passo, w_state, arco: Arco) -> str | None:
    """A evidência (uma frase do servidor) se a condição já é verdade."""
    c, mundo = passo.condicao, w_state.mundo
    if c.tipo == "chegar_local":
        return f"Você chegou a {c.alvo}." if w_state.local == c.alvo else None
    if c.tipo in ("falar_pessoa", "ganhar_confianca"):
        pessoa = mundo.pessoas.get(c.alvo)
        if pessoa is None:
            return None
        if c.tipo == "falar_pessoa":
            return f"Você ouviu {pessoa.nome}." if pessoa.ouvida else None
        return f"{pessoa.nome} passou a cooperar com você." if pessoa.disposicao == "cooperativo" else None
    if c.tipo in ("investigar", "obter_item"):
        entidade = _entidade(w_state, c)
        if entidade is None:
            return None
        if c.tipo == "investigar":
            return f"Você investigou {entidade.nome}." if entidade.descoberto else None
        return f"Você recolheu {entidade.nome}." if entidade.recolhido else None
    if c.tipo == "enfrentar_chefe":
        return "Você venceu quem estava por trás disto." if arco.chefe_enfrentado else None
    if c.tipo == "intervir_conflito":
        conflito = mundo.conflitos.get(c.alvo)
        if conflito is not None and (conflito.intervencoes > passo.base or conflito.estado == "resolvido"):
            return f"Você interveio em {conflito.nome}."
        return None
    if c.tipo == "registrar_fato":
        if fatos_do_arco(w_state, arco) > passo.base:
            return (w_state.marcos[-1] if w_state.marcos else "Você descobriu algo novo.")[:200]
        return None
    return None  # encerrar_capitulo: quem marca é `encerrar_arco`


def _impossivel(passo: Passo, w_state, arco: Arco) -> bool:
    """O alvo sumiu: o passo não trava a trilha, é pulado e outro nasce."""
    c, mundo = passo.condicao, w_state.mundo
    if c.tipo in ("falar_pessoa", "ganhar_confianca"):
        pessoa = mundo.pessoas.get(c.alvo)
        return pessoa is None or pessoa.disposicao == "ausente"
    if c.tipo in ("investigar", "obter_item"):
        return _entidade(w_state, c) is None
    if c.tipo == "intervir_conflito":
        conflito = mundo.conflitos.get(c.alvo)
        return conflito is None or conflito.estado != "ativo"
    if c.tipo == "enfrentar_chefe":
        return not arco.chefe
    return False


def _acrescentar(arco: Arco, w_state, condicao: CondicaoPasso, texto: str, origem: str) -> Passo:
    for passo in arco.passos:
        if passo.estado == "atual":
            passo.estado, passo.turno_fim = "pulado", w_state.turno
    numero = int(arco.passos[-1].id[1:]) + 1 if arco.passos else 1
    novo = Passo(id=f"p{numero}", texto=texto, condicao=condicao, origem=origem)  # type: ignore[arg-type]
    _fotografar(novo, w_state, arco)
    arco.passos = [*arco.passos, novo][-MAX_PASSOS:]
    arco.passo_pendente = False
    return novo


def conferir_passo(executor: "ToolExecutor") -> None:
    """Roda depois de cada ferramenta bem-sucedida. Em combate não confere:
    o passo fecha quando a luta acaba, nunca no meio dela."""
    if executor.c_state.ativo:
        return
    w_state = executor.w_state
    arco = arco_ativo(w_state.mundo)
    if arco is None:
        return
    atual = passo_atual(arco)
    if atual is not None and atual.condicao.tipo != "encerrar_capitulo":
        evidencia = _cumprido(atual, w_state, arco)
        if evidencia:
            atual.estado, atual.evidencia, atual.turno_fim = "feito", evidencia, w_state.turno
            executor.eventos.append(f"✔ Passo cumprido: {atual.texto}")
            executor._aplicar_xp(XP_PASSO)
            arco.passo_pendente = True
        elif _impossivel(atual, w_state, arco):
            atual.estado, atual.turno_fim = "pulado", w_state.turno
            arco.passo_pendente = True
    atual = passo_atual(arco)
    if condicoes_arco(w_state)["pode_encerrar"] and (atual is None or atual.condicao.tipo != "encerrar_capitulo"):
        _acrescentar(arco, w_state, CondicaoPasso(tipo="encerrar_capitulo"), TEXTO_ENCERRAR, "servidor")


def candidatos_passo(w_state, heroi) -> list[Candidato]:
    """Próximos passos possíveis: condições que o servidor sabe conferir e
    que ainda são falsas, na ordem em que valem como escolha padrão."""
    arco = arco_ativo(w_state.mundo)
    if arco is None:
        return []
    mundo, local = w_state.mundo, w_state.local
    usados = {(p.condicao.tipo, p.condicao.alvo, p.condicao.local) for p in arco.passos}
    lista: list[Candidato] = []

    def propor(tipo: str, texto: str, alvo: str = "", onde: str = "") -> None:
        if (tipo, alvo, onde) not in usados:
            lista.append(Candidato(CondicaoPasso(tipo=tipo, alvo=alvo, local=onde), texto[:TEXTO_MAX]))  # type: ignore[arg-type]

    conflito = mundo.conflitos.get(arco.conflito_central)
    aberto = conflito is not None and conflito.estado == "ativo"
    agente = mundo.pessoas.get(conflito.agente) if conflito else None
    presentes = [p for p in mundo.pessoas.values() if p.local == local and p.disposicao != "ausente"]
    if conflito is not None and aberto and conflito.local != local:
        propor("chegar_local", f"Vá até {conflito.local}.", conflito.local)
    if agente is not None and agente in presentes and not agente.ouvida:
        propor("falar_pessoa", f"Fale com {agente.nome}.", agente.id)
    cena = mundo.cenas.get(local)
    entidades = list(cena.entidades.values()) if cena else []
    for entidade in entidades:
        if entidade.pista and not entidade.descoberto and not entidade.recolhido:
            propor("investigar", f"Investigue {entidade.nome}.", entidade.id, local)
    for pessoa in presentes:
        if not pessoa.ouvida and pessoa is not agente:
            propor("falar_pessoa", f"Fale com {pessoa.nome}.", pessoa.id)
    if aberto and agente is not None and agente in presentes and agente.ouvida and agente.disposicao != "cooperativo":
        propor("ganhar_confianca", f"Conquiste a cooperação de {agente.nome}.", agente.id)
    if conflito is not None and aberto and conflito.local == local and agente is not None \
            and agente.disposicao == "cooperativo":
        lista.append(Candidato(CondicaoPasso(tipo="intervir_conflito", alvo=conflito.id),
                               f"Intervenha em: {conflito.nome}."[:TEXTO_MAX]))
    if arco.chefe and not arco.chefe_enfrentado and _feitos(arco) >= MIN_PASSOS_ARCO - 1:
        propor("enfrentar_chefe", "Enfrente quem está por trás disto.")
    for entidade in entidades:
        if "coletavel" in entidade.propriedades and not entidade.recolhido:
            propor("obter_item", f"Recolha {entidade.nome}.", entidade.id, local)
    for entidade in entidades:
        destino = entidade.destino
        if entidade.tipo == "saida" and destino and destino != SAIDA_LIVRE and destino != local \
                and destino not in mundo.cenas:
            propor("chegar_local", f"Vá até {destino}.", destino)
    # Sempre possível: garante que a trilha nunca fica sem próximo passo.
    reserva = Candidato(CondicaoPasso(tipo="registrar_fato"), "Descubra algo novo sobre a situação.")
    return [*lista[: MAX_CANDIDATOS - 1], reserva]


def _pedir_ia(arco: Arco, candidatos: list[Candidato], objetivo: str,
              chamar_fn: Callable[..., Any] | None) -> tuple[int, str] | None:
    """A IA escolhe um candidato pelo índice e redige a frase. Qualquer
    falha (sem provedor, cota, JSON torto, índice inválido, texto fora do
    tamanho, nome do chefe) devolve None e o servidor usa o molde."""
    if chamar_fn is None and not llm_client.clients:
        return None
    from app.services.narrator import _ler_json

    feitos = [p for p in arco.passos if p.estado == "feito" and p.evidencia][-3:]
    historico = "\n".join(f"- {p.texto} → {p.evidencia}" for p in feitos) or "- (o capítulo acabou de começar)"
    opcoes = "\n".join(f"{i}. {c.texto}" for i, c in enumerate(candidatos))
    prompt = (
        f'Você escreve o próximo passo de um capítulo de RPG. Capítulo: "{arco.titulo}". '
        f"Premissa: {arco.premissa[:300]}\n"
        f"Rumo declarado pelo jogador: {objetivo.strip()[:200] or 'nenhum'}\n"
        f"O que o jogador fez (o mais recente por último):\n{historico}\n\n"
        f"Passos possíveis agora:\n{opcoes}\n\n"
        "Escolha UM, o que melhor continua o que o jogador fez. Reescreva-o em uma frase de até 120 "
        "caracteres, no imperativo (Fale, Procure, Descubra), ligada ao que aconteceu. Não decida pelo "
        "jogador o que ele sente ou pensa. Não invente pessoas, lugares nem objetos "
        "fora da lista e não revele quem está por trás do conflito.\n"
        'Responda APENAS JSON: {"candidato": <número>, "texto": "<frase>"}'
    )
    chamar = chamar_fn or functools.partial(llm_client.chamar_com_fallback, papel="fundo", prazo=PRAZO_IA)
    try:
        dados = _ler_json(chamar([{"role": "user", "content": prompt}], response_format={"type": "json_object"}))
    except Exception as erro:  # a trilha nunca trava por causa da IA
        logger.warning("proximo_passo: IA indisponível (%s); usando o molde do servidor", type(erro).__name__)
        return None
    indice, texto = dados.get("candidato"), dados.get("texto")
    if not isinstance(indice, int) or isinstance(indice, bool) or not 0 <= indice < len(candidatos):
        return None
    if not isinstance(texto, str):
        return None
    texto = " ".join(texto.replace("*", "").split())
    if not TEXTO_MIN <= len(texto) <= TEXTO_MAX or (arco.chefe and arco.chefe.casefold() in texto.casefold()):
        return None
    return indice, texto


def proximo_passo(w_state, heroi, q_state, chamar_fn: Callable[..., Any] | None = None) -> Passo | None:
    """Chamado pelo router no fim do request em que um passo fechou."""
    arco = arco_ativo(w_state.mundo)
    if arco is None or not arco.passo_pendente:
        return None
    if passo_atual(arco) is not None:
        arco.passo_pendente = False
        return None
    candidatos = candidatos_passo(w_state, heroi)
    proposta = _pedir_ia(arco, candidatos, getattr(q_state, "objetivo_missao", "") or "", chamar_fn)
    if proposta is None:
        return _acrescentar(arco, w_state, candidatos[0].condicao, candidatos[0].texto, "servidor")
    indice, texto = proposta
    return _acrescentar(arco, w_state, candidatos[indice].condicao, texto, "ia")


def garantir_passo(w_state, heroi) -> bool:
    """Todo arco ativo tem um passo atual. Cria um pelo molde do servidor
    quando falta (personagem novo, save antigo, request interrompido)."""
    arco = arco_ativo(w_state.mundo)
    if arco is None or passo_atual(arco) is not None:
        return False
    if condicoes_arco(w_state)["pode_encerrar"]:
        _acrescentar(arco, w_state, CondicaoPasso(tipo="encerrar_capitulo"), TEXTO_ENCERRAR, "servidor")
        return True
    escolhido = candidatos_passo(w_state, heroi)[0]
    _acrescentar(arco, w_state, escolhido.condicao, escolhido.texto, "servidor")
    return True


def migrar_capitulo(w_state, heroi) -> bool:
    """`versao_mundo` 1 → 2: um arco aberto antes da trilha não recomeça do
    zero — os turnos já jogados viram passos creditados (a regra antiga
    pedia 8 turnos; a nova, MIN_PASSOS_ARCO passos)."""
    mudou = False
    if w_state.versao_mundo == 1:
        arco = arco_ativo(w_state.mundo)
        if arco is not None and not arco.passos:
            creditos = min(MIN_PASSOS_ARCO, max(0, w_state.turno - arco.turno_inicio) // 3)
            arco.passos = [
                Passo(id=f"p{n}", texto=TEXTO_CREDITO, condicao=CondicaoPasso(tipo="registrar_fato"),
                      estado="feito", turno_inicio=arco.turno_inicio, turno_fim=w_state.turno)
                for n in range(1, creditos + 1)
            ]
        w_state.versao_mundo = 2
        mudou = True
    return garantir_passo(w_state, heroi) or mudou


def painel_capitulo(w_state, q_state) -> dict:
    """O que a aba Jornada mostra. Sem condição, sem alvo e sem chefe: só o
    texto de cada passo, o estado e a evidência."""
    arcos = w_state.mundo.arcos
    arco = arco_ativo(w_state.mundo)
    base: dict = {
        "ativo": arco is not None,
        "objetivo": getattr(q_state, "objetivo_missao", "") or "",
        "passos": [],
        "anteriores": [
            {"numero": n, "titulo": a.titulo, "resultado": a.resultado}
            for n, a in enumerate(arcos, start=1) if a.estado == "encerrado"
        ],
        "marcos": w_state.marcos[-12:],
    }
    if arco is None:
        return base
    cond = condicoes_arco(w_state)
    return {
        **base,
        "id": arco.id, "numero": arcos.index(arco) + 1, "titulo": arco.titulo, "premissa": arco.premissa,
        "passos": [{"texto": p.texto, "estado": p.estado, "evidencia": p.evidencia} for p in arco.passos],
        "pode_encerrar": cond["pode_encerrar"], "motivo_bloqueio": cond["motivo_bloqueio"],
    }
