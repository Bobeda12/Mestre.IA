# Contexto eficiente do Mestre

O objetivo é acesso ao arquivo da campanha sem reenviar esse arquivo inteiro em
cada chamada. O estado continua sendo a fonte de verdade; a seleção nunca apaga o save.

## Diagnóstico e medição

`uv run python scripts/auditar_contexto.py` roda dois cenários determinísticos sem
API de IA nem acesso aos saves reais. O cenário longo acrescenta 220 frases ao
resumo e 100 registros de conhecimento. A comparação mede prompt e schemas,
antes do histórico recente, ação do usuário e resultados de ferramentas.

| Cenário | Caracteres antes | Caracteres depois | Redução |
|---|---:|---:|---:|
| Início de campanha | 32.095 | 15.808 | 51% |
| Campanha longa | 48.579 | 16.949 | 65% |

São caracteres, não tokens faturados. A estimativa de controle usa um token a
cada três caracteres de JSON compacto: aproximadamente 5.270 e 5.650 tokens nos
cenários novos. O tokenizer, os schemas internos e a resposta do provedor podem
produzir números diferentes. Estes resultados não medem a qualidade da narração
de um modelo real nem a economia total de um turno com várias chamadas.

## Caminho de uma ação

- `montar_contexto` envia instruções consolidadas, estado atual e recortes de memória.
  Resumos são selecionados por relevância lexical/recência, por frases inteiras,
  com orçamento por seção. O resumo completo fica armazenado.
- `contexto_mundo` seleciona registros inteiros com prioridade para o local,
  condições, personalidade, particularidades e conflitos. Limites e segredos de
  um registro incluído não são cortados em 160 caracteres como antes. Quando um
  registro não cabe, sua ausência é sinalizada e a consulta continua disponível.
- `tools_para` começa com as ferramentas essenciais e acrescenta grupos conforme
  a ação e o combate. Uma observação simples começa com quatro ferramentas em vez
  de 29; palavras-chave são uma antecipação, não um limite de capacidades.
- `consultar_contexto` busca o mundo, histórico completo, resumo e regras por
  palavras; `registro` lê uma referência exata. As referências `estado/heroi`,
  `estado/combate`, `estado/missoes` e `estado/viagem_progressao` dão acesso aos
  demais dados da campanha. Conteúdo extenso é paginado com indicação de continuação.
- A mesma consulta carrega grupos de ferramentas. O loop adiciona somente schemas
  conhecidos e permitidos naquele estado; não aceita schemas fornecidos pelo
  modelo nem executa ferramentas ainda não habilitadas. Escolhas exclusivas do
  jogador continuam fora do catálogo oferecido.
- Uma consulta com texto provisório não encerra o loop: a IA recebe a resposta
  antes de narrar o desfecho. Erros de ferramenta dão oportunidade de correção.

O acesso é privado ao Mestre e restrito ao personagem do executor. Saber algo no
arquivo não significa que um NPC ou o herói conheça esse fato. A busca sob demanda
é lexical e pode exigir reformular palavras; a recuperação automática inicial
continua usando busca híbrida. Não há garantia de memória perfeita.

## Controle de consumo e falhas

`AGENT_LIMITE_ENTRADA_ESTIMADO` (12.000) limita a estimativa de entrada de uma chamada;
`AGENT_LIMITE_TURNO_ESTIMADO` (24.000) limita a soma antes das chamadas do loop.
`AGENT_MAX_PASSOS` também é respeitado. Os limites são configuráveis e registrados
em log como estimativas, separando mensagens e schemas. São controles do loop,
não limites de faturamento: saída, tentativas do SDK/fallback e outras chamadas
(como prólogos e resumo) não entram nessa soma. Eles não substituem as cotas do provedor.

O histórico recente tem orçamento de caracteres. Resultados grandes de ferramentas
preservam campos mecânicos essenciais e indicam detalhes omitidos. O resumo rolante
também deixa de reenviar todo o resumo acumulado na chamada que produz o próximo delta.

Memória e regras reutilizam o embedding da mesma consulta dentro do request. O
cache não é compartilhado entre jogadores nem ligado ao cache dos documentos de
regras, que permanece estável. Isso evita duas chamadas iguais de embedding quando
os dois caminhos precisam do vetor.

429 não é repetido imediatamente no mesmo modelo: o fallback segue para o próximo.
Clientes do servidor recebem uma pausa por modelo, respeitando Retry-After numérico
entre 1 e 120 segundos (padrão: 30). Não há espera bloqueante; outras instâncias de
cliente são independentes. A pausa é local ao processo, não distribuída e não
compartilhada por chaves BYOK criadas por chamadas distintas. Timeout/conexão/5xx
mantêm retry curto; streaming já iniciado nunca troca de modelo silenciosamente.

## Próxima avaliação

Antes de afirmar melhora narrativa em produção, medir modelos reais nos mesmos
casos: recordação de promessa antiga, preservação de limite de NPC, pista privada,
ação inédita, ferramenta carregada sob demanda e combate. Comparar acerto factual,
chamadas por turno, tokens reais, latência e frequência de 429. Consultas adicionais
têm custo e latência: uma redução no primeiro prompt não garante economia em todo turno.
