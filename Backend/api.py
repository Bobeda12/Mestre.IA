import os
import json
import time
from dotenv import load_dotenv
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
import google.generativeai as genai

load_dotenv()

MINHA_CHAVE = os.getenv("GENAI_API_KEY", "COLE_SUA_CHAVE_AQUI")

if MINHA_CHAVE == "COLE_SUA_CHAVE_AQUI":
    raise ValueError("Cole sua chave na linha 10!")

genai.configure(api_key=MINHA_CHAVE)

# MUDANÇA: Usando o nome exato que apareceu na sua lista
MODEL_NAME = "models/gemini-2.0-flash-lite"

SYSTEM_PROMPT = """
Você é um Mestre de RPG. 
REGRAS:
1. IDIOMA: Português do Brasil.
2. Seja breve (max 3 frases).
3. Responda APENAS JSON.

FORMATO JSON:
{
  "narrativa": "Texto...",
  "dano_recebido": 0,
  "novo_item": null,
  "hp_atual": 20,
  "game_over": false
}
"""

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

class UserAction(BaseModel):
    session_id: str
    action: str

class GameState:
    def __init__(self):
        self.history = []
        self.hp = 20
        self.inventory = []
        self.chat_session = None

games_db = {}

def limpar_json(texto_sujo):
    return texto_sujo.replace("```json", "").replace("```", "").strip()

def get_or_create_game(session_id: str):
    if session_id not in games_db:
        try:
            model = genai.GenerativeModel(
                model_name=MODEL_NAME,
                generation_config={"response_mime_type": "application/json"},
                system_instruction=SYSTEM_PROMPT
            )
            new_game = GameState()
            new_game.chat_session = model.start_chat(history=[])
            games_db[session_id] = new_game
            
            # Intro
            response = new_game.chat_session.send_message("O jogo começou.")
            texto_limpo = limpar_json(response.text)
            return new_game, json.loads(texto_limpo)
        except Exception as e:
            print(f"Erro ao criar jogo: {e}")
            # Fallback para não travar se a IA falhar na intro
            game_fallback = GameState()
            games_db[session_id] = game_fallback
            return game_fallback, {"narrativa": "Você acorda na masmorra... (Modo offline temporário)", "hp_atual": 20, "inventory": []}
            
    return games_db[session_id], None

@app.post("/chat")
async def chat_endpoint(user_input: UserAction):
    session_id = user_input.session_id
    action = user_input.action
    
    try:
        game, intro_data = get_or_create_game(session_id)
        
        if action == "START":
            if intro_data: return intro_data
            return {"narrativa": "Masmorra reiniciada.", "hp_atual": 20, "inventory": []}

        # Verifica se o jogo foi criado corretamente
        if not game.chat_session:
             return {"narrativa": "Erro crítico: O mestre sumiu. Tente reiniciar o backend.", "hp_atual": 20, "inventory": []}

        prompt = f"Ação: {action} (HP: {game.hp}, Itens: {game.inventory})"
        
        response = game.chat_session.send_message(prompt)
        texto_limpo = limpar_json(response.text)
        dados = json.loads(texto_limpo)
        
        dano = dados.get("dano_recebido", 0)
        item = dados.get("novo_item")
        
        if dano > 0: game.hp -= dano
        if item: game.inventory.append(item)
            
        dados["hp_atual"] = game.hp
        dados["inventory"] = game.inventory
        
        return dados

    except Exception as e:
        print(f"Erro no chat: {e}")
        msg = "O Mestre está pensando... (Erro de cota, tente em 10s)" if "429" in str(e) else "Erro desconhecido."
        return {
            "narrativa": msg,
            "hp_atual": 20, "dano_recebido": 0, "novo_item": None, "game_over": False, "inventory": []
        }