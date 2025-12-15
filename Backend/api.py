import os
import json
import random
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from sqlalchemy.orm import Session

from data_manager import regras
from database import HeroModel, get_db, criar_banco

load_dotenv()
# Tenta recriar o banco se ele não existir
criar_banco()

MINHA_CHAVE = os.getenv("GROQ_API_KEY")
client = Groq(api_key=MINHA_CHAVE) if MINHA_CHAVE else None
MODEL_NAME = "llama-3.3-70b-versatile"

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# --- MODELS ---
class CharacterCreationRequest(BaseModel):
    nome: str; raca: str; classe: str; historia: str = ""

class UserAction(BaseModel):
    session_id: str; action: str

class LoadRequest(BaseModel):
    session_id: str

# --- LÓGICA DE JOGO ---
def calcular_modificador(valor): 
    return (valor - 10) // 2

# --- CORREÇÃO AQUI: INSTRUÇÃO DE FORMATO EXPLÍCITA ---
def montar_contexto_mestre(heroi, estado_mundo):
    # Recupera atributos do JSON
    attrs = heroi.atributos if heroi.atributos else {"forca": 10, "destreza": 10}
    
    mod_for = calcular_modificador(attrs.get("forca", 10))
    mod_des = calcular_modificador(attrs.get("destreza", 10))
    
    biblia = regras.get_biblia()
    # Pega o bestiário para a IA saber os status dos inimigos
    bestiario_json = json.dumps(regras.monsters, ensure_ascii=False)
    
    return f"""
    {biblia}
    
    [ESTADO DO MUNDO]
    Local: {estado_mundo.get('local')} | Horário: {estado_mundo.get('horario')} | Clima: {estado_mundo.get('clima')}
    
    [JOGADOR ATUAL]
    Nome: {heroi.nome} ({heroi.raca} {heroi.classe})
    HP: {heroi.hp_atual}/{heroi.hp_max}
    Atributos: FOR {attrs.get('forca')} ({mod_for:+}) | DES {attrs.get('destreza')} ({mod_des:+})
    Inventário: {heroi.inventario}
    
    [DADOS DE REGRAS (Bestiário)]
    {bestiario_json}

    [INSTRUÇÃO DE RESPOSTA OBRIGATÓRIA]
    Você DEVE responder APENAS um objeto JSON válido.
    Não escreva nenhum texto fora do JSON.
    O formato deve ser exatamente este:
    {{
        "narrativa": "Sua descrição da cena e do resultado das ações aqui...",
        "dano_recebido": 0,
        "novo_item": null,
        "hp_atual": {heroi.hp_atual},
        "iniciar_combate": false,
        "novos_inimigos": []
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
    # Gera ID único para o save
    session_id = f"{char.nome.lower()}_{random.randint(1000,9999)}"
    
    # 1. Pega dados base
    d_classe = regras.get_class_details(char.classe)
    d_raca = regras.get_race_details(char.raca)
    
    # 2. Calcula Atributos
    # Aqui está a correção: Criamos um dicionário, não variáveis soltas
    atributos_finais = {
        "forca": 15 + d_raca.get('bonus_atributos', {}).get('forca', 0),
        "destreza": 14 + d_raca.get('bonus_atributos', {}).get('destreza', 0),
        "constituicao": 13 + d_raca.get('bonus_atributos', {}).get('constituicao', 0),
        "inteligencia": 12 + d_raca.get('bonus_atributos', {}).get('inteligencia', 0),
        "sabedoria": 10,
        "carisma": 10
    }
    
    mod_con = calcular_modificador(atributos_finais["constituicao"])
    hp_inicial = d_classe.get('dado_vida', 8) + mod_con
    
    # 3. Define Estados Iniciais
    world_state = {"local": "Estrada Real", "clima": "Céu Limpo", "turno": 1}
    combat_state = {"ativo": False, "inimigos": []}
    inventario = d_classe.get('equipamento_inicial', ["Adaga", "Rações"])

    intro_prompt = f"O jogo começou. O herói {char.nome} está em {world_state['local']}. Descreva o cenário."

    # 4. Salva no Banco (Usando o campo 'atributos' corretamente)
    novo_heroi = HeroModel(
        session_id=session_id,
        nome=char.nome, 
        raca=char.raca, 
        classe=char.classe,
        hp_atual=hp_inicial, 
        hp_max=hp_inicial,
        atributos=atributos_finais, # CORREÇÃO: Passando o dicionário inteiro
        inventario=inventario,
        world_state=world_state,
        combat_state=combat_state,
        historico_chat=[{"role": "system", "content": intro_prompt}]
    )
    
    db.add(novo_heroi)
    db.commit()
    
    return {"status": "Criado", "session_id": session_id}

@app.post("/load_game")
def load_game(req: LoadRequest, db: Session = Depends(get_db)):
    heroi = db.query(HeroModel).filter(HeroModel.session_id == req.session_id).first()
    if not heroi: raise HTTPException(status_code=404, detail="Save não encontrado")
    
    return {
        "nome": heroi.nome, "raca": heroi.raca, "classe": heroi.classe,
        "hp_atual": heroi.hp_atual, "hp_max": heroi.hp_max,
        "inventario": heroi.inventario,
        "local": heroi.world_state.get("local", "Desconhecido")
    }

@app.post("/chat")
async def chat_endpoint(user_input: UserAction, db: Session = Depends(get_db)):
    heroi = db.query(HeroModel).filter(HeroModel.session_id == user_input.session_id).first()
    if not heroi: return {"narrativa": "Erro: Sessão perdida.", "game_over": True}

    # Atualiza turno
    w_state = dict(heroi.world_state or {})
    w_state["turno"] = w_state.get("turno", 0) + 1
    heroi.world_state = w_state

    # Prompt
    prompt_sistema = montar_contexto_mestre(heroi)
    
    historico = list(heroi.historico_chat)
    msgs = [{"role": "system", "content": prompt_sistema}] + historico[-5:] + [{"role": "user", "content": user_input.action}]

    try:
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=msgs,
            temperature=0.6,
            response_format={"type": "json_object"}
        )
        
        resp_text = completion.choices[0].message.content
        try:
            dados = json.loads(resp_text)
        except:
            # Fallback se a IA não mandar JSON
            dados = {"narrativa": resp_text, "dano_recebido": 0}

        if dados.get("dano_recebido", 0) > 0:
            heroi.hp_atual -= dados["dano_recebido"]
        
        # Salva histórico
        historico.append({"role": "user", "content": user_input.action})
        historico.append({"role": "assistant", "content": dados.get("narrativa", "...")})
        heroi.historico_chat = historico
        db.commit()

        return {
            "narrativa": dados.get("narrativa"),
            "hp_atual": heroi.hp_atual,
            "hp_max": heroi.hp_max,
            "inventory": heroi.inventario
        }

    except Exception as e:
        print(f"Erro: {e}")
        return {"narrativa": "Erro na IA.", "hp_atual": heroi.hp_atual}