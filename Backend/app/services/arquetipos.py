"""Banco de arquétipos de papel (Fase 3.5, ADR-0046).

O bestiário clássico (Goblin, Orc, Troll) é de criaturas. Os arquétipos de
papel são de PESSOAS: um rei medroso, um assassino sádico, um mago orgulhoso.
Cada ficha tem `papel`, `temperamento` e uma `persona` curta. O narrador diz
quem é o inimigo (o nome da história e o jeito dele); o servidor escolhe a
ficha do nível certo, sem inventar número nenhum."""

import random
import unicodedata

from app.infra.data_manager import regras
from app.services import rules_engine as motor

# Palavras que o modelo costuma usar → o termo da ficha.
_PAPEIS = {
    "ladino": {"ladrao", "saqueador", "batedor", "bandido", "gatuno", "ladino"},
    "bruto": {"valentao", "brutamontes", "lutador", "guerreiro", "brigao", "bruto"},
    "mago": {"feiticeiro", "feiticeira", "bruxo", "bruxa", "arcano", "aprendiz", "mago", "maga", "arquimago"},
    "guarda": {"soldado", "sentinela", "vigia", "guarda"},
    "assassino": {"cacador", "mercenario", "espiao", "assassino", "assassina"},
    "nobre": {"rei", "rainha", "principe", "princesa", "duque", "lord", "barao", "nobre", "tirano"},
    "comandante": {"general", "capitao", "cavaleiro", "lider", "chefe", "comandante"},
    "clerigo": {"sacerdote", "sacerdotisa", "inquisidor", "monge", "cultista", "padre", "clerigo", "fanatico"},
}
_TEMPERAMENTOS = {
    "medroso": {"covarde", "assustado", "temeroso", "fraco", "medroso"},
    "orgulhoso": {"arrogante", "vaidoso", "soberbo", "altivo", "orgulhoso"},
    "fanatico": {"zeloso", "devoto", "obcecado", "fervoroso", "fanatico"},
    "astuto": {"calculista", "esperto", "manipulador", "frio", "astuto"},
    "sadico": {"cruel", "tirano", "malvado", "perverso", "sadico"},
    "honrado": {"leal", "honesto", "justo", "nobre", "honrado"},
}


def _sem_acento(texto: str) -> str:
    base = unicodedata.normalize("NFD", str(texto or "").strip().lower())
    return "".join(c for c in base if unicodedata.category(c) != "Mn")


def _canonico(texto: str, tabela: dict[str, set[str]]) -> str:
    palavras = _sem_acento(texto).replace("-", " ").split()
    for canonico, sinonimos in tabela.items():
        if any(p == canonico or p in sinonimos for p in palavras):
            return canonico
    return ""


def papel_de(texto: str) -> str:
    return _canonico(texto, _PAPEIS)


def temperamento_de(texto: str) -> str:
    return _canonico(texto, _TEMPERAMENTOS)


def arquetipos_do_nivel(nivel: int) -> list[str]:
    """Fichas de papel das bandas compatíveis com o nível."""
    return [
        nome
        for banda in motor.desafio_sugerido(nivel)
        for nome, ficha in regras.monsters.get(banda, {}).items()
        if ficha.get("por_papel")
    ]


def escolher(papel: str, temperamento: str, nivel: int, rng: random.Random | None = None) -> str | None:
    """A ficha de papel que melhor combina com o que o narrador descreveu,
    entre as do nível. Papel vale mais que temperamento. Sem nenhuma
    afinidade devolve None e o chamador cai no sorteio de sempre."""
    papel_c, temp_c = papel_de(papel), temperamento_de(temperamento)
    if not papel_c and not temp_c:
        return None
    pontuados = []
    for nome in arquetipos_do_nivel(nivel):
        ficha = regras.get_monster(nome) or {}
        pontos = 2 * (papel_c == ficha.get("papel")) + (temp_c == ficha.get("temperamento"))
        if pontos:
            pontuados.append((pontos, nome))
    if not pontuados:
        # O narrador descreveu uma PESSOA (papel reconhecido) mas o nível não
        # tem esse papel: melhor outra pessoa do nível que uma criatura
        # sorteada (achado do teste ao vivo: um "guarda" virou Esqueleto).
        todas = arquetipos_do_nivel(nivel)
        if papel_c and todas:
            return (rng or random).choice(todas)
        return None
    melhor = max(p for p, _ in pontuados)
    empatados = [n for p, n in pontuados if p == melhor]
    return (rng or random).choice(empatados)
