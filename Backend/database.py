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

    # Status Vitais
    hp_atual = Column(Integer)
    hp_max = Column(Integer)
    nivel = Column(Integer, default=1)
    xp = Column(Integer, default=0)

    # Atributos (AGORA É UM JSON)
    # Guarda: {"forca": 10, "destreza": 12, "inteligencia": 8...}
    atributos = Column(JSON)

    # Estados do Mundo (JSONs para flexibilidade)
    inventario = Column(JSON, default=[])
    world_state = Column(JSON, default={})    # Guarda: Clima, Hora, Local
    combat_state = Column(JSON, default={})   # Guarda: Inimigos vivos, Turno

    historico_chat = Column(JSON)

def criar_banco():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
