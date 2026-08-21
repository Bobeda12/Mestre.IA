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
    # Nenhum JSON de classe/raça define ouro inicial (Etapa 4) — 10 é um
    # ponto de partida arbitrário, pequeno o bastante para a ferramenta
    # `gastar_ouro` já nascer com um limite real para testar.
    ouro: Mapped[int] = mapped_column(default=10, server_default="10")

    atributos: Mapped[dict] = mapped_column(JSON)
    inventario: Mapped[list] = mapped_column(JSON, default=list)
    quest_log: Mapped[dict] = mapped_column(JSON, default=dict)
    world_state: Mapped[dict] = mapped_column(JSON, default=dict)
    combat_state: Mapped[dict] = mapped_column(JSON, default=dict)
    historico_chat: Mapped[list] = mapped_column(JSON, default=list)

    # Etapa 5 (memória): sumário estruturado de médio prazo — ver
    # domain/memoria.py:ResumoRolante e services/memory.py. `turno_resumido_ate`
    # é o índice de `historico_chat` já processado, para o resumo rolante
    # nunca reprocessar a mesma fatia de mensagens duas vezes.
    resumo_rolante: Mapped[dict] = mapped_column(JSON, default=dict)
    turno_resumido_ate: Mapped[int] = mapped_column(default=0, server_default="0")
    # NPC -> reputação (-100..100). Mesmo padrão de `inventario`: o
    # ToolExecutor nunca toca o banco diretamente, só reatribui esta coluna
    # (ver services/tools.py:ajustar_reputacao_npc e Lição 03).
    reputacao_npcs: Mapped[dict] = mapped_column(JSON, default=dict)
    # Progressão (Etapa 7) — XP e nível, tabela SRD 5e (rules_engine.py:
    # XP_POR_NIVEL). `ToolExecutor._conceder_xp` é quem muta isso, nunca o
    # modelo diretamente (mesmo princípio de rules_engine.py como juiz).
    nivel: Mapped[int] = mapped_column(default=1, server_default="1")
    xp: Mapped[int] = mapped_column(default=0, server_default="0")

    usuario: Mapped["Usuario"] = relationship(back_populates="personagens")
    eventos_memoria: Mapped[list["EventoMemoria"]] = relationship(back_populates="personagem")


class EventoMemoria(Base):
    """Memória de longo prazo (Etapa 5) — um registro por evento
    significativo do jogo, recuperável por busca híbrida
    (services/hybrid_search.py) filtrada sempre por `personagem_id`, para
    nunca vazar memória entre personagens/sessões diferentes."""

    __tablename__ = "eventos_memoria"

    id: Mapped[int] = mapped_column(primary_key=True)
    personagem_id: Mapped[int] = mapped_column(ForeignKey("personagens.id"), index=True)
    turno: Mapped[int]
    tipo: Mapped[str]
    texto: Mapped[str]
    personagens_citados: Mapped[list] = mapped_column(JSON, default=list)
    embedding: Mapped[list] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    personagem: Mapped["Personagem"] = relationship(back_populates="eventos_memoria")


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
