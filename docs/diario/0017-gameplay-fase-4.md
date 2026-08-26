# Revisão de gameplay — Fase 4 (esqueleto de Atos)

**Período:** 25/08/2026 · uma sessão com o Claude Code · **estimado no plano:** 10h (Fase
4 de 9, `plans/c-users-breno-downloads-gameplay-v2-md-purrfect-mist.md`)

## O que eu queria com essa fase

O jogo tinha missão (`nome_missao`/`objetivo_missao`, atualizada livremente turno a
turno), mas nada de arco maior — sem direção de campanha, 300 turnos podiam virar "sopa
narrativa" sem nenhum fio condutor por trás. Esta fase dá um esqueleto de 3 a 5 Atos,
gerado uma vez na criação do personagem, que o servidor injeta um de cada vez — o jogador
nunca vê a lista inteira, só vive o Ato atual.

## O que mudou

- **`Ato`** (`domain/state.py`): `titulo` + `objetivo`. `QuestLog` ganha `atos: list[Ato]`
  e `ato_atual: int`.
- **`narrator.gerar_prologo_missao`** pede o esqueleto na MESMA chamada que já gera o
  prólogo (sem chamada extra ao modelo) — `_validar_atos` recusa qualquer formato fora do
  esperado (lista fora de 3-5 itens, item sem `titulo`/`objetivo`, tipo errado) e cai num
  `ATOS_PADRAO` genérico. Mesma fronteira de confiança já usada pro `local_inicial`.
- **`montar_contexto`** injeta só `[ATO ATUAL]` — nunca o esqueleto inteiro — e um aviso
  extra só quando existe um PRÓXIMO Ato pra avançar (no último Ato, o aviso some).
- **`atualizar_missao`** ganha `avancar_ato: bool` — quando `true`, avança
  `ato_atual` (nunca estoura o fim da lista) e gera um evento "📖 Novo Ato". A ferramenta
  já existia (era WIP de antes desta revisão); ganhou o parâmetro novo, não foi reescrita.

## O que achei testando ao vivo

**Um bug real na Fase 1, só visível agora.** Testei um personagem novo do início — criação
gerou um esqueleto de 3 Atos conectado à história do jogador ("Sombras na Cidade" → "Eco
da Cripta" → "Fogo do Forte"), bom sinal de que o prompt está funcionando. Mas ao jogar um
turno de combate, a tag `[OPÇÕES]` (com acento — grafia correta em português) vazou crua
pro jogador, e o campo `opcoes` voltou vazio.

A causa: o prompt da Fase 1 instrui o modelo a escrever exatamente `[OPCOES]` (sem
acento), mas ao vivo o modelo "corrige" para a grafia certa do português —
`[OPÇÕES]`. Meu regex (`guardrail.extrair_opcoes`) só reconhecia a versão sem acento.
Nenhum teste com RNG fixo pegaria isso — só apareceu jogando de verdade, exatamente a
razão de `[[mestre-ia-testar-llm-ao-vivo-cedo]]`. Corrigido trocando o regex exato por um
padrão tolerante (`\[OP.{0,2}ES\]`, mesma lógica no backend e no frontend) que casa
"OPCOES", "OPÇÕES" e variações de acento sem enumerar cada uma.

**Um lembrete chato, não um bug**: o servidor deste projeto roda sem `--reload`
(`.claude/launch.json`) — depois de corrigir o regex, testei de novo contra o MESMO
processo antigo e o bug "continuou" acontecendo, porque o código novo nunca tinha sido
carregado. Só depois de reiniciar o servidor a correção realmente se confirmou.

## Decisões tomadas

- Sem ADR nesta fase — trabalho aditivo (novo campo, nova validação, extensão de
  ferramenta existente), sem divergência de decisão registrada.
- `atualizar_missao(avancar_ato=true)` não concede XP sozinho — o modelo ainda precisa
  chamar `concluir_objetivo` separadamente se o Ato terminou por um feito digno de XP.
  Documentado como dependência fraca da Fase 0, não bug.

## Números

- 371 testes de backend passando (eram 353 no fim da Fase 3) — 18 novos: `_validar_atos`
  (formatos válidos/inválidos), `gerar_prologo_missao` com Atos do modelo/malformados/sem
  client, `montar_contexto` injetando `[ATO ATUAL]` e clampando índice fora do intervalo,
  `atualizar_missao` avançando Ato (e não estourando no último), mais o teste da grafia
  acentuada de `[OPÇÕES]`.
- `ruff check` e `tsc --noEmit` limpos.
- Testado ao vivo do zero: criação de personagem gerando um esqueleto de 3 Atos coerente
  com a história escrita, um combate resolvido, um item recebido — tudo com a tag
  `[OPCOES]`/`[OPÇÕES]` funcionando depois da correção.

## Próximo passo

Fase 5 (locais inventados) ou Fase 6 (mundo vivo) — nenhuma depende desta. Um golden case
pra `atacar_com_aliado` (pendência da Fase 3) e outro pra `avancar_ato` continuam em
aberto, registrados, não esquecidos.
