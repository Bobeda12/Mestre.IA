# O teto de orçamento cortava a narração antes de tentar

**Período:** 15/09/2026 · achado ao vivo, jogando no site publicado

## O que aconteceu

A tela mostrou de novo o aviso "O mestre engole as palavras por um instante" — o texto que
aparece quando a IA não consegue narrar, mas o dado já rolou (por isso o card de SUCESSO/FALHA
aparece normalmente, só falta a prosa). Da primeira vez que isso apareceu (ver auditoria
pré-lançamento), a causa era o teto de tokens por minuto dos provedores gratuitos — a
solução foi esperar entre turnos.

Desta vez foi diferente: aconteceu logo no segundo turno da sessão, sem nenhuma pressa antes.
O log do Render mostrou o que realmente houve nesse turno (4 chamadas para resolver uma ação
de "examinar o Armazém de Kaelen"):

1. `agir_no_mundo` (examinar) — não deu certo sozinho
2. `consultar_contexto` — buscou dados do armazém
3. `rolar_teste` (sabedoria) — o dado que apareceu na tela, com sucesso
4. a chamada que narraria o resultado — nunca chegou a sair pro provedor

A 4ª chamada falhou em menos de 1 milissegundo depois da 3ª. As três chamadas anteriores,
todas de verdade (POST pra API da Gemini, todas "200 OK"), levaram de 2 a 3 segundos cada —
tempo de rede normal. Uma falha em 1ms não é rede: é código local recusando antes de tentar.

O motor tem um orçamento de sanidade por turno (`OrcamentoTurno`, em
`app/services/orcamento_ia.py`) que soma uma estimativa de tamanho a cada chamada e desiste
do turno se a soma passar de um teto (`agent_limite_turno_estimado`, valia 24000). Com 3
chamadas já gastando cerca de 21500 dessa estimativa, sobrava menos de 2500 pra 4ª — bem
menos do que qualquer chamada real custa (a menor das três medidas foi quase 7200). O teto
não estava protegendo contra o provedor recusar (ele nem chegou a ser chamado); estava
protegendo contra si mesmo, cortando um turno comum que só precisou de mais de 3 idas e
vindas antes de narrar.

## O que mudou

- `agent_limite_turno_estimado` subiu de 24000 para 60000 em
  [`Backend/app/infra/settings.py`](../../Backend/app/infra/settings.py) — fôlego pra usar
  as 6 chamadas que `agent_max_passos` já permitia, em vez de travar depois de 3.
- O teto por chamada única (`agent_limite_entrada_estimado`, 12000) não mudou — nenhuma
  chamada real chegou perto disso; o problema era só a soma.

## Por que isso importa

Um turno que investiga antes de agir (examinar → consultar → testar → narrar) não é
incomum — é o tipo de ação mais interessante do jogo. Um teto de sanidade calibrado pra um
cenário sintético (o schema completo de 51 ferramentas, sem o filtro normal de produção)
acabou sendo pequeno demais pro caso comum de produção, que usa ferramentas filtradas e por
isso `agent_max_passos` (6) foi pensado pra caber — só que ninguém tinha medido a SOMA de 6
chamadas reais contra o teto do turno inteiro até este achado.

Achado à parte: as 3 chamadas do log foram todas pra Gemini — nenhuma pra Groq. Confirmado
com o autor: é intencional, só `GEMINI_API_KEY` está configurada no Render (chave própria,
sem cartão). `chamar_com_fallback` já pula qualquer elo `groq:...` sem cliente configurado
(ver `_chave_do_provedor`), então não é bug — é só um lembrete de que, em produção, a cadeia
de fallback entre provedores do ADR-0008/ADR-0024 hoje tem um provedor só: se a Gemini
enfrentar rate limit, não há pra onde cair.

## Como testar

Os 677 testes do backend continuam passando (a suíte de orçamento usa `monkeypatch` pro
valor do teto, não o padrão — ver `tests/test_contexto_ia.py`). A confirmação de verdade
depende de jogar ao vivo um turno com vários passos de ferramenta antes da narração — o
mesmo tipo de teste que só se vê rodando contra a API real, não com um cliente fixo.
