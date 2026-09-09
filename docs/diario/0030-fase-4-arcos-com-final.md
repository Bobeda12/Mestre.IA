# Fase 4 do plano "jogo completo": arcos com final

**Período:** 08/09/2026 · mesma sessão das Fases 0 a 3

## O que aconteceu

Desde que os Atos saíram (Fase 0, ADR-0032), só a morte encerrava alguma coisa na
campanha. Esta fase devolve os capítulos, de um jeito que os Atos nunca tiveram: **quem
decide que um capítulo pode fechar é o servidor**, com três sinais que ele mesmo mede; a IA
só escreve o desfecho depois, e a recompensa vem de tabela. A regra está no
[ADR-0035](../adr/0035-arcos-verificaveis-pelo-servidor.md).

## O que o jogador sente

- **Todo herói nasce dentro de um capítulo.** A origem emergente abre o arco 1 a partir do
  conflito da origem ("A disputa por grãos", "Uma testemunha de partida"...). O painel "Ao
  seu redor" ganhou a caixa "Capítulo atual" com a premissa, o conflito central e um
  checklist honesto: quantos turnos se passaram, quantos fatos foram registrados, e o que
  ainda falta para fechar.
- **Fechar é um momento.** Quando o servidor confirma (pelo menos 8 turnos, 2 fatos, e o
  conflito central resolvido, concretizado ou o chefe enfrentado), o botão "Encerrar
  capítulo" acende. Clicar abre uma tela com o título e o texto do desfecho escritos pela
  IA a partir dos marcos daquele arco, e a recompensa: XP por nível, ouro e itens da tabela
  de saque. No teste ao vivo: "A Partida de Dara", três parágrafos, 100 XP, 18 de ouro,
  Poção de Cura e Poção de Foco.
- **Consequência também fecha.** Se o herói deixou o conflito se concretizar, o arco encerra
  por "consequências", com metade do XP e sem item. "Abandonar" existe, pela interface, sem
  recompensa — o mundo segue.
- **O narrador não encerra sozinho.** Ele pode chamar `encerrar_arco` quando a cena pedir,
  mas só passa se o servidor confirmar; uma tentativa por turno. E pode abrir o próximo arco
  (`abrir_arco`) quando um conflito registrado ganhar peso.
- **A Crônica ganha capítulos.** O desfecho é gravado na memória de longo prazo como
  evento do tipo "arco", e a crônica exportável o lê em ordem.

## O que mudou por baixo

- `Arco` em `MundoVivo.arcos` (JSON, sem migration); `condicoes_arco` é a única fonte da
  verdade sobre "pode fechar", usada pela ferramenta, pelo frame de estado e pelo prompt
  (`[ARCO ATUAL]` diz ao narrador o que falta).
- `encerrar_arco` aplica a recompensa determinística e marca `arco_recem_encerrado`;
  `routers/game.py` gera o desfecho uma vez (`narrator.gerar_desfecho_arco`, molde do
  epitáfio, fallback = marcos) e registra a memória. `combat_state.chefe_do_arco` e
  `marcar_chefe_enfrentado` já ficam prontos para a Fase 5 ligar o chefe.

## Como testei

- 13 testes em `tests/test_arcos.py` (origem abre o arco 1; cada condição bloqueia
  separadamente; uma tentativa por turno; acordo dá recompensa e marco; consequência vale
  metade sem item; abandono sem recompensa; `abrir_arco` exige conflito ativo e nenhum arco
  aberto; não encerra em combate; origem com dois arcos é recusada; vitória contra o chefe
  habilita o fechamento; desfecho sem modelo usa os marcos; ferramentas só fora de combate)
  e um de rota (desfecho e memória gravados). Suíte: 537 verdes; ruff, mypy e typecheck
  limpos.
- No navegador, com a cota do Groq de volta: arco preparado com o conflito resolvido, caixa
  "Capítulo atual" com o checklist completo e o botão aceso, clique → desfecho gerado pela
  IA em três parágrafos, recompensa aplicada (ouro 10 → 28, XP, itens na mochila com a
  animação de saque), "Seguir em frente" fecha o overlay.

## O que ficou registrado para depois

- Os limiares (8 turnos, 2 fatos) são chute informado; ajustar com partidas reais.
- O narrador ainda não foi visto ao vivo chamando `abrir_arco` sozinho (cota curta).
- `WorldState.relogios` continua sem uso; pode sair.

## Próximo passo

Fase 5: bestiário dos níveis 5 a 10, chefe do arco de verdade (`abrir_arco` sorteia um
chefe, `iniciar_combate` usa a ficha reservada) e sprites para os monstros sem arte.
