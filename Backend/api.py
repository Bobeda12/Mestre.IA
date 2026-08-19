import os
import json
import random
import re
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from sqlalchemy.orm import Session

from data_manager import regras
from database import HeroModel, get_db, criar_banco

load_dotenv()
criar_banco()

MINHA_CHAVE = os.getenv("GROQ_API_KEY")
client = Groq(api_key=MINHA_CHAVE) if MINHA_CHAVE else None
MODEL_NAME = "openai/gpt-oss-120b"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- MODELS ---
class CharacterCreationRequest(BaseModel):
    nome: str; raca: str; classe: str; 
    alinhamento: str; background: str; objetivo: str; historia_texto: str = ""

class UserAction(BaseModel):
    session_id: str; action: str

class LoadRequest(BaseModel):
    session_id: str

# --- UTILITÁRIOS ---
def rolar_dado(expressao):
    try:
        dados, mod = expressao.split('+') if '+' in expressao else (expressao, 0)
        qtd, faces = map(int, dados.split('d'))
        return sum(random.randint(1, faces) for _ in range(qtd)) + int(mod)
    except: return 0

def calcular_modificador(valor): return (valor - 10) // 2

# --- AGENTE ROTEIRISTA (Restaura o início com história) ---
def gerar_prologo_missao(char):
    if not client: 
        return {
            "local_inicial": "Estrada Real", "clima_inicial": "Nublado", 
            "nome_missao": "Jornada Inicial", "objetivo_missao": "Chegar à cidade.",
            "intro_narrativa": f"{char.nome} inicia sua jornada na estrada."
        }

    prompt = f"""
    Crie um prólogo de RPG Dark Fantasy para:
    Nome: {char.nome} ({char.raca} {char.classe})
    Passado: {char.background} | Objetivo: {char.objetivo} | Alinhamento: {char.alinhamento}
    
    O prólogo deve começar 'in media res' (já na ação), conectado ao passado dele.
    Responda APENAS JSON:
    {{
        "local_inicial": "Nome do Local",
        "clima_inicial": "Clima atmosférico",
        "nome_missao": "Título da Missão Atual",
        "objetivo_missao": "O que ele deve fazer agora (curto)",
        "intro_narrativa": "Texto narrativo de 3 parágrafos imersivos."
    }}
    """
    try:
        resp = client.chat.completions.create(model=MODEL_NAME, messages=[{"role": "user", "content": prompt}], response_format={"type": "json_object"})
        return json.loads(resp.choices[0].message.content)
    except Exception as e:
        print("ERRO NO PRÓLOGO:", repr(e))
        return {"local_inicial": "Taverna", "clima_inicial": "Chuvoso",
                "nome_missao": "Desconhecido", "objetivo_missao": "Sobreviver",
                "intro_narrativa": "Você acorda..."}

def montar_contexto(heroi, w_state, c_state, q_state):
    combate_txt = ""
    if c_state.get("ativo"):
        vivos = [i for i in c_state.get("inimigos", []) if i['hp'] > 0]
        combate_txt = f"[COMBATE ATIVO] Inimigos: {json.dumps(vivos, ensure_ascii=False)}"
    
    return f"""
    {regras.get_biblia()}
    [HEROI] {heroi.nome} ({heroi.classe}) | HP: {heroi.hp_atual}/{heroi.hp_max}
    [MISSÃO ATUAL] {q_state.get('nome_missao')}: {q_state.get('objetivo_missao')}
    [CENA] {w_state.get('local')} | {w_state.get('clima')}
    {combate_txt}
    
    Responda JSON: 
    {{ 
        "narrativa": "...", 
        "spawn_battle": false, 
        "hp_atual": {heroi.hp_atual} 
    }}
    """

# --- ENDPOINTS ---
@app.get("/options/races")
def get_races(): return {"opcoes": regras.get_races_list()}
@app.get("/options/classes")
def get_classes(): return {"opcoes": regras.get_classes_list()}
@app.get("/options/races/{name}")
def get_race_info(name: str): return regras.get_race_details(name)
@app.get("/options/classes/{name}")
def get_class_info(name: str): return regras.get_class_details(name)

@app.post("/create_character")
def create_character(char: CharacterCreationRequest, db: Session = Depends(get_db)):
    session_id = f"{char.nome.lower()}_{random.randint(1000,9999)}"
    
    # 1. Gera Prólogo Personalizado
    roteiro = gerar_prologo_missao(char)
    
    d_classe = regras.get_class_details(char.classe)
    d_raca = regras.get_race_details(char.raca)
    
    attr = {
        "forca": 15 + d_raca.get('bonus_atributos', {}).get('forca', 0),
        "destreza": 14 + d_raca.get('bonus_atributos', {}).get('destreza', 0),
        "constituicao": 13 + d_raca.get('bonus_atributos', {}).get('constituicao', 0),
        "inteligencia": 12, "sabedoria": 10, "carisma": 10
    }
    hp = d_classe.get('dado_vida', 8) + calcular_modificador(attr["constituicao"])
    
    novo = HeroModel(
        session_id=session_id, nome=char.nome, raca=char.raca, classe=char.classe,
        alinhamento=char.alinhamento, background=char.background, objetivo=char.objetivo,
        hp_atual=hp, hp_max=hp, atributos=attr,
        inventario=d_classe.get('equipamento_inicial', ["Mochila", "Tocha"]), # Garante inventário
        world_state={"local": roteiro["local_inicial"], "clima": roteiro["clima_inicial"], "turno": 1},
        combat_state={"ativo": False, "inimigos": []},
        quest_log={"nome_missao": roteiro["nome_missao"], "objetivo_missao": roteiro["objetivo_missao"]},
        historico_chat=[{"role": "assistant", "content": roteiro["intro_narrativa"]}]
    )
    db.add(novo); db.commit()
    return {"status": "Criado", "session_id": session_id}

@app.post("/load_game")
def load_game(req: LoadRequest, db: Session = Depends(get_db)):
    heroi = db.query(HeroModel).filter(HeroModel.session_id == req.session_id).first()
    if not heroi: raise HTTPException(status_code=404, detail="Save não encontrado")
    
    # Restaura o envio completo de dados para o Frontend
    return {
        "nome": heroi.nome, "raca": heroi.raca, "classe": heroi.classe,
        "hp_atual": heroi.hp_atual, "hp_max": heroi.hp_max,
        "inventory": heroi.inventario, 
        "atributos": heroi.atributos,
        "local": heroi.world_state.get("local"), 
        "combat_active": heroi.combat_state.get("ativo", False),
        "inimigos": heroi.combat_state.get("inimigos", []),
        "missao": heroi.quest_log
    }

@app.post("/chat")
async def chat_endpoint(user_input: UserAction, db: Session = Depends(get_db)):
    heroi = db.query(HeroModel).filter(HeroModel.session_id == user_input.session_id).first()
    if not heroi: return {"narrativa": "Erro...", "game_over": True}

    w_state = dict(heroi.world_state or {}); c_state = dict(heroi.combat_state or {})
    q_state = dict(heroi.quest_log or {})

    # Lógica simplificada de Chat e Combate (mantendo a funcionalidade)
    prompt = montar_contexto(heroi, w_state, c_state, q_state)
    hist = list(heroi.historico_chat)[-4:]
    msgs = [{"role": "system", "content": prompt}] + hist + [{"role": "user", "content": user_input.action}]
    
    try:
        resp = client.chat.completions.create(model=MODEL_NAME, messages=msgs, response_format={"type": "json_object"})
        dados = json.loads(resp.choices[0].message.content)
    except: dados = {"narrativa": "..."}
    
    narrativa = dados.get("narrativa", "")
    
    # Combate Básico
    if dados.get("spawn_battle") and not c_state.get("ativo"):
        c_state["ativo"] = True
        c_state["inimigos"] = [{"nome": "Inimigo", "hp": 10, "max_hp": 10, "ca": 10}]
        narrativa += "\n\n⚔️ Inimigos surgem!"

    # Salva
    novo_hist = list(heroi.historico_chat)
    novo_hist.append({"role": "user", "content": user_input.action})
    novo_hist.append({"role": "assistant", "content": narrativa})
    heroi.historico_chat = novo_hist
    heroi.combat_state = c_state
    db.commit()

    return {
        "narrativa": narrativa, "hp_atual": heroi.hp_atual, "hp_max": heroi.hp_max,
        "inventory": heroi.inventario, "atributos": heroi.atributos,
        "combat_active": c_state.get("ativo", False),
        "inimigos": c_state.get("inimigos", []),
        "missao": q_state
    }

# Para rodar com 'python api.py' se preferir:
import uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)