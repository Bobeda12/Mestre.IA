# Lugares transformados pela jornada

Uma melhoria física pode nascer de um projeto concluído no local atual. A IA propõe nome, descrição e uso, vinculando uma condição com evidência já realizada em lugar ou objeto existente. O jogador inaugura pela Jornada. Cada projeto sustenta uma instalação; há até trinta por campanha. A inauguração não cobra recursos nem concede itens.

## Efeitos desta etapa

- Abrigo: habilita descanso longo mesmo em local gerado. Mantém recuperação, oito horas de passagem do tempo, intervalo entre descansos e avanço dos conflitos existentes.
- Oficina: preparar custa uma ação e uma hora de jogo. Concede +1 no próximo `resolver_intencao` do atributo definido, consumido em sucesso ou falha. Dura 24 horas após a preparação, acompanha o jogador em viagens e não acumula com outra preparação. Pode coexistir com aprendizados, cujos limites permanecem. Propostas de ação inválidas não consomem a preparação.

São efeitos do servidor. A IA não determina valores de bônus, custos, cura ou duração. A coerência entre evidência e tipo de instalação ainda depende da avaliação semântica do narrador; concluir um feito qualquer não justifica automaticamente criar uma oficina.

A instalação só funciona enquanto a evidência estiver nas condições do alvo e o lugar estiver acessível. Bloqueio, destruição ou remoção do objeto impede o uso, preservando o registro da conquista. Restaurar as condições permite voltar a usar. Não há manutenção, perda aleatória ou destruição automática de conquistas.

O painel mostra locais transformados, disponibilidade e preparação atual. O grupo `instalacoes` fica sob demanda e os registros usam o orçamento de contexto existente. Saves antigos recebem instalações vazias e nenhuma preparação. Não há chamada extra de IA para usar os serviços.

Esta etapa entrega serviços utilizáveis em lugares persistentes; não implementa editor visual de bases, estoques, produção passiva ou economia regional.
