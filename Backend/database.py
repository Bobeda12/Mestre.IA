from sqlalchemy import create_engine, Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = "sqlite:///./rpg_save.db"

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

class HeroModel(Base):
    __tablename__ = "herois"

    session_id = Column(String, primary_key=True, index=True)
    nome = Column(String)
    raca = Column(String)
    classe = Column(String)

    # --- NOVO: Profundidade Narrativa ---
    alinhamento = Column(String) # Ex: Caótico Bom
    background = Column(String)  # Ex: Soldado, Eremita
    objetivo = Column(String)    # Ex: Vingar o pai, Ficar rico

    hp_atual = Column(Integer)
    hp_max = Column(Integer)
    defesa = Column(Integer)

    atributos = Column(JSON)
    inventario = Column(JSON, default=[])

    # --- NOVO: O "Diretor" da Sessão ---
    # Guarda: { "titulo_missao": "...", "objetivo_atual": "...", "npc_chave": "..." }
    quest_log = Column(JSON, default={})

    world_state = Column(JSON, default={})
    combat_state = Column(JSON, default={})
    historico_chat = Column(JSON)

def criar_banco():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
