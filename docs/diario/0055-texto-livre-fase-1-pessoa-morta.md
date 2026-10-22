# Texto livre confiável, Fase 1: quem morre, morre de verdade

**Período:** 07/10/2026 · plano "Texto livre confiável e progressão" · ADR-0043

## O que o jogador viu

Você tentou matar um NPC. Ele "morreu" no texto, sem entrar em combate, e depois você
conseguiu conversar com ele. O jogo estava contando duas histórias ao mesmo tempo: a do
texto (ele morreu) e a do servidor (ele está vivo e disponível).

## O que estava errado, em termos simples

- **O servidor não tinha a palavra "morto" para pessoas.** Só inimigos de combate podiam
  morrer. Uma pessoa do mundo podia estar reservada, cooperativa, hostil ou ausente. Sem
  lugar para guardar a morte, ela só existia na narração.
- **"Matar" não acordava o combate.** O jogo liberava as ferramentas de luta só quando o
  texto tinha "atacar", "lutar", "combate" ou "agredir". Com "matar", o modelo recebia só
  as ferramentas de mundo e inventava o desfecho em prosa.
- **Vencer o combate não avisava a pessoa.** Mesmo quando havia luta, o inimigo era só um
  nome parecido com o do NPC, sem ligação de verdade.

## O que mudou

1. **Pessoas podem estar mortas.** Uma pessoa morta não conversa, não vende, não vira
   passo de trilha e não rende XP. O palco a mostra apagada.
2. **O servidor reconhece a violência.** Ele lê o seu texto (matar, esfaquear, degolar,
   atacar...), descobre quem é o alvo e libera a ferramenta de combate, pedindo ao modelo
   para abrir a luta e não descrever o desfecho.
3. **O inimigo guarda de quem ele é.** Na vitória, a pessoa vira "morta" e perde a loja.
   Quem apenas fugiu continua viva.
4. **Uma rede de segurança.** Se o modelo narrar um morto falando, ou matar alguém sem
   luta, a resposta é reescrita antes de chegar a você.

## O que foi medido

- 8 testes novos (`tests/test_morte_de_pessoa.py`): detector de violência (incluindo "mata"
  de floresta, que não deve disparar), vínculo pessoa↔inimigo, morte na vitória, quem recua
  continua vivo, morto não conversa nem vende, guardrail.
- Suíte completa do backend: 925 passando. Frontend: tipos limpos e 40 testes do palco.

## O que ainda não foi provado

Os testes não pegam "o modelo ignora o pedido e narra do mesmo jeito". Falta o **teste ao
vivo**: com Gemini, escrever "mato o NPC", conferir se a luta abre, e depois tentar
conversar. A cota gratuita é de 20 requisições por dia, então isso é feito de propósito e
pouco a pouco. Se o modelo ignorar o pedido com frequência, o próximo passo é o servidor
abrir o combate sozinho (anotado no ADR-0043).

## Um tropeço no caminho

A ferramenta que eu uso para editar arquivos transformou `\b` (limite de palavra em
expressão regular) em um caractere de controle invisível, e `\n` em uma quebra de linha de
verdade dentro de uma string. O primeiro deixou o detector de violência sem funcionar sem
dar erro; o segundo quebrou a importação do módulo, que apareceu logo. Achei o primeiro
testando a regex com frases de exemplo e conferindo os bytes do arquivo.
