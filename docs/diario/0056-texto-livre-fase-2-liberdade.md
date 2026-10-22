# Texto livre confiável, Fase 2: liberdade

**Período:** 07/10/2026 · continuação do diário 0055 · ADR-0044

## O que você queria, nas suas palavras

Se o objetivo é salvar o mundo de goblins e o personagem fica nadando num lago para sempre,
o jogo tem de **deixar**, e o mundo tem de **se adaptar**. Se o que ele tenta é literalmente
impossível (acender fogo no fundo do mar), ele só tenta e não consegue, numa narração do
Mestre. Se for muito difícil, vale uma CD mais alta.

## Um mal-entendido meu

Li "ações absurdas" como "ações impossíveis" e comecei a construir uma regra com dano
automático para quem falhasse. Você me corrigiu: o caso era "fora do rumo", não "fora das
leis do mundo". Tirei o dano. Foi bom ter perguntado antes de ir mais longe.

## O que mudou

1. **O Mestre aceita o desvio.** O texto que o guia diz que o jogador é livre, que o
   relógio e os conflitos seguem, e que o passo da trilha é só uma sugestão. A história
   se adapta ao que o jogador fez em vez de empurrá-lo de volta.
2. **Três tamanhos de dificuldade além dos antigos:**
   - *Muito difícil* (CD 24): possível, mas só com atributo alto e um dado bom.
   - *Impossível*: sem dado, sem dano, sem mudança no mundo. O Mestre narra a tentativa
     que não deu certo.
3. **Menos erros secos.** Quando o jogador age sobre algo que o mundo ainda não registrou,
   o jogo orienta o modelo a registrar e tentar, em vez de recusar.
4. **A regra mais importante não é mais cortada.** A "Lei da Verossimilhança" (se você
   insulta um rei, ele reage de verdade) estava sendo deixada de fora do prompt por falta
   de espaço. Agora entra sempre.

## O que foi medido

- 4 testes novos em `tests/test_emergencia.py`: impossível não rola nem pune nem muda o mundo;
  comum continua exigindo efeitos; extrema é possível com sorte e bem mais difícil; alvo não
  registrado orienta.
- Backend completo: 929 passando.
- O prompt tem um teto de tamanho por causa do limite de tokens do provedor. Meus acréscimos
  estouraram esse teto (16802 contra 16000), então enxuguei meus textos e reduzi o espaço das
  regras situacionais. Ficou em 15436.

## O que ainda não foi provado

O teste ao vivo: ir nadar num lago durante um arco e ver se o mundo segue; tentar fogo no
fundo do mar e ver se o Mestre escolhe "impossível". Isso depende do modelo e usa a cota
diária do Gemini (20 requisições).
