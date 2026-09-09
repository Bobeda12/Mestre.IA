"""Estado por campanha: a ficção proposta pelo mestre torna-se realidade verificável."""

from typing import Literal

from pydantic import BaseModel, Field

Id = str


# Destino-sentinela de uma saída que não prende o herói a lugar nenhum:
# `mover` aceita qualquer local conhecido por ela (ver tools.mover).
SAIDA_LIVRE = "Estrada livre"

class EntidadeCena(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")
    nome: str = Field(min_length=1, max_length=100)
    descricao: str = Field(default="", max_length=800)
    tipo: Literal["objeto", "saida", "obstaculo", "animal"] = "objeto"
    propriedades: list[
        Literal[
            "movel",
            "pesado",
            "fragil",
            "inflamavel",
            "trancado",
            "mecanismo",
            "cobertura",
            "investigavel",
            "coletavel",
        ]
    ] = Field(default_factory=list, max_length=8)
    destino: str = Field(default="", max_length=100)  # vazio ou SAIDA_LIVRE = qualquer local conhecido
    pista: str = Field(default="", max_length=600)
    estado: Literal["intacto", "aberto", "bloqueado", "destruido", "movido", "aceso", "apagado"] = "intacto"
    descoberto: bool = False
    bloqueado_por: str | None = None
    recolhido: bool = False


class CenaPersistente(BaseModel):
    descricao: str = Field(default="", max_length=1200)
    entidades: dict[str, EntidadeCena] = Field(default_factory=dict)
    visitas: int = 0


class Conhecimento(BaseModel):
    texto: str = Field(min_length=1, max_length=600)
    natureza: Literal["fato", "suspeita", "boato", "promessa"]
    fonte: str = Field(min_length=1, max_length=100)
    turno: int = 1
    publico: bool = True


class PessoaMundo(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")
    nome: str = Field(min_length=1, max_length=100)
    local: str = Field(min_length=1, max_length=100)
    raca: str = Field(default="Humano", max_length=40, description="Raça do catálogo do jogo (Humano, Elfo, Anão...)")
    descricao: str = Field(default="", max_length=500)
    objetivo: str = Field(min_length=1, max_length=500)
    medo: str = Field(default="", max_length=400)
    limite: str = Field(default="", max_length=400)
    necessidade: str = Field(default="", max_length=120)
    # Fase 1 (ADR-0033) — nomes do catálogo que esta pessoa vende; preços
    # são do servidor (services/items.py). Vazio = não é mercador.
    mercadoria: list[str] = Field(default_factory=list, max_length=8)
    segredo: str = Field(default="", max_length=600)
    segredo_revelado: bool = False
    confianca: int = Field(default=0, ge=-100, le=100)
    disposicao: Literal["reservado", "cooperativo", "hostil", "ausente"] = "reservado"
    conhecimentos: list[Conhecimento] = Field(default_factory=list, max_length=40)
    lembrancas: list[str] = Field(default_factory=list, max_length=40)
    promessas: list[str] = Field(default_factory=list, max_length=20)


class ConflitoMundo(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")
    nome: str = Field(min_length=1, max_length=100)
    agente: str = Field(min_length=1, max_length=60)
    local: str = Field(min_length=1, max_length=100)
    objetivo: str = Field(min_length=1, max_length=500)
    sinal: str = Field(min_length=1, max_length=500)
    consequencia: str = Field(min_length=1, max_length=600)
    efeito: Literal["disputa", "bloquear", "partir"] = "disputa"
    alvo: str = Field(default="", max_length=60)
    intervalo: int = Field(default=60, ge=10, le=1440)
    etapas: int = Field(default=4, ge=2, le=8)
    progresso: int = 0
    proximo_avanco: int = 0
    intervencoes: int = 0
    estado: Literal["ativo", "resolvido", "concretizado"] = "ativo"
    desfecho: str = ""


class Arco(BaseModel):
    """Fase 4 do plano "jogo completo" (ADR-0035) — um conflito central que
    vira capítulo. O servidor decide quando ele pode encerrar; a IA só
    escreve o desfecho depois."""

    id: str = Field(pattern=r"^[a-z0-9_-]{1,60}$")
    titulo: str = Field(min_length=1, max_length=100)
    premissa: str = Field(default="", max_length=600)
    conflito_central: str = Field(default="", max_length=60)
    chefe: str | None = None
    chefe_enfrentado: bool = False
    estado: Literal["ativo", "encerrado"] = "ativo"
    resultado: Literal["", "acordo", "consequencia", "vitoria_chefe", "abandono"] = ""
    turno_inicio: int = 1
    turno_fim: int | None = None
    marcos_no_inicio: int = 0
    desfecho: dict | None = None
    recompensa: dict = Field(default_factory=dict)


class MundoVivo(BaseModel):
    versao: int = 1
    arcos: list[Arco] = Field(default_factory=list)
    minutos: int = 0
    cenas: dict[str, CenaPersistente] = Field(default_factory=dict)
    pessoas: dict[str, PessoaMundo] = Field(default_factory=dict)
    conflitos: dict[str, ConflitoMundo] = Field(default_factory=dict)
    conhecimento: list[Conhecimento] = Field(default_factory=list)
    tentativas: dict[str, str] = Field(default_factory=dict)
    objetivos: list[str] = Field(default_factory=list)
    especializacoes: dict[str, str] = Field(default_factory=dict)
