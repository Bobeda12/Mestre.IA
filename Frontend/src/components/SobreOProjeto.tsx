// Aviso para quem chega: o que é este jogo, por que o limite existe e o que muda
// ao criar uma conta ou trazer a própria chave. Fica na tela de entrada porque é
// lá que a pessoa decide entre jogar como convidada, criar conta ou entrar com
// Google (quem clica em "Novo jogo" sem estar logado cai aqui).
interface Props {
  turnosPorDia?: { convidado: number; conta: number };
}

export default function SobreOProjeto({ turnosPorDia }: Props) {
  const convidado = turnosPorDia?.convidado;
  const conta = turnosPorDia?.conta;

  return (
    <div className="w-full mb-5 border-2 border-rpg-gold/60 bg-black/60 p-3 text-left">
      <h2 className="font-pixel-title text-[10px] text-rpg-gold mb-2 leading-relaxed">
        PROTOTIPO GRATIS
      </h2>
      <p className="text-xs text-gray-300 leading-relaxed font-rpg">
        Mestre.IA é um protótipo, feito sem gastar dinheiro. A IA roda em cotas gratuitas, então o
        jogo pode ser lento e o limite de cada dia é pequeno.
      </p>
      <ul className="mt-2 space-y-1.5 text-xs text-gray-300 leading-relaxed font-rpg">
        <li>
          <strong className="text-white">Convidado:</strong>{' '}
          {convidado ? `${convidado} turnos por dia` : 'poucos turnos por dia'} e o herói só existe
          neste navegador.
        </li>
        <li>
          <strong className="text-white">Com conta:</strong>{' '}
          {conta ? `${conta} turnos por dia` : 'mais turnos por dia'} e seus heróis ficam salvos.
          Vale a pena criar uma.
        </li>
        <li>
          <strong className="text-rpg-gold">Com a sua chave grátis do Gemini:</strong> sem o limite do
          servidor, porque você usa a sua própria cota. Crie em{' '}
          <a
            href="https://aistudio.google.com/apikey"
            target="_blank"
            rel="noreferrer"
            className="text-rpg-gold underline hover:text-white"
          >
            aistudio.google.com/apikey
          </a>{' '}
          (leva um minuto) e cole em Opções.
        </li>
      </ul>
    </div>
  );
}
