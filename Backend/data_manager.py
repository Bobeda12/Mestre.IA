import json
import os

class DataManager:
    def __init__(self):
        self.base_path = os.path.dirname(os.path.abspath(__file__))
        self.data_dir = os.path.join(self.base_path, "data")
        
        # Cache dos dados (para não ler o disco toda hora)
        self.races = self._load_json("races.json")
        self.classes = self._load_json("classes.json")
        # Futuro: self.weapons = ...
    
    def _load_json(self, filename):
        """Lê um arquivo JSON e retorna o dicionário, ou vazio se der erro."""
        filepath = os.path.join(self.data_dir, filename)
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"⚠️ Aviso: Arquivo {filename} não encontrado em {self.data_dir}")
            return {}
        except Exception as e:
            print(f"❌ Erro ao ler {filename}: {e}")
            return {}

    def get_races_list(self):
        """Retorna apenas os nomes e descrições breves para o menu."""
        # Retorna uma lista simples para o Frontend montar os cards
        return list(self.races.keys())

    def get_race_details(self, race_name):
        return self.races.get(race_name, {})

    def get_classes_list(self):
        return list(self.classes.keys())

    def get_class_details(self, class_name):
        return self.classes.get(class_name, {})

# Instância global para ser usada na API
regras = DataManager()