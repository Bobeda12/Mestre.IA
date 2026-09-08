"""Objetivos e terreno jogáveis. O narrador escolhe a cena; o motor resolve seus efeitos."""

import random
from typing import TYPE_CHECKING

from app.domain.eventos import DadosRolagem, EventoRolagem
from app.domain.state import CombatState, WorldState
from app.services import rules_engine as motor

if TYPE_CHECKING:
    from app.services.tools import ToolExecutor


CENARIOS: dict[str, dict] = {
    "duelo": {
        "nome": "Entre aço e palavra",
        "tipo": "duelo",
        "descricao": "Cada abertura conta. A postura do adversário revela a próxima ameaça.",
        "objetivo": "Vencer o confronto ou encontrar uma saída.",
        "meta": 0,
        "interacoes": [
            {"id": "cobertura", "nome": "Tomar cobertura", "descricao": "+3 de defesa nesta rodada."},
            {
                "id": "distrair",
                "nome": "Provocar uma abertura",
                "descricao": "Teste de Carisma: reduz a precisão inimiga.",
            },
        ],
    },
    "emboscada": {
        "nome": "O caminho estreito",
        "tipo": "emboscada",
        "descricao": "Destroços cortam a passagem. A poeira pode esconder uma retirada.",
        "objetivo": "Romper a emboscada; o terreno também é uma arma.",
        "meta": 0,
        "interacoes": [
            {"id": "cobertura", "nome": "Atrás dos destroços", "descricao": "+3 de defesa nesta rodada."},
            {"id": "poeira", "nome": "Levantar poeira", "descricao": "Uma vez: inimigos atacam com desvantagem."},
            {"id": "derrubar", "nome": "Derrubar a barricada", "descricao": "Uma vez: teste de Força, dano em todos."},
        ],
    },
    "ritual": {
        "nome": "Os três selos",
        "tipo": "ritual",
        "descricao": "Três focos alimentam o ritual. Seus guardiões não precisam morrer para que ele termine.",
        "objetivo": "Desfazer 3 selos ou derrotar os guardiões.",
        "meta": 3,
        "interacoes": [
            {
                "id": "objetivo",
                "nome": "Desfazer um selo",
                "descricao": "Teste de Inteligência ou Sabedoria; 3 sucessos vencem.",
            },
            {"id": "cobertura", "nome": "Usar o altar", "descricao": "+3 de defesa nesta rodada."},
        ],
    },
    "resgate": {
        "nome": "Ninguém fica para trás",
        "tipo": "resgate",
        "descricao": "Uma pessoa está presa entre os combatentes. Cortar suas amarras abre outra forma de vencer.",
        "objetivo": "Abrir passagem e concluir 3 etapas do resgate, ou vencer o combate.",
        "meta": 3,
        "interacoes": [
            {
                "id": "objetivo",
                "nome": "Avançar o resgate",
                "descricao": "Teste de Força ou Destreza; 3 sucessos libertam o refém.",
            },
            {
                "id": "distrair",
                "nome": "Desviar a atenção",
                "descricao": "Teste de Carisma: inimigos têm desvantagem nesta rodada.",
            },
        ],
    },
    "cerco": {
        "nome": "A última passagem",
        "tipo": "cerco",
        "descricao": "A passagem ainda pode ser fechada. Trabalhar no mecanismo deixa você exposto.",
        "objetivo": "Preparar e fechar o portão em 3 etapas, ou derrotar os invasores.",
        "meta": 3,
        "interacoes": [
            {
                "id": "objetivo",
                "nome": "Acionar o mecanismo",
                "descricao": "Teste de Força ou Inteligência; 3 sucessos encerram o cerco.",
            },
            {"id": "cobertura", "nome": "Proteger-se na muralha", "descricao": "+3 de defesa nesta rodada."},
            {"id": "derrubar", "nome": "Soltar os escombros", "descricao": "Uma vez: teste de Força, dano em todos."},
        ],
    },
    "cacada": {
        "nome": "Caçador e presa",
        "tipo": "cacada",
        "descricao": "Há espaço para atrair o inimigo e usar o chão irregular a seu favor.",
        "objetivo": "Controlar a aproximação e sobreviver ao confronto.",
        "meta": 0,
        "interacoes": [
            {
                "id": "armadilha",
                "nome": "Improvisar uma armadilha",
                "descricao": "Uma vez: teste de Destreza ou Sabedoria, dano em um alvo.",
            },
            {"id": "cobertura", "nome": "Usar o relevo", "descricao": "+3 de defesa nesta rodada."},
        ],
    },
}


def preparar_encontro(c_state: CombatState, w_state: WorldState, cenario: str | None = None) -> None:
    if cenario in CENARIOS:
        c_state.cenario_id = str(cenario)
    else:
        # Não cria reféns ou rituais que não existem na ficção. Estes são escolhas explícitas do narrador.
        rng = random.Random(w_state.semente_aventura + w_state.turno * 31)
        c_state.cenario_id = rng.choice(["duelo", "emboscada", "cacada"])
    c_state.progresso_objetivo = 0
    c_state.objetivo_concluido = False
    c_state.interacoes_usadas = []


def painel_cena(c_state: CombatState, w_state: WorldState) -> dict:
    if not c_state.ativo:
        return {
            "tipo": "exploracao",
            "nome": w_state.local or "Sua jornada",
            "descricao": "Observe os detalhes, converse e tente caminhos próprios. O mundo guarda suas escolhas.",
            "objetivo": "Escolha seu próximo passo.",
            "progresso": 0,
            "meta": 0,
            "interacoes": [],
            "rodada": 0,
        }
    if w_state.local in w_state.mundo.cenas:
        return {
            "tipo": "confronto",
            "nome": w_state.local,
            "descricao": w_state.mundo.cenas[w_state.local].descricao,
            "objetivo": "Encontre sua saída: lute, use o ambiente ou tente negociar.",
            "progresso": 0,
            "meta": 0,
            "interacoes": [],
            "rodada": c_state.rodada,
        }
    cena = CENARIOS.get(c_state.cenario_id, CENARIOS["duelo"])
    return {
        **cena,
        "progresso": c_state.progresso_objetivo,
        "rodada": c_state.rodada,
        "interacoes": [i for i in cena["interacoes"] if i["id"] not in c_state.interacoes_usadas],
    }


def _teste(executor: "ToolExecutor", atributos: tuple[str, ...], motivo: str) -> bool:
    atributo = max(atributos, key=lambda a: executor.heroi.atributos.get(a, 10))
    bonus = motor.calcular_modificador(executor.heroi.atributos.get(atributo, 10))
    bonus += motor.bonus_proficiencia(executor.heroi.nivel or 1)
    cd = motor.ajustar_cd_por_dificuldade(11, executor.heroi.dificuldade)
    resultado = motor.resolver_teste_atributo(bonus, cd, executor.rng)
    dados = DadosRolagem(
        tipo="teste",
        quem="heroi",
        d20=resultado.rolagem,
        bonus=bonus,
        total=resultado.total,
        cd=cd,
        sucesso=resultado.sucesso,
        atributo=atributo,
        motivo=motivo,
    )
    executor.eventos.append(
        EventoRolagem(
            f"🎲 {motivo}: {resultado.total} vs CD {cd} — {'sucesso' if resultado.sucesso else 'falha'}.",
            dados,
        )
    )
    return resultado.sucesso


def interagir_cenario(executor: "ToolExecutor", interacao: str) -> dict:
    c_state, w_state = executor.c_state, executor.w_state
    if not c_state.ativo or executor.heroi.hp_atual <= 0:
        return {"erro": "Esta interação exige um combate ativo e um herói consciente."}
    cena = painel_cena(c_state, w_state)
    if interacao not in {i["id"] for i in cena["interacoes"]}:
        return {"erro": "Essa interação não está disponível neste cenário."}
    if interacao == "cobertura":
        c_state.heroi_bonus_ca = 3
        executor.eventos.append("🛡️ O terreno protege você: +3 de defesa nesta rodada.")
    elif interacao in {"distrair", "poeira"}:
        if interacao == "poeira" or _teste(executor, ("carisma",), "Desviar a atenção"):
            c_state.heroi_vantagem_inimiga = False
            executor.eventos.append("Os inimigos perdem a precisão: desvantagem nesta rodada.")
        if interacao == "poeira":
            c_state.interacoes_usadas.append(interacao)
    elif interacao == "objetivo":
        atributos: tuple[str, ...] = {
            "ritual": ("inteligencia", "sabedoria"),
            "resgate": ("forca", "destreza"),
            "cerco": ("forca", "inteligencia"),
        }[c_state.cenario_id]
        if _teste(executor, atributos, cena["objetivo"]):
            c_state.progresso_objetivo += 1
            executor.eventos.append(f"Uma etapa concluída: {c_state.progresso_objetivo}/{cena['meta']}.")
        else:
            # Falha custa a reação inimiga, mas nunca apaga as etapas conquistadas.
            executor.eventos.append("A tentativa consome tempo. O progresso anterior permanece.")
        if c_state.progresso_objetivo >= cena["meta"]:
            c_state.objetivo_concluido = True
            c_state.ativo = False
            c_state.resultado = "vitoria"
            marco = {
                "ritual": "Desfez os três selos e encerrou o ritual sem precisar matar seus guardiões.",
                "resgate": "Libertou a pessoa aprisionada e escapou com ela viva.",
                "cerco": "Fechou a passagem e impediu a entrada dos invasores.",
            }[c_state.cenario_id]
            w_state.marcos = [*w_state.marcos, f"{w_state.local}: {marco}"][-40:]
            executor.eventos.append(f"🏆 {marco}")
            # Não conta guardiões vivos como abates. A recompensa só ocorre na transição de estado.
            return {
                "resultado": "vitoria",
                "objetivo_concluido": True,
                **executor._aplicar_xp(60 + 20 * (executor.heroi.nivel or 1)),
            }
    else:
        c_state.interacoes_usadas.append(interacao)
        atributos = ("forca",) if interacao == "derrubar" else ("destreza", "sabedoria")
        if _teste(executor, atributos, "Usar o terreno contra o inimigo"):
            dano = 4 + 2 * (executor.heroi.nivel or 1)
            alvos = [i for i in c_state.inimigos if i.hp > 0 and not i.afastado]
            if interacao == "armadilha":
                alvos = alvos[:1]
            for alvo in alvos:
                alvo.hp = max(0, alvo.hp - dano)
                executor.eventos.append(
                    EventoRolagem(
                        f"O cenário causa {dano} de dano em {alvo.nome}.",
                        DadosRolagem(tipo="dano", quem="heroi", alvo=alvo.nome, dano=dano),
                    )
                )
            if all(i.hp <= 0 or i.afastado for i in c_state.inimigos):
                c_state.ativo = False
                c_state.resultado = "vitoria"
                executor.eventos.append("🏆 O terreno decidiu o combate!")
                return {"resultado": "vitoria", **executor._conceder_xp(c_state.inimigos)}
    return {"interacao": interacao, "progresso": c_state.progresso_objetivo, **executor._resolver_reacao_inimiga()}
