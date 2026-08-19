from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, create_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.infra.settings import settings

# Único usuário local, criado no startup (ver garantir_usuario_local). A
# autenticação de verdade chega na Etapa 8 — até lá, todo personagem
# pertence a este id. Ver ADR-0005.
USUARIO_LOCAL_ID = 1


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(unique=True, default=None)
    criado_em: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    personagens: Mapped[list["Personagem"]] = relationship(back_populates="usuario")


class Personagem(Base):
    __tablename__ = "personagens"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    # Identificador público usado na URL (/jogar/:sessionId) e no localStorage
    # do front — não é mais a chave primária (ver ADR-0005), mas continua
    # existindo para não quebrar o contrato com o Frontend.
    session_id: Mapped[str] = mapped_column(unique=True, index=True)

    nome: Mapped[str]
    raca: Mapped[str]
    classe: Mapped[str]
    alinhamento: Mapped[str]
    background: Mapped[str]
    objetivo: Mapped[str]

    hp_atual: Mapped[int]
    hp_max: Mapped[int]
    defesa: Mapped[int]

    atributos: Mapped[dict] = mapped_column(JSON)
    inventario: Mapped[list] = mapped_column(JSON, default=list)
    quest_log: Mapped[dict] = mapped_column(JSON, default=dict)
    world_state: Mapped[dict] = mapped_column(JSON, default=dict)
    combat_state: Mapped[dict] = mapped_column(JSON, default=dict)
    historico_chat: Mapped[list] = mapped_column(JSON, default=list)

    usuario: Mapped["Usuario"] = relationship(back_populates="personagens")


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def garantir_usuario_local(db: Session) -> None:
    if db.get(Usuario, USUARIO_LOCAL_ID) is None:
        db.add(Usuario(id=USUARIO_LOCAL_ID))
        db.commit()
