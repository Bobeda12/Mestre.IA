import { useEffect, useRef, useState } from 'react';

// Etapa 11 (B-4) — trilha sonora por tema. O tema vem do ESTADO do jogo,
// não do modelo: pedir ao LLM adicionaria latência e uma chance de erro
// para resolver algo que o servidor já sabe (combate ativo, HP baixo,
// game over). Ver docs/backlog-pos-lancamento.md.
export type TemaMusical = 'aventura' | 'combate' | 'suspense' | 'tristeza';

export const FAIXAS: Record<TemaMusical, string> = {
  aventura: '/assets/audio/aventura.ogg',
  combate: '/assets/audio/combate.ogg',
  suspense: '/assets/audio/suspense.ogg',
  tristeza: '/assets/audio/tristeza.ogg',
};

const CHAVE_MUDO = 'mestre_ia_trilha_muda';
const CHAVE_VOLUME = 'mestre_ia_trilha_volume';
const DURACAO_CROSSFADE_MS = 1500;
// Volume padrão quando a pessoa nunca mexeu. Deixar de ser constante foi o
// que permitiu o controle no menu de configuração: antes 0.35 era o único
// volume possível, no código.
const VOLUME_PADRAO = 0.35;

function lerVolumeInicial(): number {
  const salvo = localStorage.getItem(CHAVE_VOLUME);
  const n = salvo === null ? NaN : Number(salvo);
  return Number.isFinite(n) && n >= 0 && n <= 1 ? n : VOLUME_PADRAO;
}

function lerMudoInicial(): boolean {
  // Começar mudo é defensável — o amigo pode estar no ônibus, e ninguém
  // gosta de som estourando sem avisar. `localStorage` sobrescreve isso
  // assim que a pessoa mexe no botão uma vez.
  const salvo = localStorage.getItem(CHAVE_MUDO);
  return salvo === null ? true : salvo === '1';
}

// Um `<audio>` por troca de tema, com crossfade de ~1,5s entre o antigo e o
// novo. Autoplay é bloqueado pelo navegador até o primeiro gesto do
// usuário — `.play()` falha em silêncio até lá (a Promise rejeitada é
// ignorada de propósito); o botão de mudo, por ser um clique real, destrava
// o áudio na hora em que a pessoa desmuta.
export function useTrilha(tema: TemaMusical) {
  const [mudo, setMudoState] = useState(lerMudoInicial);
  const mudoRef = useRef(mudo);
  mudoRef.current = mudo;
  const atualRef = useRef<HTMLAudioElement | null>(null);
  const temaAtualRef = useRef<TemaMusical | null>(null);

  const [volume, setVolumeState] = useState(lerVolumeInicial);
  // Ref além do state porque a rampa de fade roda fora do ciclo de render e
  // precisa do valor corrente, não do capturado quando o efeito começou.
  const volumeRef = useRef(volume);
  volumeRef.current = volume;

  const setVolume = (v: number) => {
    const preso = v < 0 ? 0 : v > 1 ? 1 : v;
    setVolumeState(preso);
    localStorage.setItem(CHAVE_VOLUME, String(preso));
    if (atualRef.current) atualRef.current.volume = preso;
  };

  const setMudo = (valor: boolean) => {
    setMudoState(valor);
    localStorage.setItem(CHAVE_MUDO, valor ? '1' : '0');
    if (atualRef.current) atualRef.current.muted = valor;
    if (!valor) atualRef.current?.play().catch(() => {});
  };

  useEffect(() => {
    if (temaAtualRef.current === tema) return;
    temaAtualRef.current = tema;

    const anterior = atualRef.current;
    const novo = new Audio(FAIXAS[tema]);
    novo.loop = true;
    novo.muted = mudoRef.current;
    novo.volume = 0;
    atualRef.current = novo;
    novo.play().catch(() => {});

    let cancelado = false;
    const inicio = performance.now();
    const passo = (agora: number) => {
      if (cancelado) return;
      const t = Math.min(1, (agora - inicio) / DURACAO_CROSSFADE_MS);
      novo.volume = volumeRef.current * t;
      if (anterior) anterior.volume = volumeRef.current * (1 - t);
      if (t < 1) {
        requestAnimationFrame(passo);
      } else if (anterior) {
        anterior.pause();
        anterior.src = '';
      }
    };
    requestAnimationFrame(passo);

    return () => {
      cancelado = true;
      // Sem esta linha a faixa toca MUDA, e foi exatamente o bug relatado
      // ("cliquei no som e não sai nada"): o áudio ficava `paused: false`,
      // `muted: false`, com o tempo correndo — e `volume: 0`.
      //
      // A armadilha é a combinação do guard lá em cima com o cleanup aqui:
      // o efeito começa a rampa de fade-in em volume 0, o cleanup a cancela
      // no meio (o StrictMode monta/desmonta/monta em desenvolvimento, e uma
      // remontagem de rota faz o mesmo em produção), e na segunda execução o
      // guard `temaAtualRef.current === tema` retorna cedo — ou seja, ninguém
      // recomeça a rampa e o volume fica parado onde a rampa morreu.
      //
      // Encerrar a rampa levando o volume ao alvo torna o resultado o mesmo
      // com ou sem interrupção: o fade é um enfeite, o volume final não é.
      novo.volume = volumeRef.current;
    };
  }, [tema]);

  useEffect(() => {
    const atual = atualRef.current;
    return () => {
      atual?.pause();
    };
  }, []);

  return { mudo, alternarMudo: () => setMudo(!mudoRef.current), volume, setVolume };
}

// Trocar faixa a seco é pior que não ter música (backlog B-4) — o tema só
// muda quando o estado realmente muda de categoria, não a cada tick de HP.
export function calcularTema(opts: {
  gameOver: boolean;
  combateAtivo: boolean;
  hpAtual: number;
  hpMax: number;
}): TemaMusical {
  if (opts.gameOver) return 'tristeza';
  if (opts.combateAtivo) return 'combate';
  if (opts.hpMax > 0 && opts.hpAtual / opts.hpMax < 0.3) return 'suspense';
  return 'aventura';
}
