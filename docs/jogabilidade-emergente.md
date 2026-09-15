# Jogabilidade emergente

A IA interpreta a intenção e cria conteúdo contextual; o motor resolve o teste,
aplica apenas o ramo correspondente e persiste suas consequências. Não há catálogo
de missões novas nem soluções obrigatórias.

## Fluxo implementado

1. `registrar_particularidade` estabelece uma regra singular para uma pessoa,
   objeto ou lugar existente. O registro é aditivo: reapresentar o mesmo ID não
   reescreve sua regra. A interface mostra a pista; a regra privada só aparece após
   um efeito `revelar` ou quando foi originalmente registrada como pública.
2. `resolver_intencao` recebe intenção, abordagem, fundamento, atributo e dois
   conjuntos de efeitos: sucesso e falha. O jogador continua escrevendo no chat;
   não precisa escolher um verbo ou preencher esse contrato.
3. O servidor valida todos os efeitos antes do dado. As dificuldades base são
   10/15/20, ajustadas pelo nível de dificuldade da campanha. A ação consome o
   turno e tempo; em combate provoca a reação inimiga. Uma falha idêntica exige
   mudar o meio, condições ou efeito pretendido para tentar de novo.
4. Toda ação consumida, inclusive os controles antigos, ganha um acontecimento
   persistente com ID. `desenvolver_consequencia` referencia esse ID para registrar
   uma iniciativa motivada de um NPC, com sinal perceptível e prazo.
5. O prazo torna a iniciativa disponível para interpretação; não garante que o
   plano deu certo. O jogador pode interrompê-la por um efeito. A IA pode propor
   outra iniciativa com `substitui`, vinculada a um novo acontecimento, encerrando
   o plano anterior. Agentes não recebem automaticamente notícias de outro local.
6. `propor_aprendizado` oferece uma evolução baseada em pelo menos duas ações
   livres registradas. A escolha é exclusiva da interface Jornada, por
   `/game/action` com `escolher_aprendizado`; o narrador não recebe essa ferramenta.

## Efeitos e limites

Os efeitos combináveis são condições ficcionais persistentes, remoção de condições,
mudanças de confiança/memória, descoberta de informação, revelação de uma
particularidade e encerramento de uma iniciativa. Nenhum deles altera HP, ouro,
inventário, posição ou atributos diretamente: esses sistemas mantêm ferramentas
próprias. Condições informam a interpretação das próximas ações; não equivalem
automaticamente a status de combate como atordoamento ou imunidade.

Uma ação oferece até três efeitos de sucesso e dois de falha; só um ramo é aplicado.
Confiança muda no máximo cinco pontos por pessoa por ação. Aprendizados dão +1
em um atributo contra o alvo associado, com soma limitada a +2; a quantidade ativa
é no máximo `max(1, nivel // 3)`. Para objetos, a aplicação respeita também o local.
Nomes e descrições são gerados pela IA; a força mecânica é definida pelo servidor.

O save guarda os últimos 100 acontecimentos, até 100 particularidades, 60
consequências, 12 ofertas de aprendizado e 12 condições por alvo. O contexto
leva uma seleção recente e os elementos locais, preservando separação entre
informação pública e intenções privadas. Os campos têm defaults: saves antigos
continuam carregando sem migração SQL. A criação de personagem zera os registros
de experiência, impedindo que o prólogo gere aprendizados já adquiridos.

## O que ainda depende do modelo

A coerência semântica de uma proposta — se um argumento respeita o limite de um
NPC, se uma condição combina com uma particularidade, se uma informação foi
realmente descoberta — depende da interpretação da IA orientada pelo contexto.
O motor valida contratos, referências, limites, rolagens, persistência e privacidade;
não demonstra a veracidade de frases em linguagem natural. A qualidade das cenas
geradas precisa de avaliação com modelos reais; os testes automatizados usam
respostas controladas e não consomem API de IA.

## Validação

`Backend/tests/test_emergencia.py` cobre sucesso/falha, efeitos inválidos sem
mutação, repetição, persistência, regras imutáveis, segredos, causas reais,
iniciativas, escolha e bônus de aprendizado, saves antigos e reação de combate.
`test_game_actions.py` cobre a escolha pela API, persistência e reenvio do mesmo
turno. `AbaJornada.test.tsx` cobre a apresentação e o comando de escolha.
