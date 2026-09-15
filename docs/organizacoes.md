# Organizações e iniciativas coletivas

Grupos são criados pela IA para a campanha, com nome, propósito, princípio público e até cinco NPCs registrados e presentes. Não há facções de catálogo nem filiação automática do jogador. A identidade registrada é preservada. Saves antigos recebem uma coleção vazia.

`mobilizar_organizacao` vincula um acontecimento real a um representante que o conhece. Uma reação por acontecimento e organização, um conflito ativo por representante e no máximo duas iniciativas simultâneas por organização. Existem até vinte organizações e quarenta conflitos por campanha.

As iniciativas usam o relógio existente, com intervalo mínimo de trinta minutos e pelo menos duas etapas. Tempo de viagem e descanso faz o mundo avançar sem chamada adicional de IA. O sinal público permite antecipar o risco. `intervir_conflito` permite apoiar, atrasar ou negociar; os controles existentes na Jornada atendem também às iniciativas coletivas.

Os efeitos mecânicos desta etapa são os já existentes: bloquear um alvo da cena, afastar o representante ou concretizar uma disputa social registrada. A IA gera motivos, sinais e consequências dentro desses limites. O motor não concede itens, ouro, propriedade ou obrigações pelo texto do desfecho. Um representante ausente ou alvo removido/destruído impede a execução. A mudança persiste ao retornar ao local.

O painel mostra iniciativas do local atual, evitando notícias instantâneas de lugares distantes. Organizações e representantes conhecidos aparecem na Jornada. Ofertas de projeto podem indicar a organização representada, com validação de filiação. A decisão de aceitar continua sendo exclusivamente do jogador.

As ferramentas ficam no grupo `organizacoes`, carregado sob demanda. Os registros usam o orçamento de contexto existente. Os testes não chamam modelos externos: verificam relógios, intervenção, persistência, presença, causalidade e representação. A adequação dos motivos e a coerência de recursos declarados ainda dependem da IA.

Esta etapa não implementa economia regional, estoques de facção, mapas de território, guerras ou tomada automática de bases. Abre o ciclo de ação coletiva usando pessoas e conflitos já jogáveis.
