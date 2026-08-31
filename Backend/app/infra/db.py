from collections.abc import Generator
from datetime import UTC, datetime

from sqlalchemy import JSON, ForeignKey, create_engine, func
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, relationship, sessionmaker

from app.infra.settings import settings


class Base(DeclarativeBase):
    pass


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str | None] = mapped_column(unique=True, default=None)
    # Nenhum dos dois é obrigatório sozinho: uma conta pode ter só senha, só
    # Google, ou as duas (ver ADR-0014) — o que não pode é ter nenhuma.
    senha_hash: Mapped[str | None] = mapped_column(default=None)
    # `sub` do Google (identificador estável da conta, não muda se o e-mail
    # mudar) — é o que liga um login OAuth a um Usuario, não o e-mail cru.
    google_sub: Mapped[str | None] = mapped_column(unique=True, index=True, default=None)
    # Etapa 10 (A-2) — bloqueia jogar (não logar) até confirmar. Contas
    # Google entram com isto já `True` (o Google já verificou); convidado
    # não tem e-mail, então a checagem nem se aplica a ele.
    email_verificado: Mapped[bool] = mapped_column(default=False)
    criado_em: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))

    personagens: Mapped[list["Personagem"]] = relationship(back_populates="usuario")


class RegistroPendente(Base):
    """Espelho consultável do token de confirmação (services/auth.py) — o
    token continua sendo o que autentica o clique no link, mas sem nenhum
    registro no banco `/auth/login` não tinha como saber que um e-mail tem
    um cadastro esperando confirmação, e caía na mesma mensagem genérica de
    "e-mail ou senha incorretos" de um e-mail nunca usado. `usuario_id` é
    `None` num registro comum (`/auth/registrar`) e o id do convidado numa
    reivindicação (`/auth/reivindicar`) — mesma distinção que já existe
    dentro do token. Sem expiração ativa: uma linha mais velha que
    `TTL_TOKEN_CONFIRMACAO` (services/auth.py) é tratada como inexistente
    nas checagens, mas continua no banco (aceitável no volume do projeto)."""

    __tablename__ = "registros_pendentes"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(unique=True, index=True)
    senha_hash: Mapped[str]
    usuario_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"), default=None)
    criado_em: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


class Personagem(Base):
    __tablename__ = "personagens"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    # Identificador público usado na URL (/jogar/:sessionId) e no localStorage
    # do front — não é mais a chave primária (ver ADR-0005), mas continua
    # existindo para não quebrar o contrato com o Frontend.
    session_id: Mapped[str] = mapped_column(unique=True, index=True)
    criado_em: Mapped[datetime] = mapped_column(
        default=lambda: datetime.now(UTC), server_default=func.now()
    )
    # Etapa 8: "arquivar" em vez de apagar — a tela "Meus heróis" some com o
    # personagem sem destruir histórico/memória (evento_memoria continua
    # apontando pra ele).
    arquivado: Mapped[bool] = mapped_column(default=False, server_default="0")

    nome: Mapped[str]
    raca: Mapped[str]
    classe: Mapped[str]
    alinhamento: Mapped[str]
    background: Mapped[str]
    objetivo: Mapped[str]
    # Etapa 11 (B-3) — URL da imagem gerada na criação. O front monta o
    # prompt e a URL do pollinations.ai (precisa do nome pro seed, que só
    # existe no navegador); o servidor só guarda o resultado, não gera nada.
    imagem: Mapped[str | None] = mapped_column(default=None)
    # Etapa 11 (B-7, resolve P-4) — até aqui, o texto que o jogador escreve
    # na criação (`CharacterCreationRequest.historia_texto`) entrava no
    # prompt do prólogo (narrator.gerar_prologo_missao) e nunca era
    # gravado: existia por uma chamada ao modelo e depois sumia. Agora é a
    # fonte da tela de abertura, e o primeiro EventoMemoria do personagem.
    historia_texto: Mapped[str | None] = mapped_column(default=None)

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
    # Fase 3 da revisão de gameplay (Etapa 12/13, ADR-0027) — roster de
    # companheiros recrutados: [{"nome", "classe", "hp", "hp_max",
    # "lealdade", "inventario"}]. HP aqui é o que sobrevive entre combates e
    # sessões; o HP "de agora" durante uma luta vive em
    # `combat_state.aliados` (domain/state.py:Aliado) e é sincronizado de
    # volta pra cá a cada turno (services/tools.py:sincronizar_aliados) —
    # senão dano em combate "some" assim que o turno termina.
    aliados: Mapped[list] = mapped_column(JSON, default=list)
    # Fase 7 da revisão de gameplay (Etapa 12/13) — gerado uma vez por
    # `narrator.gerar_epitafio` quando `c_state.resultado == "morte"` se
    # confirma (routers/game.py), e nunca mais regenerado: regerar a cada
    # visita custaria dinheiro e daria uma memória diferente da mesma morte
    # a cada vez. `None` enquanto o herói está vivo.
    epitafio: Mapped[dict | None] = mapped_column(JSON, default=None)
    # Progressão (Etapa 7) — XP e nível, tabela SRD 5e (rules_engine.py:
    # XP_POR_NIVEL). `ToolExecutor._conceder_xp` é quem muta isso, nunca o
    # modelo diretamente (mesmo princípio de rules_engine.py como juiz).
    nivel: Mapped[int] = mapped_column(default=1, server_default="1")
    xp: Mapped[int] = mapped_column(default=0, server_default="0")

    # Pendências do remaster UX (PLANO_REMASTER_UX.md) — itens 3 e 4.
    # `monstros_derrotados`: nome do bestiário -> quantas vezes já morreu
    # pra este herói (`ToolExecutor._conceder_xp`, services/tools.py, é o
    # único lugar que escreve aqui — mesmo princípio de `inventario`/
    # `reputacao_npcs`: o ToolExecutor nunca toca o banco direto, só
    # reatribui a coluna). `morto_em`/`pontuacao_final` ficam `None`
    # enquanto o herói está vivo, preenchidos uma vez em
    # `_persistir_epitafio_se_confirmado` (routers/game.py) no mesmo
    # commit que confirma a morte — mesmo padrão do `epitafio` acima.
    monstros_derrotados: Mapped[dict] = mapped_column(JSON, default=dict)
    morto_em: Mapped[datetime | None] = mapped_column(default=None)
    pontuacao_final: Mapped[int | None] = mapped_column(default=None)

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


class EventoTelemetria(Base):
    """Telemetria de produto (Etapa 9) — granularidade mínima: um evento por
    fato, sem dashboard nenhum embutido aqui. Sessões criadas, turnos por
    sessão, retenção D1/D7 e ponto de abandono são consulta sobre esta
    tabela (ver `scripts/telemetria_resumo.py`), não uma feature de runtime.
    `personagem_id` é `None` só em eventos que não têm um personagem
    associado (nenhum hoje, mas o tipo já vem opcional para não fechar essa
    porta)."""

    __tablename__ = "eventos_telemetria"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"), index=True)
    personagem_id: Mapped[int | None] = mapped_column(ForeignKey("personagens.id"), index=True, default=None)
    # "sessao_criada" | "turno" | "personagem_arquivado" — string solta em
    # vez de enum: mesma escolha de EventoMemoria.tipo acima, um tipo novo
    # não deve exigir migration.
    tipo: Mapped[str]
    criado_em: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC), index=True)


class FeedbackNarracao(Base):
    """👍/👎 por narração (Etapa 9) — sinal humano para validar o
    LLM-as-a-judge (ADR-0011) e dataset de preferência próprio.
    `historico_chat` é uma coluna JSON de lista (`Personagem.historico_chat`),
    não uma tabela por mensagem — o vínculo com a narração é por índice
    nessa lista, não por FK de linha."""

    __tablename__ = "feedback_narracoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    personagem_id: Mapped[int] = mapped_column(ForeignKey("personagens.id"), index=True)
    turno_index: Mapped[int]
    valor: Mapped[int]  # +1 ou -1
    # Etapa 10 (A-4) — só o 👎 oferece o campo, mas a coluna serve os dois;
    # nenhum jogador digita nada na maioria dos votos, por isso opcional.
    comentario: Mapped[str | None] = mapped_column(default=None)
    criado_em: Mapped[datetime] = mapped_column(default=lambda: datetime.now(UTC))


_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}
engine = create_engine(settings.database_url, connect_args=_connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Generator[Session]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
