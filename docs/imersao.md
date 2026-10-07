# Descoberta, convivência e identidade

> **Sem painel desde 07/10/2026** (ADR-0039). A aba Jornada virou a trilha do capítulo e marcas e momentos saíram da tela (os sinais da cena continuam). O sistema continua funcionando no servidor e no contexto do narrador; o jogador mexe nele conversando com o mestre. As menções a botões e seções da Jornada abaixo descrevem a tela antiga.

O conteúdo continua sendo criado pela IA a partir da campanha. Não há catálogo de cenas pessoais, apelidos ou soluções de enigmas.

- Particularidades aceitam até quatro pistas alternativas em fontes presentes. A regra e as pistas ficam fixadas no registro; a interface só recebe pistas descobertas. `resolver_intencao` usa o efeito `pista` com o ID da particularidade em `alvo` e o ID da pista em `texto`. Uma dedução coerente pode usar `revelar` sem completar uma sequência.
- NPCs têm hábito e voz persistentes. `registrar_momento` cria um gesto ou convite ligado a um acontecimento real, com NPC presente e sem combate. Não aceita convites pelo jogador, não cria promessas e não aumenta confiança. Há intervalo de três turnos e a mesma experiência não gera momentos repetidos.
- `registrar_marca` guarda apelidos atribuídos, vínculos observados, feitos e significado de objetos possuídos. Exige acontecimento existente; objetos precisam estar no inventário. Marcas não concedem atributos, itens nem sentimentos ao herói.
- `apresentar_oportunidades` mostra até três percepções com riscos em alvos presentes. O painel recolhível acima das ações permite consultá-las sem impor opções de solução. Expiram após dois turnos; ações removem sinais de alvos ausentes.
- O ritmo considera combate, tentativas frustradas, vitória, descanso e momentos pessoais. Sugere descoberta, tensão, respiro, convívio ou escuta. Não suspende relógios, perigos ou decisões.

Pistas descobertas, marcas e momentos aparecem na Jornada. Hábitos e voz aparecem em Relações. Saves antigos recebem valores vazios por padrão; a geração inicial não inventa experiências já vividas.

## Custo e limites

O grupo `imersao` é carregado sob demanda, com alguns gatilhos de conversa e investigação. Os novos registros usam a seleção de contexto existente, com orçamento fixo; os demais podem ser recuperados por `consultar_contexto`. O ritmo é calculado localmente. Não há chamada extra obrigatória de IA por turno.

O servidor valida referências, presença, propriedade, repetição e privacidade das pistas estruturadas. A coerência semântica de gestos, apelidos e percepções ainda depende do narrador: uma referência válida não prova que toda a redação gerada é adequada. A qualidade e a diversão precisam de avaliação em partidas; os testes automatizados verificam o comportamento mecânico, sem chamar modelos externos.
