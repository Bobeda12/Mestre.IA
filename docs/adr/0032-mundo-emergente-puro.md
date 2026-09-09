# ADR-0032 — Mundo emergente puro: fim do esqueleto de Atos e das aberturas roteirizadas

**Data:** 08/09/2026
**Status:** Aceito
**Etapa:** Plano "jogo completo" (Fase 0 — ver `docs/diario/0026-mundo-vivo-e-fim-dos-atos.md`)
**Supersede:** a Fase 4 da revisão de gameplay (esqueleto de Atos em `QuestLog`, 25/08/2026) e as 8 aberturas curadas de `services/adventure.py` (`INICIOS`)

---

## Contexto

Desde a revisão de gameplay de 25/08/2026 toda campanha nascia de uma das 8 aberturas
roteirizadas de `adventure.INICIOS` (caravana, baile de máscaras, julgamento, farol...) e
carregava um esqueleto de 3 a 5 **Atos** gerado pelo prólogo. O narrador recebia o Ato
atual no prompt, avançava de Ato por `atualizar_missao(avancar_ato=True)` e um relógio de
urgência (`RELOGIO_URGENCIA`, que subia a cada descanso longo) injetava um `[EVENTO GLOBAL]`
quando o herói demorava demais.

Na prática, jogando, esse desenho tinha três problemas:

1. **O roteiro não era a história.** O modelo raramente chamava `avancar_ato`; a campanha
   ficava presa no Ato 1 enquanto a narração já tinha ido para outro lugar. O Ato virou
   anotação ignorada, não estrutura.
2. **As aberturas se repetiam.** Oito textos fixos, sorteados, dão a mesma "primeira
   cena" a cada herói novo. Depois de três personagens o jogador reconhece o baile.
3. **Nada do que o narrador inventava virava mundo.** Um portão descrito como trancado
   estava aberto no turno seguinte; o NPC que prometeu algo esquecia. A ficção não tinha
   onde ser registrada.

A sessão de 08/09/2026 trouxe o **Mundo Vivo** (`domain/living_world.py`,
`services/living_world.py`, `services/world_tools.py`, `services/emergent_start.py`):
cenas com objetos que têm propriedades verificáveis (trancado, móvel, inflamável...),
pessoas com objetivo/medo/limite/necessidade/segredo/confiança, conflitos com relógio
próprio que avançam sozinhos, e uma **origem determinística por semente** que já é
jogável sem IA. O prólogo passou a forçar `atos = []`, o que deixou o sistema de Atos
desligado mas ainda no código.

## Decisão

**Mundo emergente puro.** O esqueleto de Atos, as 8 aberturas roteirizadas e o relógio de
urgência do Ato são **removidos** do código, não só desligados:

- `services/adventure.py` fica só com temperamentos, dificuldades e o catálogo que a
  criação usa. `INICIOS`, `preparar_abertura` e `contexto_campanha` saem.
- `QuestLog` volta a ser missão miúda (`nome_missao`, `objetivo_missao`). `Ato`,
  `atos`, `ato_atual` saem; `atualizar_missao` perde `avancar_ato`.
- `narrator.montar_contexto` perde `[ATO ATUAL]`, `[EVENTO GLOBAL]` e `[ORIGEM DA
  CAMPANHA]`. O que o narrador recebe sobre "onde a história está" é o bloco
  `[MUNDO PERSISTENTE]`: pessoas, objetos, conflitos e o que o herói já sabe.
- A requisição de criação perde `inicio_aventura` (o frontend nunca enviava).
- Toda campanha nasce de `emergent_start.criar_origem(char, semente)`: uma cena, dois
  NPCs com interesses opostos, um conflito com prazo e **uma saída livre** — "você pode
  partir sem aceitar qualquer compromisso" é uma promessa que o motor honra (`mover`
  aceita qualquer local conhecido a partir dela). O modelo pode propor outro mundo
  inicial; `validar_mundo_inicial` decide se ele é coerente, senão cai na origem
  determinística. Mesmo padrão "o modelo propõe, o servidor decide" do ADR-0002.

**A pressão de tempo continua existindo, só mudou de dono.** Antes era um contador por
descanso longo ligado ao Ato; agora são os conflitos do Mundo Vivo, que avançam em
minutos a cada ação consumida (`executar` → `avancar_tempo`: 1 min em combate, 10 numa
ação, 120 numa viagem, 480 num descanso longo). A consequência de ignorar um conflito é
concreta (uma passagem bloqueada, um NPC que partiu), não uma frase genérica no prompt.

**Saves antigos não quebram.** `QuestLog`/`WorldState` são Pydantic com chaves extras
ignoradas; `atos`, `ato_atual` e `relogios["urgencia_ato"]` gravados ficam inertes.
`living_world.migrar_mundo` cria a cena do local atual em saves anteriores ao Mundo Vivo
(`WorldState.versao_mundo`, mesmo padrão de `versao_progressao`).

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Manter os Atos "como anotação" ao lado do Mundo Vivo | Zero remoção; campanha teria começo/meio/fim garantido no papel | Era exatamente o estado do WIP: código morto (`ATOS_PADRAO`, `_validar_atos`, `contexto_campanha` devolvendo string vazia) que ninguém executava e que qualquer refatoração precisaria carregar | Código que não roda mente sobre o que o jogo faz |
| Híbrido: as 8 aberturas viram "sementes" que populam o mundo inicial (NPCs, conflito, lugar), sem Atos | Aproveita ~250 linhas de conteúdo autoral já escrito | Cada abertura precisaria ser reescrita no formato de cena/pessoa/conflito do Mundo Vivo (não é conversão mecânica), e a repetição entre heróis continuaria — são 8 variantes fixas contra uma origem parametrizada por semente | O custo é o de escrever conteúdo novo, e o resultado ainda seria menos variado que a origem determinística |
| Voltar aos Atos com o Mundo Vivo só como camada de cena | Arco garantido | Reinstala o problema 1 (o modelo não avança Ato) e obriga o narrador a servir a dois donos da história: o roteiro e os conflitos | O autor decidiu explicitamente pelo emergente (08/09/2026) |

## Consequências

**Ganhamos:**
- Uma única fonte de "o que existe no mundo": o `MundoVivo` gravado no save. O que o
  narrador não registrou não existe; o que registrou não some.
- Campanhas diferentes de verdade entre heróis (origem por semente + o que o modelo
  propõe) sem oito textos fixos para manter.
- ~500 linhas a menos de código e prompt: `adventure.py` passou de 380 para 30 linhas;
  três seções saíram do prompt do narrador.

**Pagamos:**
- **A crônica perde os "capítulos" que os Atos davam de graça.** Hoje a única estrutura
  de arco é a missão miúda. Isso é recuperado na **Fase 4 do plano "jogo completo"**
  (arcos com final verificável pelo servidor, ADR-0035), que é a resposta desenhada
  para este buraco — não uma volta aos Atos.
- Os cenários táticos de combate (`encounters.CENARIOS`) e as cenas do Mundo Vivo são
  dois sistemas de "lugar" que coexistem: a cena persistente empresta a descrição ao
  painel tático, mas as interações de terreno continuam vindo do cenário sorteado.
  Unificar os dois é trabalho futuro, não desta decisão.

**Fica em aberto:**
- O `WorldState.relogios` fica no modelo sem uso (só para saves antigos carregarem).
  Se nenhum relógio novo aparecer até a Fase 4, sai junto com a limpeza dos arcos.

## Como saber que erramos

- Se, jogando dez turnos, o mundo continuar vazio (o narrador não chama
  `registrar_cena`/`registrar_pessoa`), a origem determinística está segurando o jogo
  sozinha e o prompt precisa forçar o registro na primeira visita a um local (a
  assinatura `tool_choice: dict` em `llm_client` foi preparada para isso e ainda não
  tem chamador).
- Se os amigos relatarem "não sei o que fazer" com mais frequência do que com as
  aberturas roteirizadas, a origem precisa de um gancho mais forte — não de Atos de volta.

## Referências

- ADR-0002 — o modelo propõe, o servidor decide
- ADR-0027, ADR-0028 — companheiros mecânicos e locais inventados (o Mundo Vivo é a
  generalização dos dois: tudo o que o narrador inventa passa pelo registro)
- `docs/diario/0026-mundo-vivo-e-fim-dos-atos.md` — a rodada em que isto foi feito
- Plano "jogo completo" (08/09/2026), Fase 0 e Fase 4
