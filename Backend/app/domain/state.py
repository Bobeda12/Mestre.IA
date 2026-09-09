"""Modelos Pydantic do estado do jogo — a "verdade" do sistema, tipada.

Antes da Etapa 2, `world_state`, `combat_state` e `quest_log` (Backend/api.py)
eram dicionários soltos, passados de função em função sem forma garantida.
Aqui eles ganham um formato explícito; a forma do JSON gravado no banco e
devolvido pela API não muda (ver domain/state.py usado pelos routers)."""

from typing import Literal

from pydantic import BaseModel

from app.domain.items import ItemInventado
from app.domain.living_world import MundoVivo


class Inimigo(BaseModel):
    nome: str
    hp: int
    max_hp: int
    ca: int
    # Preenchidos a partir de data/monsters.json na criação (Etapa 3, ver
    # services/combat.py) — o "Inimigo genérico hp:10" morreu aqui.
    bonus_ataque: int = 0
    dano_dado: str = "1d4"
    nome_ataque: str = ""
    # Fase 0 da revisão de gameplay (Etapa 12/13) — antes era lido de
    # data/monsters.json e descartado em services/combat.py:_criar_inimigo;
    # a IA de inimigo (Fase 1) passa a usar este campo para recuar, ganhar
    # vantagem em matilha etc., em vez de só bater sempre.
    comportamento: str = ""
    arquetipo: str = ""
    afastado: bool = False
    xp: int = 0
    intencao: str = "atacar"
    efeitos: dict[str, int] = {}


class Aliado(BaseModel):
    """Fase 2 da revisão de gameplay (Etapa 12/13) — combatente amigo além
    do herói. Mesma forma de `Inimigo` (é o que faz o motor tratar os dois
    como alvo/atacante pela mesma lógica), mas semanticamente distinto: só
    aparece em combate depois que a Fase 3 der ao jogador uma forma de
    recrutar (ainda não existe nenhuma nesta fase — `aliados` fica vazio na
    prática, e é isso que preserva o comportamento de antes desta fase)."""

    nome: str
    hp: int
    max_hp: int
    ca: int
    bonus_ataque: int = 0
    dano_dado: str = "1d4"
    nome_ataque: str = ""


class CombatState(BaseModel):
    ativo: bool = False
    bonus_especializacao: int = 0
    foco: int = 3
    foco_max: int = 3
    rodada: int = 1
    efeitos_heroi: dict[str, int] = {}
    acao_resolvida: bool = False
    cenario_id: str = ""
    progresso_objetivo: int = 0
    objetivo_concluido: bool = False
    interacoes_usadas: list[str] = []
    inimigos: list[Inimigo] = []
    # Fase 2 — ver `Aliado`. `combat.turno_inimigos` escolhe entre o herói
    # e os aliados vivos como alvo de cada ataque inimigo; ADR-0027 revisa
    # a decisão de escopo §9.3 (PLANO_MESTRE.md) que isto altera.
    aliados: list[Aliado] = []
    # Testes de morte (herói a 0 PV) — ver services/combat.py:turno_morte.
    sucessos_morte: int = 0
    falhas_morte: int = 0
    resultado: Literal["vitoria", "morte", "estabilizado"] | None = None
    # Ordem de iniciativa (Etapa 7) — índices em `inimigos`, com -1
    # representando o herói, ordenados do maior pro menor resultado de
    # `rules_engine.rolar_iniciativa`. Calculada uma vez em
    # `combat.iniciar_combate`; `combat.turno_inimigos` ataca nessa ordem
    # em vez de todos de uma vez. `turno_atual` é o índice dentro desta
    # lista — HUD do frontend usa pra destacar de quem é a vez; não trava a
    # resolução (o backend ainda resolve o herói e depois a rodada de
    # inimigos inteira numa única chamada, um turno = uma mensagem).
    ordem_iniciativa: list[int] = []
    turno_atual: int = 0
    # Fase 1 da revisão de gameplay (Etapa 12/13) — efeitos das ações
    # estruturadas (esquivar/defender/investir/esconder_se) sobre a PRÓXIMA
    # rodada de inimigos. `services/tools.py:_resolver_reacao_inimiga`
    # consome e reseta os três depois de cada rodada — "até seu próximo
    # turno" dura exatamente uma rodada, nunca mais.
    heroi_vantagem_inimiga: bool | None = None  # True=investir (vantagem p/ inimigo), False=esquivar (desvantagem)
    heroi_bonus_ca: int = 0  # defender: +2 na CA do herói contra a próxima rodada
    heroi_escondido: bool = False  # esconder_se bem-sucedido: inimigos não acham o herói nesta rodada


class LocalDescoberto(BaseModel):
    """Fase 5 da revisão de gameplay (Etapa 12/13, ADR-0028) — um local que
    o narrador propôs e o servidor registrou, fora do catálogo global
    (`data/locations.json`). Vive em `WorldState`, então é por PERSONAGEM
    — dois heróis podem descobrir "A Torre Caída" em lugares narrativamente
    diferentes, sem colidir."""

    descricao: str
    clima: str = ""


class WorldState(BaseModel):
    local: str = ""
    mundo: MundoVivo = MundoVivo()
    inicio_aventura: str = "emergente"
    # Fase 0 do plano "jogo completo" — versão do Mundo Vivo dentro do save.
    # 0 = personagem criado antes do Mundo Vivo (mundo vazio); `living_world.
    # migrar_mundo` cria a cena do local atual e marca 1. Mesmo padrão de
    # `versao_progressao`/`progression.migrar_progressao`.
    versao_mundo: int = 0
    semente_aventura: int = 0
    marcos: list[str] = []
    versao_progressao: int = 0
    objetivos_concluidos: list[str] = []
    clima: str = ""
    turno: int = 1
    # Fase 5 — locais que `mover()` registrou porque o narrador propôs uma
    # descrição pra um destino fora do catálogo. `services/tools.py:mover`
    # consulta isto ANTES do catálogo global — é o que faz o motor nunca
    # ficar sabendo de um lugar que ele mesmo não registrou (mesma garantia
    # da validação estrita antiga, só que o registro agora pode acontecer
    # em tempo de jogo, não só nos arquivos JSON).
    locais_descobertos: dict[str, LocalDescoberto] = {}
    # Fase 1 (ADR-0033) — itens que o narrador criou por `dar_item` fora do
    # catálogo: só nome, descrição e tags fechadas; nunca números.
    itens_inventados: dict[str, ItemInventado] = {}
    # Relógios genéricos por nome. O único uso (urgência do Ato) saiu com
    # os Atos (Fase 0 do plano "jogo completo", ADR-0032); o campo fica
    # pra saves antigos carregarem sem erro e pra um relógio futuro caber
    # sem mudar o formato salvo. Pressão de tempo hoje = conflitos do
    # Mundo Vivo (`living_world.avancar_tempo`).
    relogios: dict[str, int] = {}
    # Fase 6 — turno (world_state.turno) do último descanso longo bem
    # sucedido; -999 nunca aconteceu. `descansar` usa isso pra impedir
    # descanso longo em sequência sem tempo narrativo passar entre eles.
    ultimo_descanso_longo: int = -999
    # Pendência do remaster UX (PLANO_REMASTER_UX.md, item 2) — hora do dia
    # (0-23), começa às 8h. Avança por AÇÃO lógica em services/tools.py
    # (mover = poucas horas, descanso longo = uma noite inteira), nunca por
    # `turno` — é exatamente a distinção que o documento de design original
    # pedia e que não existia até aqui. `rules_engine.periodo_do_dia`
    # traduz pra madrugada/manhã/tarde/noite.
    hora_do_dia: int = 8


class QuestLog(BaseModel):
    """Missão miúda que o narrador atualiza turno a turno (`atualizar_missao`).
    O esqueleto de Atos que morava aqui saiu na Fase 0 do plano "jogo
    completo" (ADR-0032); saves antigos com `atos`/`ato_atual` carregam
    sem erro porque o Pydantic ignora chaves extras."""

    nome_missao: str = ""
    objetivo_missao: str = ""
