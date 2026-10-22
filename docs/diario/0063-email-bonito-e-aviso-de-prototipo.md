# E-mail com a cara do jogo e um aviso de que é um protótipo

**Período:** 22/10/2026 · continuação do diário 0062

## O que apareceu

O cadastro por e-mail passou a funcionar, mas dois pontos ficaram ruins:

1. **O e-mail de confirmação era feio.** Eu o tinha deixado quase só texto de propósito, para
   não cair em spam. Só que, mandando pelo Gmail de verdade (diário 0062), esse cuidado não
   pesa tanto, e o e-mail destoava do jogo.
2. **Ninguém explicava ao jogador novo por que existe um limite.** O jogo roda em cotas
   gratuitas de IA, então ele é lento e cada dia só cabe um número pequeno de turnos. Quem
   chegava sem saber disso achava que estava quebrado.

## O que mudou

1. **E-mail novo.** Fundo escuro, dourado e pergaminho (as cores do jogo), um botão grande
   "Confirmar meu e-mail", o link por extenso embaixo (para quando o botão não funciona), e
   um rodapé explicando por que a pessoa recebeu a mensagem. Continua sem nenhuma imagem
   (clientes de e-mail costumam bloquear imagens), com a versão em texto puro por garantia.
2. **Aviso "Protótipo grátis" na tela de entrada.** É o melhor lugar: quem clica em "Novo
   jogo" sem estar logado cai ali, e é ali que a pessoa decide entre jogar como convidada,
   criar conta ou entrar com o Google. O texto diz que é um protótipo feito sem gastar
   dinheiro, quantos turnos cada tipo de acesso tem por dia, e que dá para jogar sem o limite
   do servidor usando a própria chave gratuita do Gemini.
3. **Os números do aviso vêm do servidor.** A rota `/auth/opcoes` agora devolve os limites
   diários reais (8 para convidado, 20 para conta). Se eu mudar o limite, o aviso muda sozinho.
4. **Dois textos dentro do jogo ficaram mais claros.** O convite para criar conta agora diz
   o motivo ("seu herói fica salvo e você ganha mais turnos por dia"), e a tela de cota
   esgotada explica que é um protótipo gratuito.
5. **Página de privacidade corrigida.** Faltava dizer que o e-mail de confirmação sai pelo
   Gmail e que, quando a cota do Gemini acaba, o texto das jogadas pode ir a um provedor de
   reserva (Groq). Isso já era verdade em produção, mas o texto só citava o Google.

## Como conferir

`uv run pytest` no `Backend/` e `npm run build` no `Frontend/`. Criar uma conta com um
e-mail seu para ver o e-mail novo; abrir `/entrar` para ver o aviso.
