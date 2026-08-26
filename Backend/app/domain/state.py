"""Modelos Pydantic do estado do jogo — a "verdade" do sistema, tipada.

Antes da Etapa 2, `world_state`, `combat_state` e `quest_log` (Backend/api.py)
eram dicionários soltos, passados de função em função sem forma garantida.
Aqui eles ganham um formato explícito; a forma do JSON gravado no banco e
devolvido pela API não muda (ver domain/state.py usado pelos routers)."""

from typing import Literal

from pydantic import BaseModel


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
    clima: str = ""
    turno: int = 1
    # Fase 5 — locais que `mover()` registrou porque o narrador propôs uma
    # descrição pra um destino fora do catálogo. `services/tools.py:mover`
    # consulta isto ANTES do catálogo global — é o que faz o motor nunca
    # ficar sabendo de um lugar que ele mesmo não registrou (mesma garantia
    # da validação estrita antiga, só que o registro agora pode acontecer
    # em tempo de jogo, não só nos arquivos JSON).
    locais_descobertos: dict[str, LocalDescoberto] = {}
    # Fase 6 da revisão de gameplay (Etapa 12/13) — relógio de facção
    # (contador de urgência do Ato atual). Só uma chave usada por enquanto
    # (`services/tools.py.RELOGIO_URGENCIA`); dict pra caber mais de um
    # relógio no futuro sem mudar o formato salvo. Avança em
    # `descansar("longo")`, reseta quando o Ato muda
    # (`atualizar_missao(avancar_ato=True)`).
    relogios: dict[str, int] = {}
    # Fase 6 — turno (world_state.turno) do último descanso longo bem
    # sucedido; -999 nunca aconteceu. `descansar` usa isso pra impedir
    # descanso longo em sequência sem tempo narrativo passar entre eles.
    ultimo_descanso_longo: int = -999


class Ato(BaseModel):
    """Fase 4 da revisão de gameplay (Etapa 12/13) — um passo do esqueleto
    de campanha (3 a 5 Atos), gerado uma vez na criação do personagem
    (`narrator.gerar_prologo_missao`). Mais estável que `QuestLog.nome_missao`/
    `objetivo_missao` (que o narrador atualiza livremente turno a turno via
    `atualizar_missao`) — os Atos são a arquitetura da campanha, a missão
    atual é o passo miúdo dentro de um Ato."""

    titulo: str
    objetivo: str


class QuestLog(BaseModel):
    nome_missao: str = ""
    objetivo_missao: str = ""
    # Fase 4 — o esqueleto inteiro (3 a 5 Atos) fica guardado aqui, mas
    # `narrator.montar_contexto` só injeta o ATO ATUAL no prompt (mesmo
    # padrão de "nunca despejar a estrutura inteira" de `[MISSÃO ATUAL]`) —
    # ver a nota em `services/narrator.py`. Lista vazia é o caso de
    # personagens criados antes desta fase, ou quando o prólogo roda sem
    # LLM (`gerar_prologo_missao` sem chave configurada).
    atos: list[Ato] = []
    ato_atual: int = 0
