# Revisão de gameplay — Fase 5 (locais inventados)

**Período:** 25/08/2026 · uma sessão com o Claude Code · **estimado no plano:** 12h (Fase
5 de 9, `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`)

## O que eu queria com essa fase

`mover()` (Etapa 4) só reconhecia os 7 locais de `data/locations.json` — sair desse
catálogo era erro, ponto final. Isso protege o motor (o narrador nunca referencia um
lugar que o resto do jogo não reconhece), mas também trava o mundo num tamanho fixo. Esta
fase abre essa porta sem abrir mão da garantia: o modelo pode propor um local novo, mas
quem decide se ele passa a existir de verdade é sempre o servidor.

## O que mudou

- **`WorldState.locais_descobertos: dict[str, LocalDescoberto]`** — por personagem (dois
  heróis podem descobrir "A Torre Caída" em cenas diferentes sem colidir).
- **`mover(destino, descricao_proposta=None)`**: primeiro busca em `locais_descobertos`,
  depois no catálogo global. Se não achar em nenhum dos dois E vier uma descrição, registra
  o local (clima herdado da cena atual, descrição da proposta) e só então move. Sem
  descrição, o comportamento continua sendo o de sempre — erro com a lista de locais
  válidos, agora incluindo os já descobertos nesta sessão.
- **Nenhuma ferramenta nova** — `mover` ganhou um parâmetro opcional, não virou duas
  ferramentas. Era a decisão certa: uma ação só ("ir a algum lugar"), não duas pro modelo
  escolher entre.

## Por que isso precisava de ADR

[ADR-0028](../adr/0028-locais-inventados-revisao-da-validacao-fechada-de-mover.md) — a
validação fechada de `mover` existe desde a Etapa 4 por um motivo concreto e documentado
(P-5 do backlog antigo: o prólogo inventava locais fora do catálogo, e o próprio `mover`
rejeitava o lugar onde o herói nascia). Abrir essa porta de novo sem cuidado reabriria
exatamente aquele problema. A garantia que sobrevive: o modelo nunca escreve
`world_state.local` direto — só propõe uma descrição; `mover()` é sempre quem decide e
grava. Mesmo padrão "propõe/decide" do ADR-0002, aplicado agora à existência de um lugar.

## O que achei no caminho

**P-5 estava listado como problema aberto no backlog antigo, mas já tinha sido corrigido
na Etapa 11** — `gerar_prologo_missao` já valida `local_inicial` contra o catálogo.
Achado investigando o código antes de planejar esta fase (mesmo hábito de sempre: "o
código é a fonte, não o documento"), corrigido o texto do backlog junto.

## Como testei

**11 testes novos** de backend: destino desconhecido sem descrição continua rejeitado
(comportamento antigo intacto), destino novo com descrição é registrado e move, clima
herda da cena atual, local já descoberto é reconhecido sem precisar de nova descrição, e
`descricao_proposta` é ignorada quando o destino já está no catálogo (não sobrescreve
nada).

**Ao vivo, contra a Groq de verdade**: pedi pro herói sair da estrada e chegar a um
vilarejo inventado, "Poço do Corvo". O modelo chamou `mover` com `descricao_proposta`
corretamente, o evento "🗺️ Novo local registrado" apareceu, e `load_game` confirmou o
estado persistido (`local: "Poço do Corvo"`, clima herdado). Testei o caminho de volta —
saí pra Vila de Phandalin e voltei pro Poço do Corvo numa mensagem SEM descrição nenhuma
— e o servidor reconheceu o local sem pedir registro de novo, sem a linha "Novo local
registrado" (só "Vocês seguem para..."), exatamente o comportamento esperado de um lugar
que já existe.

## Números

- 376 testes de backend passando (eram 371 no fim da Fase 4) — 11 novos, `TestMover`
  ampliado.
- `ruff check` e `tsc --noEmit` limpos (frontend não precisou de mudança nesta fase).
- Fluxo completo confirmado ao vivo: descoberta → persistência → reconhecimento na
  segunda visita, sem precisar forçar nada.

## Próximo passo

Fase 6 (mundo vivo: relógios de facção, encontros aleatórios, descanso, tags de item) é a
próxima da lista original, e depende parcialmente desta Fase 5 (encontros aleatórios usam
`mover`). Fase 7 (livro da campanha: epitáfio, crônica) não depende de nada ainda pendente
e também está livre pra vir antes.
