"""As ferramentas que o modelo pode chamar (Etapa 4, ADR-0007) — o
substituto do `comando_combate`/`inimigos_sugeridos`/`spawn_battle` em JSON
solto da Etapa 3. O modelo continua só PROPONDO (ADR-0006); quem decide
número é sempre `rules_engine.py`/`combat.py`, chamados daqui.

`TOOLS_SCHEMA` é o `tools=[...]` mandado pro SDK da Groq. `ToolExecutor` liga
cada nome de ferramenta ao estado real de um turno (`heroi`, `c_state`,
`w_state`) e devolve, para cada chamada, um par (resultado para o modelo,
sucesso) — nunca deixa uma ferramenta malformada derrubar o turno inteiro."""

import json
import random
from collections.abc import Callable

from app.domain.state import CombatState, WorldState
from app.infra.data_manager import regras
from app.infra.db import Personagem
from app.services import combat
from app.services import rules_engine as motor


def _efeito_pocao_cura(executor: "ToolExecutor") -> dict:
    cura = motor.calcular_dano("2d4+2", rng=executor.rng)
    executor.heroi.hp_atual = min(executor.heroi.hp_max, executor.heroi.hp_atual + cura)
    executor.eventos.append(
        f"🧪 Poção de Cura: recupera {cura} PV. HP: {executor.heroi.hp_atual}/{executor.heroi.hp_max}."
    )
    return {"cura": cura, "hp_atual": executor.heroi.hp_atual}


# Itens com efeito mecânico conhecido. Um item fora deste mapa ainda pode ser
# "usado" (validação de posse continua valendo), só não move nenhum número —
# não existe um sistema de itens completo ainda, é escopo aberto para depois.
_EFEITOS_ITENS: dict[str, Callable[["ToolExecutor"], dict]] = {
    "Poção de Cura": _efeito_pocao_cura,
}


class ToolExecutor:
    """Um por turno. Mantém referência direta a `c_state`/`w_state` (o mesmo
    objeto que o router vai persistir depois) — ferramentas mutam em vez de
    substituir, senão a reatribuição feita pelo router perderia a mudança."""

    def __init__(
        self,
        heroi: Personagem,
        c_state: CombatState,
        w_state: WorldState,
        rng: random.Random | None = None,
    ) -> None:
        self.heroi = heroi
        self.c_state = c_state
        self.w_state = w_state
        self.rng = rng
        self.eventos: list[str] = []

    # -- ferramentas ---------------------------------------------------

    def rolar_teste(self, atributo: str, cd: int) -> dict:
        if atributo not in motor.ATRIBUTOS_VALIDOS:
            return {"erro": f"'{atributo}' não é um atributo válido: {sorted(motor.ATRIBUTOS_VALIDOS)}"}
        mod = motor.calcular_modificador(self.heroi.atributos.get(atributo, 10))
        resultado = motor.resolver_teste_atributo(mod, cd, self.rng)
        self.eventos.append(
            f"🎲 Teste de {atributo}: d20({resultado.rolagem})+{mod}={resultado.total} vs CD {cd} → "
            f"{'SUCESSO' if resultado.sucesso else 'FALHA'}."
        )
        return {"sucesso": resultado.sucesso, "total": resultado.total}

    def atacar(self, alvo: str, arma: str | None = None) -> dict:
        if not self.c_state.ativo:
            return {"erro": "não há combate ativo — chame iniciar_combate antes de atacar"}
        eventos = combat.turno_jogador(self.c_state, self.heroi.atributos, self.heroi.inventario, arma, alvo, self.rng)
        self.eventos.extend(eventos)

        if all(i.hp <= 0 for i in self.c_state.inimigos):
            self.c_state.ativo = False
            self.c_state.resultado = "vitoria"
            self.eventos.append("🏆 Combate vencido!")
            return {"resultado": "vitoria"}

        eventos_inimigos, dano = combat.turno_inimigos(self.c_state, self.heroi.defesa, self.rng)
        self.eventos.extend(eventos_inimigos)
        self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano)
        if self.heroi.hp_atual == 0 and dano > 0:
            self.eventos.append("🩸 Você caiu! Nos próximos turnos, role para não morrer.")
        return {"dano_recebido": dano, "hp_atual": self.heroi.hp_atual}

    def aplicar_dano(self, alvo: str, dado_dano: str, motivo: str = "") -> dict:
        dano = motor.calcular_dano(dado_dano, rng=self.rng)
        nomes_heroi = {"heroi", "herói", "você", "voce", self.heroi.nome.lower()}
        if alvo.lower() in nomes_heroi:
            self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano)
            self.eventos.append(
                f"🎲 {motivo or 'Dano recebido'}: {dado_dano} → {dano} de dano. "
                f"HP: {self.heroi.hp_atual}/{self.heroi.hp_max}."
            )
            return {"dano": dano, "hp_atual": self.heroi.hp_atual}

        alvo_obj = next((i for i in self.c_state.inimigos if i.nome == alvo and i.hp > 0), None)
        if alvo_obj is None:
            return {"erro": f"'{alvo}' não é um alvo válido (nem o herói, nem um inimigo vivo no combate)"}
        alvo_obj.hp = max(0, alvo_obj.hp - dano)
        self.eventos.append(
            f"🎲 {motivo or 'Dano aplicado'} em {alvo_obj.nome}: {dado_dano} → {dano} de dano. "
            f"{alvo_obj.nome}: {alvo_obj.hp}/{alvo_obj.max_hp} PV."
        )
        if alvo_obj.hp == 0:
            self.eventos.append(f"💀 {alvo_obj.nome} cai morto.")
        return {"dano": dano, "hp_atual": alvo_obj.hp}

    def mover(self, destino: str) -> dict:
        if self.c_state.ativo:
            return {"erro": "não é possível se mover durante um combate ativo"}
        dados = regras.get_location(destino)
        if not dados:
            return {"erro": f"'{destino}' não é um local conhecido", "locais_validos": regras.get_locations_list()}
        self.w_state.local = destino
        if dados.get("clima"):
            self.w_state.clima = dados["clima"]
        self.eventos.append(f"🧭 Vocês seguem para {destino}.")
        return {"local": destino, "descricao": dados.get("descricao", "")}

    def consultar_regra(self, termo: str) -> dict:
        termo_lower = termo.lower().strip()
        if not termo_lower:
            return {"encontrado": False}
        trechos = [
            linha.strip()
            for linha in regras.get_biblia().splitlines()
            if termo_lower in linha.lower() and linha.strip()
        ]
        if not trechos:
            return {"encontrado": False}
        return {"encontrado": True, "trechos": trechos[:3]}

    def usar_item(self, item: str) -> dict:
        if item not in self.heroi.inventario:
            return {"erro": f"'{item}' não está no inventário"}
        efeito = _EFEITOS_ITENS.get(item)
        if efeito is None:
            return {"usado": True, "efeito": "sem efeito mecânico definido — narre livremente o uso"}
        resultado = efeito(self)
        self.heroi.inventario = [i for i in self.heroi.inventario if i != item]
        return resultado

    def dar_item(self, item: str) -> dict:
        self.heroi.inventario = [*self.heroi.inventario, item]
        self.eventos.append(f"🎁 {self.heroi.nome} recebe: {item}.")
        return {"inventario": self.heroi.inventario}

    def gastar_ouro(self, qtd: int) -> dict:
        if qtd < 0:
            return {"erro": "quantidade não pode ser negativa"}
        if self.heroi.ouro < qtd:
            return {"erro": f"ouro insuficiente: tem {self.heroi.ouro}, precisa de {qtd}"}
        self.heroi.ouro -= qtd
        self.eventos.append(f"💰 Gasta {qtd} de ouro. Restam {self.heroi.ouro}.")
        return {"ouro_restante": self.heroi.ouro}

    def iniciar_combate(self, inimigos: list[str]) -> dict:
        if self.c_state.ativo:
            return {"erro": "já há um combate ativo"}
        novo, eventos, dano_surpresa = combat.iniciar_combate(
            inimigos, self.heroi.atributos, self.heroi.defesa, self.rng
        )
        self.c_state.ativo = novo.ativo
        self.c_state.inimigos = novo.inimigos
        self.c_state.sucessos_morte = novo.sucessos_morte
        self.c_state.falhas_morte = novo.falhas_morte
        self.c_state.resultado = novo.resultado
        self.eventos.extend(eventos)
        if dano_surpresa:
            self.heroi.hp_atual = max(0, self.heroi.hp_atual - dano_surpresa)
        return {"inimigos": [i.nome for i in self.c_state.inimigos], "dano_surpresa": dano_surpresa}

    # -- despacho --------------------------------------------------------

    _DESPACHO: dict[str, Callable] = {}  # preenchido abaixo da classe

    def executar(self, nome: str, args_json: str) -> tuple[dict, bool]:
        """Nunca deixa uma ferramenta malformada (nome inexistente, JSON
        quebrado, argumento errado, ou uma exceção interna) travar o turno —
        vira uma mensagem de erro que volta pro modelo como resultado da
        ferramenta, e ele tem o próximo passo do loop para se corrigir."""
        metodo = self._DESPACHO.get(nome)
        if metodo is None:
            return {"erro": f"ferramenta '{nome}' não existe"}, False
        try:
            args = json.loads(args_json) if args_json else {}
        except json.JSONDecodeError:
            return {"erro": f"argumentos de '{nome}' não são um JSON válido"}, False
        try:
            resultado = metodo(self, **args)
        except TypeError as e:
            return {"erro": f"argumentos inválidos para '{nome}': {e}"}, False
        except Exception as e:  # ferramenta com bug não pode derrubar o turno
            return {"erro": f"'{nome}' falhou ao executar: {e}"}, False
        return resultado, "erro" not in resultado


ToolExecutor._DESPACHO = {
    "rolar_teste": ToolExecutor.rolar_teste,
    "atacar": ToolExecutor.atacar,
    "aplicar_dano": ToolExecutor.aplicar_dano,
    "mover": ToolExecutor.mover,
    "consultar_regra": ToolExecutor.consultar_regra,
    "usar_item": ToolExecutor.usar_item,
    "dar_item": ToolExecutor.dar_item,
    "gastar_ouro": ToolExecutor.gastar_ouro,
    "iniciar_combate": ToolExecutor.iniciar_combate,
}


TOOLS_SCHEMA: list[dict] = [
    {
        "type": "function",
        "function": {
            "name": "rolar_teste",
            "description": (
                "Testa um atributo do herói contra uma dificuldade — para qualquer ação arriscada e "
                "incerta que NÃO seja atacar em combate (escalar, se esconder, persuadir, resistir a "
                "veneno, notar uma armadilha, equilibrar-se). Sempre que o jogador tenta algo que pode "
                "dar errado, chame esta ferramenta em vez de decidir sozinho se ele conseguiu."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "atributo": {
                        "type": "string",
                        "enum": ["forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"],
                        "description": "O atributo mais relevante para a ação (força para escalar/arrombar, "
                        "destreza para se esconder/equilibrar, carisma para persuadir/enganar, etc.).",
                    },
                    "cd": {
                        "type": "integer",
                        "description": "Classe de Dificuldade: 5=trivial, 10=fácil, 15=médio, "
                        "20=difícil, 25=muito difícil.",
                    },
                },
                "required": ["atributo", "cd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "atacar",
            "description": (
                "Resolve um ataque corpo a corpo ou à distância do herói contra um inimigo vivo do "
                "combate atual. Use sempre que o jogador declarar uma ação de ataque em combate."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "alvo": {
                        "type": "string",
                        "description": "Nome exato de um inimigo vivo listado no combate atual.",
                    },
                    "arma": {
                        "type": "string",
                        "description": "Nome exato de uma arma do inventário do herói. Omita para usar a "
                        "primeira arma reconhecida do inventário, ou ataque desarmado se não houver nenhuma.",
                    },
                },
                "required": ["alvo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "aplicar_dano",
            "description": (
                "Aplica dano que NÃO vem de um ataque com arma — queda, armadilha, fogo, veneno, magia "
                "ambiental. Não use para ataques normais em combate (isso é a ferramenta 'atacar'). Você "
                "propõe a notação de dado apropriada à fonte do dano (ex: uma queda de 3 metros é '1d6', "
                "uma fogueira é '2d6'); o servidor rola o dado de verdade."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "alvo": {
                        "type": "string",
                        "description": "'heroi', ou o nome exato de um inimigo vivo no combate atual.",
                    },
                    "dado_dano": {"type": "string", "description": "Notação de dado, ex: '1d6', '2d6+2'."},
                    "motivo": {"type": "string", "description": "Causa do dano, ex: 'queda', 'fogueira', 'veneno'."},
                },
                "required": ["alvo", "dado_dano"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mover",
            "description": (
                "Move o herói para outro local do mundo. Use quando o jogador declarar que está indo "
                "para um lugar específico e a cena não estiver em combate. O destino precisa ser um dos "
                "locais conhecidos do mundo — se não tiver certeza do nome exato, chame mesmo assim: o "
                "servidor devolve a lista de locais válidos se o nome não bater."
            ),
            "parameters": {
                "type": "object",
                "properties": {"destino": {"type": "string", "description": "Nome do local de destino."}},
                "required": ["destino"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "consultar_regra",
            "description": (
                "Busca uma regra na bíblia do mestre. Chame SEMPRE que o jogador fizer uma pergunta sobre "
                "como uma mecânica do jogo funciona — mesmo fora do personagem, mesmo em tom de dúvida "
                "('como funciona X?', 'o que acontece se eu Y?') — em vez de responder de memória."
            ),
            "parameters": {
                "type": "object",
                "properties": {"termo": {"type": "string", "description": "Palavra-chave da regra buscada."}},
                "required": ["termo"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "usar_item",
            "description": "Usa um item que já está no inventário do herói (poção, pergaminho, ferramenta).",
            "parameters": {
                "type": "object",
                "properties": {"item": {"type": "string", "description": "Nome exato do item no inventário."}},
                "required": ["item"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "dar_item",
            "description": (
                "Adiciona um item ao inventário do herói — recompensa de combate, saque encontrado, "
                "presente de um NPC. Use quando a cena claramente entrega um item novo ao jogador."
            ),
            "parameters": {
                "type": "object",
                "properties": {"item": {"type": "string", "description": "Nome do item a entregar."}},
                "required": ["item"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "gastar_ouro",
            "description": "Debita ouro do herói — compra, suborno, pagamento de taxa. Falha se não houver saldo.",
            "parameters": {
                "type": "object",
                "properties": {"qtd": {"type": "integer", "description": "Quantidade de ouro a gastar."}},
                "required": ["qtd"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "iniciar_combate",
            "description": (
                "Cria um combate quando a cena tem um confronto físico iminente com um ou mais monstros "
                "do bestiário do mundo. Use assim que a ameaça se torna hostil — não espere o jogador "
                "declarar 'eu ataco' primeiro, isso quem resolve é a ferramenta 'atacar' depois."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "inimigos": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Nomes de monstros do bestiário que encaixam na cena (ex: ['Goblin']).",
                    },
                },
                "required": ["inimigos"],
            },
        },
    },
]
