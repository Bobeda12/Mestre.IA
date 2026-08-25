import { useState } from 'react';
import { useTrilha, type TemaMusical } from '../lib/trilha';
import MenuConfiguracao from './MenuConfiguracao';
import PixelIcon from './PixelIcon';

// Engrenagem + menu de opções, empacotados para as telas que não têm trilha
// própria (inicial, login, criação). O jogo NÃO usa este componente: lá o
// `GameChat` já é dono do `useTrilha` (o tema muda conforme o combate) e passa
// os controles direto pro menu.
//
// Essa divisão existe porque `useTrilha` cria um elemento de áudio por
// instância: se este componente fosse usado dentro do jogo, seriam dois
// players tocando a mesma faixa em paralelo. A regra é uma instância por tela.
export default function BotaoConfig({
  tema = 'aventura',
  mostrarVoltar = true,
  className = '',
}: {
  tema?: TemaMusical;
  /** Na própria tela inicial não faz sentido oferecer "voltar ao menu". */
  mostrarVoltar?: boolean;
  className?: string;
}) {
  const [aberto, setAberto] = useState(false);
  const trilha = useTrilha(tema);

  return (
    <>
      <button
        onClick={() => setAberto(true)}
        aria-label="Abrir configurações"
        title="Configurações"
        className={`flex items-center gap-2 px-2 py-1 border-2 border-gray-700 bg-black/60 text-gray-300 hover:text-rpg-gold hover:border-rpg-gold transition-colors font-rpg text-xs focus-visible:outline-none focus-visible:border-rpg-gold ${className}`}
      >
        <PixelIcon name="config" size={14} />
        Opções
      </button>
      <MenuConfiguracao
        aberto={aberto}
        aoFechar={() => setAberto(false)}
        trilha={trilha}
        mostrarVoltar={mostrarVoltar}
      />
    </>
  );
}
