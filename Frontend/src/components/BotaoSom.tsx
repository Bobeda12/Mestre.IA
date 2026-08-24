import { useTrilha, type TemaMusical } from '../lib/trilha';
import PixelIcon from './PixelIcon';

// Revisão da Etapa 14 — a trilha só tocava DENTRO do jogo (GameChat). Tela
// inicial e criação de personagem ficavam mudas, que é justamente onde a
// pessoa passa os primeiros minutos.
//
// Sobre "a música não sai": ela começa MUDA de propósito (ver `lerMudoInicial`
// em lib/trilha.ts) e o navegador bloqueia autoplay sem gesto do usuário de
// qualquer forma. Por isso o controle aqui é rotulado com texto e não só um
// ícone de 18px escondido num canto: era possível jogar a sessão inteira sem
// perceber que existia som. A escolha fica salva em `localStorage`, então
// desmutar uma vez vale pra todas as telas.
export default function BotaoSom({
  tema = 'aventura',
  className = '',
}: {
  tema?: TemaMusical;
  className?: string;
}) {
  const { mudo, alternarMudo } = useTrilha(tema);
  return (
    <button
      onClick={alternarMudo}
      aria-pressed={!mudo}
      aria-label={mudo ? 'Ativar música' : 'Silenciar música'}
      className={`flex items-center gap-2 px-2 py-1 border-2 border-gray-700 bg-black/60 text-gray-300 hover:text-rpg-gold hover:border-rpg-gold transition-colors font-rpg text-xs focus-visible:outline-none focus-visible:border-rpg-gold ${className}`}
    >
      <PixelIcon name={mudo ? 'som-mudo' : 'som-ligado'} size={14} />
      {mudo ? 'Som' : 'Som'}
    </button>
  );
}
