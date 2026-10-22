import os
import requests
import unicodedata
import time

# --- CONFIGURAÇÃO ---
BASE_DIR = os.path.join("Frontend", "public", "assets")
RACES_DIR = os.path.join(BASE_DIR, "races")
CLASSES_DIR = os.path.join(BASE_DIR, "classes")

# Função para normalizar nomes (Anão -> anao)
def normalizar_nome(texto):
    nfkd = unicodedata.normalize('NFKD', texto)
    return "".join([c for c in nfkd if not unicodedata.combining(c)]).lower().replace(" ", "-")

# Função de Download com Paciência (Retry + Timeout Longo)
def baixar_imagem(url, pasta, nome_arquivo):
    if not os.path.exists(pasta):
        os.makedirs(pasta)
    
    caminho_completo = os.path.join(pasta, nome_arquivo + ".jpg")
    
    # Se a imagem já existe, pula (para você não esperar à toa se rodar de novo)
    if os.path.exists(caminho_completo):
        print(f"⏩ {nome_arquivo} já existe. Pulando...")
        return

    max_tentativas = 3
    for tentativa in range(1, max_tentativas + 1):
        print(f"⬇️  Baixando {nome_arquivo}... (Tentativa {tentativa}/{max_tentativas})")
        
        try:
            # AQUI ESTÁ A MÁGICA: timeout=60 segundos!
            response = requests.get(url, timeout=60) 
            
            if response.status_code == 200:
                with open(caminho_completo, 'wb') as f:
                    f.write(response.content)
                print(f"✅ Sucesso: {nome_arquivo}")
                return # Sai da função se deu certo
            else:
                print(f"⚠️  Erro {response.status_code}. O servidor rejeitou.")
        
        except Exception as e:
            print(f"⏳ Demorou demais ou falhou. Tentando de novo em 3s...")
        
        time.sleep(3) # Respira antes de tentar de novo

    print(f"❌ Desisto de baixar {nome_arquivo} após {max_tentativas} tentativas.")

# --- LISTAS DE IMAGENS ---
races = {
    "Anão": "dwarf warrior beard&seed=201",
    "Elfo": "elf archer elegant&seed=202",
    "Humano": "human hero sword&seed=203",
    "Halfling": "hobbit peaceful&seed=204",
    "Draconato": "dragonborn breath&seed=205",
    "Tiefling": "tiefling horns fire&seed=206",
    "Meio-Orc": "orc warrior fierce&seed=207",
    "Gnomo": "gnome inventor&seed=208",
    "Meio-Elfo": "half-elf adventurer&seed=209"
}

classes = {
    "Bárbaro": "barbarian fury&seed=101",
    "Bardo": "bard musician tavern&seed=102",
    "Clérigo": "cleric holy light&seed=103",
    "Druida": "druid nature forest&seed=104",
    "Guerreiro": "knight armor sword&seed=105",
    "Monge": "monk martial arts&seed=106",
    "Paladino": "paladin shining armor&seed=107",
    "Patrulheiro": "ranger hooded bow&seed=108",
    "Ladino": "rogue shadow dagger&seed=109",
    "Feiticeiro": "sorcerer fire magic&seed=110",
    "Bruxo": "warlock dark magic&seed=111",
    "Mago": "wizard library spell&seed=112"
}

# --- EXECUÇÃO ---
print("--- INICIANDO DOWNLOAD (MODO PACIENTE) ---")

print("\n[1/2] Baixando Raças...")
for nome, prompt in races.items():
    url = f"https://image.pollinations.ai/prompt/fantasy%20rpg%20dnd%20{prompt}%20character%20portrait%20cinematic%20lighting%20highly%20detailed?width=600&height=800&nologo=true"
    baixar_imagem(url, RACES_DIR, normalizar_nome(nome))

print("\n[2/2] Baixando Classes...")
for nome, prompt in classes.items():
    url = f"https://image.pollinations.ai/prompt/fantasy%20rpg%20dnd%20{prompt}%20character%20portrait%20cinematic%20lighting%20highly%20detailed?width=600&height=800&nologo=true"
    baixar_imagem(url, CLASSES_DIR, normalizar_nome(nome))

print("\n✨ TUDO PRONTO! Pode abrir o site.")