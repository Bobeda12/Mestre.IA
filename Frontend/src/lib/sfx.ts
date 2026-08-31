import { useRef, useState } from 'react';

// Fase 4 do remaster UX (PLANO_REMASTER_UX.md) — efeitos sonoros curtos,
// irmão mais simples de `useTrilha` (mesma pasta, mesmo padrão de
// mudo/localStorage). Sem crossfade nem loop: cada `tocar()` cria um
// `<audio>` novo e descartável — sons curtos podem se sobrepor (dois
// ataques em sequência rápida não precisam esperar um terminar o outro),
// o que a trilha de fundo (um elemento reaproveitado) não permite.
export type EfeitoSonoro = 'dado' | 'item' | 'levelup' | 'golpe';

const ARQUIVOS: Record<EfeitoSonoro, string> = {
  dado: '/assets/audio/sfx/dado.flac',
  item: '/assets/audio/sfx/item.wav',
  levelup: '/assets/audio/sfx/levelup.wav',
  golpe: '/assets/audio/sfx/golpe.ogg',
};

const CHAVE_MUDO = 'mestre_ia_sfx_mudo';
// Mais discreto que a trilha (que já preenche o volume "de música"): efeito
// tocando junto da trilha não devia disputar espaço com ela.
const VOLUME_SFX = 0.55;

function lerMudoInicial(): boolean {
  // Mesma filosofia de `useTrilha`: começar mudo é o padrão defensável até
  // a pessoa mexer no interruptor uma vez.
  const salvo = localStorage.getItem(CHAVE_MUDO);
  return salvo === null ? true : salvo === '1';
}

export function useSfx() {
  const [mudo, setMudoState] = useState(lerMudoInicial);
  const mudoRef = useRef(mudo);
  mudoRef.current = mudo;

  const setMudo = (valor: boolean) => {
    setMudoState(valor);
    localStorage.setItem(CHAVE_MUDO, valor ? '1' : '0');
  };

  // Autoplay bloqueado até o primeiro gesto real do usuário, igual à
  // trilha — `.play()` falhando em silêncio antes disso é esperado, não um
  // bug pra tratar.
  const tocar = (efeito: EfeitoSonoro) => {
    if (mudoRef.current) return;
    const audio = new Audio(ARQUIVOS[efeito]);
    audio.volume = VOLUME_SFX;
    audio.play().catch(() => {});
  };

  return { mudo, alternarMudo: () => setMudo(!mudoRef.current), tocar };
}
