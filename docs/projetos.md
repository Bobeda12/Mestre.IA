# Projetos livres — primeiro ciclo

Na Jornada, o jogador escolhe uma ambição em texto livre. Há um projeto ativo por vez e até 30 registros por campanha. Iniciar, concluir e abandonar são decisões exclusivas do jogador, bloqueadas em combate ou inconsciência. Não gastam recursos nem concedem recompensas automáticas.

O narrador carrega o grupo `projetos` por demanda. `planejar_projeto` define de uma a cinco condições de resultado em alvos presentes. Não há catálogo de ambições, ordem de etapas nem meios obrigatórios. O plano é preservado após registrado; o jogador pode superar uma exigência por um caminho alternativo.

`registrar_avanco_projeto` associa uma condição a um acontecimento bem-sucedido e a um texto exato de condição persistente do mesmo alvo, produzido pela ação. A mera narração ou promessa não registra avanço. `resolver_intencao` já permite produzir essas mudanças com meios livres. O motor valida a existência da evidência; sua pertinência semântica à ambição continua dependendo da IA.

O jogador só pode concluir quando todas as condições estiverem satisfeitas ou superadas. A evidência fica copiada no projeto, sobrevivendo à retenção limitada do histórico de acontecimentos. Abandonar preserva essas mudanças e libera outra ambição; concluir deixa a conquista registrada. O sistema não desfaz conquistas ao viajar ou iniciar outro projeto.

Projetos ativos têm prioridade dentro do orçamento existente de contexto. O arquivo completo permanece consultável. Saves antigos recebem uma coleção vazia; a criação inicial da campanha remove projetos inventados como se já tivessem sido escolhidos pelo jogador.

## Escopo desta entrega

### Acordos e interesses concorrentes

NPCs presentes podem oferecer apoio com contrapartida e motivo declarado, associados a uma condição aberta. Cada projeto guarda até oito ofertas, com no máximo uma oferta pendente por NPC. Os termos são imutáveis por ID. Conhecimento de ambições distantes exige informação registrada no NPC.

O jogador aceita, recusa ou renuncia na Jornada. Exclusividade impede aceitar propostas concorrentes na mesma condição, inclusive enquanto um compromisso cumprido continuar vigente. Decisões deixam memória no interlocutor e um acontecimento que pode motivar as consequências já existentes. Recusar ou renunciar não produz punição numérica arbitrária. Compromissos persistem após concluir ou abandonar o projeto, e podem ser renunciados em conversa com o NPC.

Aceitar não entrega itens nem conclui condições. Registrar uma contrapartida cumprida exige evidência de ação bem-sucedida e condição persistente no alvo. A IA ainda interpreta se a evidência atende semanticamente à promessa e se a oferta cabe nos recursos do NPC; esta versão não simula estoques de patrocinadores. Organizações registradas podem ser representadas nas ofertas; o motor valida a filiação do NPC.

O grupo `acordos` é carregado sob demanda. Seus registros são separados do projeto na seleção de contexto para que várias propostas não façam a ambição inteira exceder o orçamento. Somente motivos declarados devem entrar nas propostas públicas, nunca segredos dos NPCs.

Implementa escolha → condições geradas → mudança executada → evidência persistente → conclusão pelo jogador, integrado à API e à Jornada. Usa pessoas, condições e consequências já existentes para a ficção. Organizações e iniciativas por relógio estão descritas em [Organizações](organizacoes.md). Projetos concluídos podem sustentar [abrigos e oficinas](instalacoes.md). Economia regional e construção visual de bases permanecem fora do escopo atual.
