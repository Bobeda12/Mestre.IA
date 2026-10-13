# Texto livre confiável, Fase 4: o jogo recompensa de verdade

**Período:** 07/10/2026 · continuação do diário 0058 · ADR-0047 · relatório 0007

## O que você sentiu, e o que o jogo fazia

Você descreveu um RPG sem graça: loot sem graça, recompensas sem graça, inimigos repetidos,
uma história que não cresce. O relatório que medi na Fase 0 mostrou a causa mais grave:
**do nível 4 em diante, um único encontro já subia de nível.** Um Troll vale 400 XP e faltavam
230. O herói chegava ao nível 10 em cerca de 15 encontros, antes de o mundo acompanhar.

## O que mudou

1. **A curva de XP foi refeita.** O nível 2 pede 150, o 5 pede 2400, o 10 pede 45000. Cada nível
   custa de 3 a 7 encontros típicos. Na simulação, a média ficou entre 2,6 e 5,4 por nível.
2. **XP de passos, pistas, acordos e capítulos acompanha o nível**, em vez de uma moeda fixa de
   50 que valia nada no nível 8.
3. **Itens encantados.** Dez armas (+1 a +3) e cinco peças de armadura e escudo com CA maior.
   O bônus vale para acertar e para o dano, e o card do ataque mostra "Arma encantada".
   Eles caem em saques das bandas médias (8% a 18%), nos chefes (60%) e sempre no chefe de
   elite, e aparecem como recompensa de capítulo.
4. **Ouro tem para onde ir.** Itens encantados custam de 120 a 5000 moedas e entram no
   catálogo, então um comerciante pode vendê-los. Com isso o ouro de 1900 moedas do nível 10
   deixa de ser só um número.
5. **Final de campanha.** Derrotar um chefe de elite como chefe de um capítulo, com o herói
   no nível 8 ou mais, marca a campanha como concluída. O mundo continua, em modo pós-jogo.

## Medido

- 9 testes novos: encantados existem no catálogo; a arma encantada soma +1 no dano; chefe de
  elite sempre deixa um; banda comum quase nunca; arco alto pode trazer; armadura encantada vale
  mais CA; campanha conclui com chefe de elite e herói forte, e não conclui com chefe comum ou
  herói fraco. Backend completo: 972 passando.
- Simulação "depois" no relatório 0007.

## Não resolvido

- **Sem sumidouro dedicado** (estalagem, treino, conserto). Decidi não criar uma ferramenta
  nova porque o prompt de entrada está rente ao teto do provedor (15479 de 16000 caracteres).
- **Sem arte** para os encantados nem tela de raridade; o nome já mostra o "+N".
- **A história que cresce** só ganhou o final de campanha e os lugares revelados por capítulo.
  Arcos que carregam consequência de um para o outro seguem pelos marcos, sem mecânica nova.
- **Um custo que você deve saber:** o limite de 20 turnos por dia por conta agora pesa mais,
  porque chegar ao nível 10 pede cerca de 47 encontros.
- Saves antigos mantêm o nível, mas o próximo nível fica mais caro.

## Um tropeço

Os cinco testes que falharam depois da nova curva tinham "100 XP" escrito direto no teste. Em
vez de trocar para 150, mudei os que dava para ler a tabela, para o teste não quebrar da próxima
vez que a curva mexer.
