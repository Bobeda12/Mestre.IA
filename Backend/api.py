import os
import json
import random
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel, field_validator
from fastapi.middleware.cors import CORSMiddleware
import groq
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

# --- REGRAS DE POINT-BUY (D&D 5e) ---
# Tabela oficial de custo por valor final de atributo (antes de bônus racial).
ATRIBUTOS_VALIDOS = {"forca", "destreza", "constituicao", "inteligencia", "sabedoria", "carisma"}
CUSTO_PONTOS = {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}
PONTOS_DISPONIVEIS = 27

# --- MODELS ---
class CharacterCreationRequest(BaseModel):
    nome: str; raca: str; classe: str
    alinhamento: str; background: str; objetivo: str; historia_texto: str = ""
    # O cliente PROPÕE estes valores; o servidor sempre revalida (ver create_character).
    atributos: dict[str, int]
    atributos_livre: list[str] = []

    @field_validator("atributos")
    @classmethod
    def valida_point_buy(cls, valores: dict[str, int]) -> dict[str, int]:
        if set(valores.keys()) != ATRIBUTOS_VALIDOS:
            raise ValueError(f"atributos precisa ter exatamente as chaves {sorted(ATRIBUTOS_VALIDOS)}")
        custo_total = 0
        for attr, valor in valores.items():
            if valor not in CUSTO_PONTOS:
                raise ValueError(f"{attr}={valor} está fora do intervalo de point-buy (8 a 15)")
            custo_total += CUSTO_PONTOS[valor]
        if custo_total > PONTOS_DISPONIVEIS:
            raise ValueError(f"point-buy gastaria {custo_total} pontos; o limite é {PONTOS_DISPONIVEIS}")
        return valores

    @field_validator("atributos_livre")
    @classmethod
    def valida_atributos_livre(cls, valores: list[str]) -> list[str]:
        if len(valores) != len(set(valores)):
            raise ValueError("atributos_livre não pode repetir o mesmo atributo")
        for attr in valores:
            if attr not in ATRIBUTOS_VALIDOS:
                raise ValueError(f"'{attr}' não é um atributo válido")
        return valores

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

class ErroMestre(Exception):
    """Erro ao consultar a IA, com uma mensagem já pronta para o jogador ler."""
    def __init__(self, mensagem: str):
        self.mensagem = mensagem
        super().__init__(mensagem)

def chamar_mestre(msgs: list[dict]) -> dict:
    """Chama o LLM e devolve o JSON já decodificado, ou levanta ErroMestre
    com uma mensagem específica para cada tipo de falha (nunca engole o erro em silêncio)."""
    if not client:
        raise ErroMestre("O mestre está sem acesso à IA — falta configurar a chave da Groq no servidor (GROQ_API_KEY).")
    try:
        resp = client.chat.completions.create(model=MODEL_NAME, messages=msgs, response_format={"type": "json_object"})
    except groq.RateLimitError:
        raise ErroMestre("A cota de uso da IA acabou por agora. Espere um pouco e tente de novo.")
    except groq.APITimeoutError:
        raise ErroMestre("O mestre demorou demais para responder. Tente enviar a ação de novo.")
    except groq.APIConnectionError:
        raise ErroMestre("Não foi possível conectar ao serviço de IA. Verifique sua internet.")
    except groq.APIStatusError as e:
        raise ErroMestre(f"O serviço de IA recusou o pedido (código {e.status_code}).")

    try:
        return json.loads(resp.choices[0].message.content)
    except (json.JSONDecodeError, AttributeError):
        raise ErroMestre("O mestre respondeu num formato que não consegui entender.")

# --- AGENTE ROTEIRISTA (Restaura o início com história) ---
def gerar_prologo_missao(char):
    if not client: 
        return {
            "local_inicial": "Estrada Real", "clima_inicial": "Nublado", 
            "nome_missao": "Jornada Inicial", "objetivo_missao": "Chegar à cidade.",
            "intro_narrativa": f"{char.nome} inicia sua jornada na estrada."
        }

    historia_extra = f"\n    História contada pelo próprio jogador: {char.historia_texto}" if char.historia_texto.strip() else ""

    prompt = f"""
    Crie um prólogo de RPG Dark Fantasy para:
    Nome: {char.nome} ({char.raca} {char.classe})
    Passado: {char.background} | Objetivo: {char.objetivo} | Alinhamento: {char.alinhamento}{historia_extra}

    O prólogo deve começar 'in media res' (já na ação), conectado ao passado dele{" e à história que ele contou" if historia_extra else ""}.
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
        return chamar_mestre([{"role": "user", "content": prompt}])
    except ErroMestre as e:
        print("ERRO NO PRÓLOGO:", e.mensagem)
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
    d_classe = regras.get_class_details(char.classe)
    d_raca = regras.get_race_details(char.raca)
    if not d_classe:
        raise HTTPException(status_code=400, detail=f"Classe '{char.classe}' não existe.")
    if not d_raca:
        raise HTTPException(status_code=400, detail=f"Raça '{char.raca}' não existe.")

    # O front PROPÕE atributos e pontos livres; aqui é onde o servidor DECIDE.
    # (dá para burlar o front direto pela API — é exatamente por isso que a
    # regra vive aqui, e não só na interface. Ver ADR-0002.)
    bonus_racial = d_raca.get("bonus_atributos", {})
    pontos_livres_da_raca = bonus_racial.get("livre_escolha", 0)

    if len(char.atributos_livre) != pontos_livres_da_raca:
        raise HTTPException(
            status_code=400,
            detail=f"{char.raca} concede {pontos_livres_da_raca} ponto(s) de atributo livre; o pedido trouxe {len(char.atributos_livre)}.",
        )
    for attr in char.atributos_livre:
        if bonus_racial.get(attr, 0) > 0:
            raise HTTPException(
                status_code=400,
                detail=f"'{attr}' já recebe bônus fixo de {char.raca}; o ponto livre precisa ir para outro atributo.",
            )

    attr_final = {
        attr: valor + bonus_racial.get(attr, 0) + (1 if attr in char.atributos_livre else 0)
        for attr, valor in char.atributos.items()
    }

    hp = d_classe.get('dado_vida', 8) + calcular_modificador(attr_final["constituicao"])
    defesa = 10 + calcular_modificador(attr_final["destreza"])

    session_id = f"{char.nome.lower()}_{random.randint(1000,9999)}"
    roteiro = gerar_prologo_missao(char)

    novo = HeroModel(
        session_id=session_id, nome=char.nome, raca=char.raca, classe=char.classe,
        alinhamento=char.alinhamento, background=char.background, objetivo=char.objetivo,
        hp_atual=hp, hp_max=hp, defesa=defesa, atributos=attr_final,
        inventario=d_classe.get('equipamento_inicial', ["Mochila", "Tocha"]), # Garante inventário
        world_state={"local": roteiro["local_inicial"], "clima": roteiro["clima_inicial"], "turno": 1},
        combat_state={"ativo": False, "inimigos": []},
        quest_log={"nome_missao": roteiro["nome_missao"], "objetivo_missao": roteiro["objetivo_missao"]},
        historico_chat=[{"role": "assistant", "content": roteiro["intro_narrativa"]}]
    )
    db.add(novo); db.commit()
    return {"status": "Criado", "session_id": session_id, "hp_max": hp, "defesa": defesa}

@app.post("/load_game")
def load_game(req: LoadRequest, db: Session = Depends(get_db)):
    heroi = db.query(HeroModel).filter(HeroModel.session_id == req.session_id).first()
    if not heroi: raise HTTPException(status_code=404, detail="Save não encontrado")
    
    # Restaura o envio completo de dados para o Frontend
    return {
        "nome": heroi.nome, "raca": heroi.raca, "classe": heroi.classe,
        "hp_atual": heroi.hp_atual, "hp_max": heroi.hp_max, "defesa": heroi.defesa,
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
    if not heroi:
        raise HTTPException(status_code=404, detail="Sessão não encontrada.")

    w_state = dict(heroi.world_state or {}); c_state = dict(heroi.combat_state or {})
    q_state = dict(heroi.quest_log or {})

    # Lógica simplificada de Chat e Combate (mantendo a funcionalidade)
    prompt = montar_contexto(heroi, w_state, c_state, q_state)
    hist = list(heroi.historico_chat)[-4:]
    msgs = [{"role": "system", "content": prompt}] + hist + [{"role": "user", "content": user_input.action}]

    try:
        dados = chamar_mestre(msgs)
    except ErroMestre as e:
        return {
            "narrativa": f"*({e.mensagem})*", "erro": True,
            "hp_atual": heroi.hp_atual, "hp_max": heroi.hp_max, "defesa": heroi.defesa,
            "inventory": heroi.inventario, "atributos": heroi.atributos,
            "combat_active": c_state.get("ativo", False), "inimigos": c_state.get("inimigos", []),
            "missao": q_state,
        }

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
        "narrativa": narrativa, "hp_atual": heroi.hp_atual, "hp_max": heroi.hp_max, "defesa": heroi.defesa,
        "inventory": heroi.inventario, "atributos": heroi.atributos,
        "combat_active": c_state.get("ativo", False),
        "inimigos": c_state.get("inimigos", []),
        "missao": q_state
    }

# Para rodar com 'python api.py' se preferir:
import uvicorn
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)