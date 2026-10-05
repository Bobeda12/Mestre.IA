# ADR-0038 — Rotear cada chamada de IA por papel (volume, destaque, fundo), não por uma cadeia única

**Data:** 05/10/2026
**Status:** Aceito
**Etapa:** Pós-lançamento, achado de uso (ver diários 0041 e 0042)
**Supersede:** — (revisa o ADR-0008 e o ADR-0024, sem substituí-los: a cadeia de fallback continua, agora uma por papel)

---

## Contexto

`settings.cadeia_llm` era uma lista só, usada para quase toda chamada de IA do jogo. Em
produção só existe a chave do Gemini (decisão registrada: grátis, sem cartão), então a lista
se reduzia a um elo: `gemini-3.5-flash`.

Em 05/10/2026 o prólogo falhou em 3 de 6 tentativas. Capturando o corpo do erro e, depois,
lendo o painel de limites da conta (ai.dev/rate-limit), os números do plano gratuito são:

| Modelo | Chamadas/min | Chamadas/dia |
|---|---|---|
| 3.5, 3.6, 3.7, 3.8, 3 e 2.5 Flash | 5 cada | 20 cada |
| 3.5 Flash Lite, 3.1 Flash Lite | 15 cada | 500 cada |
| Gemma 4 (26B, 31B) | 30 | 14.400 (16 mil tokens/min) |

Um turno de jogo faz em média 2,7 chamadas (medido, 32 chamadas em 12 turnos) e pode chegar
a 6 (`agent_max_passos`). Com 20 chamadas por dia, a chave do servidor sustentava cerca de 7
turnos por dia para todos os jogadores, e um turno longo já estourava as 5 por minuto. Além
da cota, o Google devolve 503 ("high demand") com frequência, e com um elo só não havia
"próximo modelo" para onde cair.

O jogo chama IA em sete lugares com necessidades diferentes: o turno (várias chamadas com
ferramentas, a toda hora), a correção do guardrail, o Oráculo da criação, o prólogo, o turno
de morte, os desfechos (epitáfio, capítulo, crônica) e o resumo da memória em segundo plano.

## Decisão

Cada chamada declara um **papel**, e cada papel tem a própria lista de modelos
(`settings.cadeia_volume`, `cadeia_destaque`, `cadeia_fundo`; `llm_client.CADEIAS`):

- **volume** (turno, guardrail, Oráculo): 3.5 Flash Lite primeiro; os Flash de 20/dia como
  reserva; 3.1 Flash Lite por último.
- **destaque** (prólogo, morte, epitáfio, desfecho, crônica): 3.5 Flash, 3.6 Flash e logo o
  3.5 Flash Lite, que é o único com prólogo bom comprovado e cota para repetir; os outros
  Flash ficam depois. O 2.5 Flash respondeu rápido a pedidos mínimos, mas no prólogo deu 1
  resultado válido em 5 (2 descartados na validação, 2 estouros de tempo).
- **fundo** (resumo da memória): 3.1 Flash Lite, depois 3.5 Flash Lite.

Junto com os papéis, a cadeia mudou de comportamento diante de erro:

- **Um erro transitório pausa o modelo e a fila segue, sem repetir no mesmo modelo.** 503 pausa
  3 minutos, tempo estourado 1 minuto, cota do minuto até 2 minutos, cota do dia 15 minutos.
  Antes havia um retry curto no mesmo modelo (ADR-0008); ele continua só onde não há fila:
  chave própria do jogador e modelo fixo das avaliações.
- **Se a fila inteira estiver pausada, os pausados por sobrecarga são tentados mesmo assim.**
  Os pausados por cota não.
- **Cada chamada tem tempo limite por papel** (`settings.timeouts_ia`: 25 s no volume, 50 s no
  destaque, 30 s no fundo). Antes valia o padrão da biblioteca, 10 minutos.
- **O servidor conta as próprias chamadas por modelo** (no último minuto e no dia) contra os
  limites da tabela acima (`settings.limites_ia`) e tira da frente da fila o modelo que
  chegou ao limite, sem gastar uma chamada para descobrir. Conta a tentativa, não só o
  sucesso. O dia vira à meia-noite do Pacífico, como a cota do Gemini.
- **A chave própria do jogador (BYOK) percorre as mesmas listas**, só os elos do Gemini, com
  a chave dele. Antes usava o `gemini-3.5-flash` fixo: 20 chamadas por dia numa chave
  gratuita. Nunca cai para outro provedor nem para a chave do servidor. Chave recusada
  (401/403) encerra no primeiro modelo. Como o cliente da chave do jogador é criado a cada
  chamada (para a chave não ficar guardada), as pausas e contagens dele ficam numa conta
  identificada pelo hash SHA-256 da chave, no máximo 256 contas em memória.
- **A fila inteira tem prazo por papel** (`settings.prazos_ia`: 45 s no volume, 90 s no
  destaque, 60 s no fundo). Só com o limite por chamada, um prólogo levou 201 s ao vivo: seis
  modelos falharam em sequência. Acabou o prazo, a chamada falha e quem chamou usa a sua saída
  de emergência (texto de reserva no prólogo, turno só com o juiz).

## Alternativas consideradas

| Alternativa | A favor | Contra | Por que não |
|---|---|---|---|
| Manter uma cadeia só, com mais modelos Gemini | Mudança de uma linha | O prólogo disputaria o Lite com os turnos, ou os turnos gastariam os 20/dia do Flash primeiro | Não separa o que é frequente do que é raro, que é justamente onde as cotas diferem |
| Ativar cobrança no Gemini | Resolve cota e parte dos 503 de uma vez | Exige cartão | Contraria a premissa do projeto (grátis, sem cartão) |
| Groq como reserva em produção | Cota separada, já integrada | Chave tirada de produção de propósito; teto de 8 mil tokens/min | Decisão do autor; segue possível em desenvolvimento (os elos `groq:` ficam no fim das listas e são pulados sem chave) |
| Lite só narra, Flash decide as ferramentas | Melhor acerto de ferramenta | Toda decisão gastaria os 20/dia do Flash | A avaliação mostrou o 3.5 Flash Lite chamando ferramentas de forma válida em 100% dos casos; não foi preciso |
| Gemma 4 para o resumo | 14.400 chamadas/dia | 16 mil tokens/min; suporte a JSON forçado não verificado | Fica como experimento; o resumo é raro (1 a cada 8 turnos) e cabe no Lite |

## Consequências

**Ganhamos:**
- Capacidade estimada de ~185 turnos por dia (500 ÷ 2,7) e ~5 por minuto, contra ~7 por dia.
- O 503 passa a ter para onde cair dentro do mesmo provedor.
- Os textos lidos com mais atenção ficam com o modelo melhor, sem competir por cota com os turnos.
- Uma linha de log por chamada atendida (`ia papel=… modelo=…`), que permite medir chamadas por turno.

**Pagamos:**
- O turno é narrado por um modelo menor. Na avaliação (12 cenários), o 3.5 Flash Lite fez
  0,74 de pontuação agregada; a referência de agosto era 0,82, medida com outros cenários e
  na Groq, então a comparação é só de ordem de grandeza. Ele também usa negrito, que a bíblia
  proíbe, e num cenário narrou um ataque sem resolver o golpe.
- O 3.1 Flash Lite é fraco: caiu numa injeção de prompt, deixou 2 turnos sem narração e
  devolveu 503 em 12 de 30 chamadas. Por isso fica no fim da lista de volume.
- Três listas para manter, e nomes de modelo e cotas gratuitas que mudam sem aviso.
- A voz pode mudar entre o prólogo (Flash) e os turnos (Lite).

**Fica em aberto:**
- O contador é uma estimativa local: zera quando o processo reinicia (o Render gratuito
  hiberna e reinicia) e não enxerga outro processo com a mesma chave, como o ambiente de
  desenvolvimento. Por isso ele só reordena a fila; se tirar todos os modelos, eles são
  tentados mesmo assim e o 429 do provedor decide. Persistir a contagem no banco resolveria
  o reinício, ao custo de uma escrita por chamada.
- A pausa de cota diária é de 15 minutos, não as "11 horas" que o corpo do erro anunciou: o
  mesmo modelo voltou a responder cerca de uma hora depois, então o número do Google não é
  confiável.
- Há relatos no fórum do Google (23 a 29/09/2026) de que um 503 gasta a cota diária do plano
  gratuito. O Google não confirmou nem negou. A pausa de 3 minutos parte dessa hipótese.
- `settings.esforco_raciocinio` existe e está vazio. Medido: o 3.5 Flash Lite não "pensa" por
  padrão (tokens de saída = tokens visíveis), então `minimal` não muda nada e `low` só
  acrescenta raciocínio. Nos Flash a latência variou de 10 a 20 s por chamada com e sem o
  parâmetro; a amostra (2 chamadas em cada) não permite concluir.
- Com a chave própria, um 400 (pedido recusado) ainda percorre a fila inteira antes de virar
  erro: até 7 chamadas para um problema que provavelmente é igual em todos os modelos. Não
  parei no primeiro porque um 400 também pode ser específico de um modelo.
- `teto_turnos_conta` (20) e `teto_turnos_convidado` (8) não foram recalibrados.
- Sondagem de 05/10/2026, 3 chamadas mínimas em cada: 3.6 e 2.5 Flash responderam as 3 (até
  4 s e menos de 1 s); 3.7 falhou 1 e levou 13 s nas outras; 3.8 devolveu 503 nas 3; o 3 Flash
  (preview) levou 293 s numa delas e ficou fora das listas. Num turno com ferramentas, 3.6 e
  2.5 chamaram `rolar_teste` certo, mas levaram 10 a 20 s por chamada: servem de reserva, não
  de modelo principal do turno. Essa ordem é de um dia só e pode mudar.
- Não há medição do 3.5 Flash nos mesmos 12 cenários (a cota de 20/dia não cobre a suíte).

## Como saber que erramos

- Se o log mostrar mais de 3,5 chamadas por turno em média, a capacidade real fica abaixo de
  140 turnos por dia e a conta precisa ser refeita.
- Se jogadores reclamarem de ações narradas sem efeito (golpe que não acontece, item que não
  entra), o Lite está pulando ferramenta e vale testar "Flash decide, Lite narra".
- Se o painel de limites mostrar outro RPD para o Flash Lite, as listas mudam: elas são
  variáveis de ambiente (`CADEIA_VOLUME` etc.) justamente para isso.

## Referências

- [Diário 0041](../diario/0041-prologo-sob-medida.md) e [Diário 0042](../diario/0042-um-modelo-por-papel.md)
- [ADR-0008](0008-cadeia-de-fallback-de-modelo.md), [ADR-0024](0024-cadeia-multi-provedor-groq-gemini.md)
- Painel de limites da conta: https://ai.dev/rate-limit (os números acima são de 05/10/2026)
- Fórum Google AI: [503 no plano gratuito](https://discuss.ai.google.dev/t/repeated-503-unavailable-on-free-tier-including-a-tiny-text-only-generatecontent-request-from-apps-script/185898),
  [503 gastando a cota diária](https://discuss.ai.google.dev/t/gemini-api-503-errors-appear-to-consume-free-tier-rpd-leading-to-429-quota-exhaustion/184644)
- [Rate limits](https://ai.google.dev/gemini-api/docs/rate-limits): limites por projeto, "não garantidos", cota diária zera à meia-noite do Pacífico
