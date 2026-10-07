# Trilha e Combate v2, Fase 7: a tela de combate

**Período:** 06/10/2026 · continuação do diário 0051

## O problema

As Fases 4 a 6 mudaram o combate inteiro no servidor, mas a tela continuava a antiga: sem
fila, sem distância, sem botão de mover nem de encerrar turno, sem a prosa da rodada. Uma
luta com o turno aberto ficava sem saída pela tela.

## O que mudou na tela

**No dock (a barra de ações), em combate:**

- **Fila de turnos:** "VEZ DE Lia › Dara › Lobo", com quem age agora em destaque e quem
  caiu ou fugiu riscado.
- **O que resta do turno:** "● Ação ● Bônus ● Movimento". O que já foi gasto aparece
  riscado, e só os botões daquela parte travam.
- **Encerrar turno:** sempre visível, ao lado. Fica em destaque quando a ação já foi usada.
- **Mover ▾:** Aproximar do alvo, Recuar e, quando o herói está no chão, Levantar. Cada
  opção explica por que está travada ("O alvo já está perto.").
- **Itens:** poção trava quando a ação bônus foi usada, não quando a ação foi.
- **Atacar:** trava, com explicação, quando a arma é de corpo a corpo, o alvo está longe e
  o movimento já foi gasto. Para isso o servidor passou a informar o alcance do ataque do
  herói.
- **O campo de texto vira o Improvisar.** Em combate, o que o jogador escreve não vai mais
  para o chat: vai como improviso, julgado pela IA e rolado pelo servidor.

**No palco:**

- Cada inimigo tem a etiqueta **PERTO** ou **LONGE**.
- As condições do herói aparecem embaixo dele, com a duração ("envenenado · 2").
- O botão do aliado virou **COMANDAR**, e a etiqueta dele mostra quem ele mira.

**No log:**

- Depois que o turno fecha, a tela pede a prosa daquela rodada e a mostra como fala do
  Mestre. Se a IA não responder, aparece um aviso discreto, uma vez por sessão.
- As linhas do juiz que já viraram card de rolagem ("d20(16)+5=21 vs CA 13") não se repetem
  mais como texto. Ficam só as que não têm card: avanços, condições, saque.
- Ao recarregar a página, a prosa gravada volta junto com a rodada.

## Três coisas que só apareceram no navegador

1. **A fila cobria o herói no celular.** A primeira versão punha a fila dentro do selo do
   palco. No celular ela cobria o herói e o aliado, e sumia com o palco recolhido. Foi para
   o dock, que é onde o jogador decide.
2. **"Encerrar turno" ficava fora da tela no celular.** A fileira de botões rola para o
   lado, e o botão era o último. Ele e os marcadores do turno ganharam uma barra própria,
   sempre visível.
3. **A fileira carregava rolada, com "Atacar" escondido.** No celular, ao entrar em
   combate, a fileira aparecia parada no meio. Agora ela volta ao início a cada turno. Não
   descobri a causa de fundo (suspeito do "encaixe" de rolagem do CSS quando o conteúdo
   muda); o conserto trata o sintoma.

Nenhuma das três aparecia nos testes automáticos.

## Como foi verificado

**Testes.** 11 novos: 8 do dock em combate (marcadores do turno, travas por parte,
aproximar, recuar, levantar, poção como bônus, Atacar fora de alcance, campo de texto
como improviso) e 3 da fila. Frontend: 84 testes e tipos sem erro. Backend: 901.

**Uma luta inteira no navegador**, com servidor e IA reais, contra um Lobo, com uma aliada:

| Jogada | O que aconteceu |
|---|---|
| Comandar Dara | Bônus marcado como usado; etiqueta da aliada virou "MIRA LOBO"; turno continuou |
| Atacar Lobo | O herói avançou sozinho e acertou; o turno fechou; Dara e o Lobo agiram; rodada 2 |
| Texto: "Chuto terra nos olhos do lobo" | Foi como improviso; o dado falhou; a prosa narrou a falha |
| Mover → Recuar | O Lobo usou o ataque de oportunidade e errou; etiqueta virou LONGE |
| (Atacar) | Travado, com a dica "Lobo está longe e você já se moveu neste turno." |
| Encerrar turno | Dara errou, o Lobo acertou Dara; rodada 4 |
| Atacar Lobo | O herói errou, Dara derrubou o Lobo; vitória, saque, nível 2; a tela voltou à exploração |

As quatro rodadas fechadas receberam prosa da IA. Conferi a última contra o que o servidor
gravou: a prosa dizia que o herói errou e Dara derrubou o lobo, e era isso mesmo.

**No celular (375 px):** sem rolagem lateral da página, fila e "Encerrar turno" visíveis,
"Atacar" como primeiro botão.

## O que não foi verificado ou ficou pendente

- **Luta com vários inimigos, com chefe e com o herói caído** no navegador. Só os testes
  automáticos cobrem.
- **Captura de tela em tela larga da versão final.** O painel do navegador estava oculto
  no fim da sessão; a verificação em tela larga foi pelo conteúdo da página. No celular há
  captura.
- **O servidor ainda aceita texto livre em combate pelo chat.** A tela não manda mais, mas
  a rota continua aberta. Fechar e tirar as ferramentas de combate do narrador mexe em
  muitos testes antigos; fica com a remoção do motor antigo, na Fase 9.
- **O aviso de "crie uma conta" do convidado cobre parte do dock no celular** até ser
  fechado. Já era assim; agora cobre os botões de combate.
- **O selo do palco cobre a etiqueta dos personagens da esquerda no celular.** Também já
  era assim.
- **O palco recolhido** não mostra distância.
