import os
import json
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from groq import Groq
from sqlalchemy.orm import Session

# Importa nossos módulos
from data_manager import regras
from database import HeroModel, get_db, criar_banco

# --- CONFIGURAÇÃO ---
load_dotenv()
criar_banco() # Garante que o arquivo .db existe

MINHA_CHAVE = os.getenv("GROQ_API_KEY")
if not MINHA_CHAVE:
    raise ValueError("❌ Configure o GROQ_API_KEY no .env")

client = Groq(api_key=MINHA_CHAVE)
MODEL_NAME = "llama-3.3-70b-versatile"

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- DADOS ---
class CharacterCreationRequest(BaseModel):
    nome: str
    raca: str
    classe: str
    historia: str = ""

class UserAction(BaseModel):
    session_id: str
    action: str

# --- ENDPOINTS DE OPÇÕES (MENU) ---

@app.get("/options/races")
def get_races():
    """Retorna a lista de nomes das raças"""
    return {"opcoes": regras.get_races_list()}

@app.get("/options/races/{name}")
def get_race_info(name: str):
    """Retorna os detalhes (lore, atributos) de uma raça específica"""
    info = regras.get_race_details(name)
    if not info:
        raise HTTPException(status_code=404, detail="Raça não encontrada")
    return info

@app.get("/options/classes")
def get_classes():
    """Retorna a lista de nomes das classes"""
    return {"opcoes": regras.get_classes_list()}

@app.get("/options/classes/{name}")
def get_class_info(name: str):
    """Retorna os detalhes (lore, hp) de uma classe específica"""
    info = regras.get_class_details(name)
    if not info:
        raise HTTPException(status_code=404, detail="Classe não encontrada")
    return info

# --- ENDPOINTS DO JOGO ---

@app.post("/create_character")
def create_character(char: CharacterCreationRequest, db: Session = Depends(get_db)):
    session_id = "sessao_demo_1" 
    
    # 1. Verifica se já existe save e deleta (reset)
    heroi_antigo = db.query(HeroModel).filter(HeroModel.session_id == session_id).first()
    if heroi_antigo:
        db.delete(heroi_antigo)
        db.commit()

    # 2. Pega status base da classe
    dados_classe = regras.get_class_details(char.classe)
    hp_inicial = dados_classe.get('dado_vida', 10) + 2
    inv_inicial = dados_classe.get('equipamento_inicial', [])

    # 3. O "Cérebro" do Mestre (System Prompt)
    system_prompt = f"""
    Você é um Mestre de RPG D&D 5e Sombrio.
    O Jogador é: {char.nome} ({char.raca} {char.classe}).
    
    REGRAS DE RESPOSTA (IMPORTANTE):
    1. Você DEVE responder APENAS no formato JSON.
    2. Não escreva nada fora do JSON.
    3. Use o campo 'narrativa' para descrever a história.
    
    FORMATO JSON ESPERADO:
    {{
        "narrativa": "A descrição da cena...",
        "dano_recebido": 0,
        "novo_item": null,
        "hp_atual": {hp_inicial},
        "game_over": false
    }}
    """

    # 4. Cria a ficha no Banco
    novo_heroi = HeroModel(
        session_id=session_id,
        nome=char.nome,
        raca=char.raca,
        classe=char.classe,
        hp_atual=hp_inicial,
        hp_max=hp_inicial,
        forca=10, destreza=10, inteligencia=10,
        inventario=inv_inicial,
        historico_chat=[{"role": "system", "content": system_prompt}] 
    )
    
    db.add(novo_heroi)
    db.commit()
    
    return {"status": "Personagem Salvo!", "session_id": session_id}

@app.post("/chat")
async def chat_endpoint(user_input: UserAction, db: Session = Depends(get_db)):
    # 1. Carrega o herói do Banco
    heroi = db.query(HeroModel).filter(HeroModel.session_id == user_input.session_id).first()
    
    if not heroi:
        return {"narrativa": "Personagem não encontrado. Crie um novo!", "game_over": True}

    # 2. Recupera histórico
    historico = list(heroi.historico_chat) 
    
    # 3. Adiciona ação do usuário
    prompt_usuario = f"[{heroi.nome} ({heroi.classe}) | HP: {heroi.hp_atual}/{heroi.hp_max}] Ação: {user_input.action}"
    historico.append({"role": "user", "content": prompt_usuario})

    try:
        # 4. Chama a IA
        completion = client.chat.completions.create(
            model=MODEL_NAME,
            messages=historico,
            temperature=0.7,
            response_format={"type": "json_object"} 
        )
        
        resp_text = completion.choices[0].message.content
        historico.append({"role": "assistant", "content": resp_text})
        
        # 5. Processa JSON da IA
        dados = json.loads(resp_text) 
        
        # 6. Atualiza o Banco
        dano = dados.get("dano_recebido", 0)
        if dano > 0:
            heroi.hp_atual -= dano
        
        item_novo = dados.get("novo_item")
        if item_novo:
            novo_inv = list(heroi.inventario)
            novo_inv.append(item_novo)
            heroi.inventario = novo_inv

        heroi.historico_chat = historico 
        db.commit() 

        return {
            "narrativa": dados.get("narrativa", "Algo aconteceu..."),
            "hp_atual": heroi.hp_atual,
            "inventory": heroi.inventario,
            "game_over": heroi.hp_atual <= 0
        }

    except Exception as e:
        print(f"Erro: {e}")
        return {"narrativa": "A conexão falhou.", "hp_atual": heroi.hp_atual}