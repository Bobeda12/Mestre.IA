import json
import os

class DataManager:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.base_path, "data")
        
        # Carrega a Base de Conhecimento
        self.races = self._load_json("races.json")
        self.classes = self._load_json("classes.json")
        self.monsters = self._load_json("monsters.json")
        self.weapons = self._load_json("weapons.json")
        self.locations = self._load_json("locations.json") # Se tiver
        
        # Carrega a "Bíblia" (Texto Puro)
        self.biblia_text = self._load_text("biblia_mestre.txt")
    
    def _load_json(self, filename):
        filepath = os.path.join(self.data_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}

    def _load_text(self, filename):
        filepath = os.path.join(self.data_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return f.read()
        except:
            return "Você é um Mestre de RPG justo." # Fallback de segurança

    # --- Métodos de Acesso (RAG Simples) ---
    
    def get_biblia(self):
        return self.biblia_text

    def get_race_details(self, name): return self.races.get(name, {})
    def get_class_details(self, name): return self.classes.get(name, {})
    def get_races_list(self): return list(self.races.keys())
    def get_classes_list(self): return list(self.classes.keys())

    def get_relevant_rules(self, context_keywords):
        """
        Aqui poderíamos ter uma lógica para buscar regras específicas
        baseadas no que o jogador disse (ex: se disse 'magia', trazer regras de magia).
        Por enquanto, retornamos o bestiário completo e armas.
        """
        return {
            "monsters": self.monsters,
            "weapons": self.weapons
        }

regras = DataManager()