import json
import unicodedata

from app.domain.items import ItemCatalogo
from app.infra.settings import settings


def _normalizar(nome: str) -> str:
    sem_acento = unicodedata.normalize("NFD", nome)
    return "".join(c for c in sem_acento if unicodedata.category(c) != "Mn").casefold().strip()


class DataManager:
    def __init__(self) -> None:
        self.data_dir = settings.data_dir

        self.races = self._load_json("races.json")
        self.classes = self._load_json("classes.json")
        self.monsters = self._load_json("monsters.json")
        self.weapons = self._load_json("weapons.json")
        self.locations = self._load_json("locations.json")
        # Fase 6 da revisão de gameplay (Etapa 12/13) — catálogo de itens
        # narrativos com tags (Tocha=[Fogo], Símbolo Sagrado=[Sagrado]...).
        # Diferente das `propriedades` de arma (Sutil/Munição — já afetam a
        # matemática de ataque, ver services/combat.py): tags são pra uso
        # criativo fora do combate (rolar_teste), não pra dano.
        self.items = self._load_json("items.json")
        # Fase 1 do plano "jogo completo" (ADR-0033) — o catálogo tem
        # NÚMEROS (cura, CA, preço); validar no boot é o que impede um JSON
        # torto de virar matemática de combate errada em pleno jogo.
        for dados in self.items.values():
            ItemCatalogo.model_validate(dados)
        self._indice_itens = {_normalizar(n): n for n in self.items}
        self._indice_armas = {_normalizar(n): n for g in self.weapons.values() for n in g}
        self.loot = self._load_json("loot.json")

        self.biblia_text = self._load_text("biblia_mestre.txt")

    def _load_json(self, filename: str) -> dict:
        try:
            with open(self.data_dir / filename, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            return {}

    def _load_text(self, filename: str) -> str:
        try:
            with open(self.data_dir / filename, encoding="utf-8") as f:
                return f.read()
        except OSError:
            return "Você é um Mestre de RPG justo."

    def get_biblia(self) -> str:
        return self.biblia_text

    def get_race_details(self, name: str) -> dict:
        return self.races.get(name, {})

    def get_class_details(self, name: str) -> dict:
        return self.classes.get(name, {})

    def get_races_list(self) -> list[str]:
        return list(self.races.keys())

    def get_classes_list(self) -> list[str]:
        return list(self.classes.keys())

    def get_relevant_rules(self, context_keywords: list[str] | None = None) -> dict:
        """RAG simples: hoje devolve o bestiário e as armas inteiros. Filtrar
        por `context_keywords` é escopo da Etapa 5 (memória / RAG sobre regras)."""
        return {"monsters": self.monsters, "weapons": self.weapons}

    def get_monster(self, nome: str) -> dict | None:
        """Busca um monstro pelo nome em todos os níveis de data/monsters.json.
        Usado por services/combat.py para spawnar inimigos de verdade —
        antes da Etapa 3, ninguém chamava esta função nem `self.monsters`."""
        for grupo in self.monsters.values():
            if nome in grupo:
                return dict(grupo[nome])
        return None

    def get_monstros_nivel_1(self) -> list[str]:
        return list(self.monsters.get("Nivel_1", {}).keys())

    def get_monstros_chefe(self) -> list[str]:
        """Etapa 11 (B-9) — quem é "chefe" vira um dos gatilhos de momento de
        alto impacto na narração (narrator.py:montar_contexto)."""
        return [*self.monsters.get("Chefe", {}).keys(), *self.monsters.get("Chefe_Elite", {}).keys()]

    def chefes_para_nivel(self, nivel: int) -> list[str]:
        """Fase 5 — o chefe do arco: fichas de 'Chefe' até o nível 5, 'Chefe_Elite' depois."""
        banda = "Chefe" if nivel <= 5 else "Chefe_Elite"
        return list(self.monsters.get(banda, {}).keys()) or self.get_monstros_chefe()

    def get_monstros_por_banda(self, banda: str) -> list[str]:
        """Bestiário por banda de nível (Nivel_1..Nivel_4, Chefe) — usado pelo
        escalonamento de perigo (rules_engine.desafio_sugerido) para sugerir
        encontros compatíveis com o nível do herói."""
        return list(self.monsters.get(banda, {}).keys())

    def get_weapon(self, nome: str) -> dict | None:
        exato = self._indice_armas.get(_normalizar(nome), nome)
        for grupo in self.weapons.values():
            if exato in grupo:
                return dict(grupo[exato])
        return None

    def nome_canonico(self, nome: str) -> str | None:
        """Nome exato do catálogo (item ou arma) para um nome "quase" — acento/caixa."""
        chave = _normalizar(nome)
        return self._indice_itens.get(chave) or self._indice_armas.get(chave)

    def listar_por_tipo(self, tipo: str) -> list[str]:
        if tipo == "arma":
            return [n for g in self.weapons.values() for n in g]
        return [n for n, d in self.items.items() if d.get("tipo") == tipo]

    def get_location(self, nome: str) -> dict | None:
        """Usado pela ferramenta `mover` (Etapa 4) para confirmar que o
        destino proposto pelo modelo existe em data/locations.json — mesma
        fronteira de confiança do bestiário (`get_monster`)."""
        dados = self.locations.get(nome)
        return dict(dados) if dados is not None else None

    def get_locations_list(self) -> list[str]:
        return list(self.locations.keys())

    def get_item(self, nome: str) -> dict | None:
        exato = self._indice_itens.get(_normalizar(nome), nome)
        dados = self.items.get(exato)
        return dict(dados) if dados is not None else None

    def get_tags(self, nome: str) -> list[str]:
        """Fase 6 — tags de um item OU arma, pra `rolar_teste` conceder
        bônus por uso criativo (`services/tools.py`). Armas reaproveitam
        `propriedades` como tag ("Pesada" ajuda a arrombar uma porta tanto
        quanto "cortar") — sem duplicar o dado em dois lugares."""
        item = self.get_item(nome)
        if item is not None:
            return item.get("tags", [])
        arma = self.get_weapon(nome)
        if arma is not None:
            return arma.get("propriedades", [])
        return []


regras = DataManager()
