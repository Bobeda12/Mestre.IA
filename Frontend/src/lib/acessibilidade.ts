import { useEffect, useState } from 'react';

// Rodada de conserto — achado ao vivo: `index.css` já desliga toda
// `animation`/`transition` via CSS quando o sistema operacional pede menos
// movimento (@media prefers-reduced-motion), mas isso só mata a ANIMAÇÃO.
// Qualquer `setTimeout` em JS que existisse só para esperar a animação
// terminar (o "fator cassino" do dado em RollCard.tsx, GameChat.tsx) continua
// esperando do mesmo jeito — o efeito prático é o dado não girar E a
// narração parecer travar meio segundo à toa. Este hook deixa o código em
// JS saber da mesma preferência que o CSS já respeita, pra pular a espera
// também, não só a animação.
export function prefereMovimentoReduzido(): boolean {
  if (typeof window === 'undefined' || !window.matchMedia) return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

export function useMovimentoReduzido(): boolean {
  const [reduzido, setReduzido] = useState(prefereMovimentoReduzido);
  useEffect(() => {
    const mql = window.matchMedia('(prefers-reduced-motion: reduce)');
    const ouvir = () => setReduzido(mql.matches);
    mql.addEventListener('change', ouvir);
    return () => mql.removeEventListener('change', ouvir);
  }, []);
  return reduzido;
}
