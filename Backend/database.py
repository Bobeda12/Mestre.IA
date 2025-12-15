from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. Conexão com o Arquivo (O "Save Game")
DATABASE_URL = "sqlite:///./rpg_save.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# 2. A Tabela de Personagem (Ficha)
class HeroModel(Base):
    __tablename__ = "herois"

    session_id = Column(String, primary_key=True, index=True) # A "Identidade" do save
    nome = Column(String)
    raca = Column(String)
    classe = Column(String)
    hp_atual = Column(Integer)
    hp_max = Column(Integer)
    
    # Atributos
    forca = Column(Integer)
    destreza = Column(Integer)
    inteligencia = Column(Integer)
    
    # Inventário e Histórico (Salvos como texto JSON)
    inventario = Column(JSON) 
    historico_chat = Column(JSON) # Salva o papo com a IA

# 3. Cria o arquivo do banco se não existir
def criar_banco():
    Base.metadata.create_all(bind=engine)

# 4. Ferramenta para abrir/fechar conexão
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()