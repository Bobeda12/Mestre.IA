import { useEffect, useState } from 'react';

// Preferências do jogador que não são estado de jogo — vivem no navegador, não
// no servidor. O volume da trilha mora em `trilha.ts` porque está acoplado ao
// elemento de áudio; o que não tem dono natural fica aqui.
//
// Guardado em `localStorage` e sincronizado entre abas pelo evento `storage`:
// sem isso, mudar a configuração numa aba deixaria a outra com o valor velho
// até recarregar.

/** Velocidade do efeito de digitação do prólogo, em ms por tique. Menor = mais
 *  rápido. `0` desliga o efeito e mostra o texto de uma vez. */
export type VelocidadeTexto = 0 | 6 | 12 | 24;

export const VELOCIDADES: { valor: VelocidadeTexto; rotulo: string }[] = [
  { valor: 0, rotulo: 'Instantâneo' },
  { valor: 6, rotulo: 'Rápido' },
  { valor: 12, rotulo: 'Normal' },
  { valor: 24, rotulo: 'Lento' },
];

const CHAVE_VELOCIDADE = 'mestre_ia_velocidade_texto';
const PADRAO: VelocidadeTexto = 12;

function ler(): VelocidadeTexto {
  const n = Number(localStorage.getItem(CHAVE_VELOCIDADE));
  return VELOCIDADES.some((v) => v.valor === n) ? (n as VelocidadeTexto) : PADRAO;
}

export function useVelocidadeTexto() {
  const [velocidade, setEstado] = useState<VelocidadeTexto>(ler);

  useEffect(() => {
    // Outra aba mexeu na configuração: `storage` só dispara nas OUTRAS abas,
    // nunca na que escreveu, então não há risco de laço.
    const aoMudar = (e: StorageEvent) => {
      if (e.key === CHAVE_VELOCIDADE) setEstado(ler());
    };
    window.addEventListener('storage', aoMudar);
    return () => window.removeEventListener('storage', aoMudar);
  }, []);

  const setVelocidade = (v: VelocidadeTexto) => {
    setEstado(v);
    localStorage.setItem(CHAVE_VELOCIDADE, String(v));
  };

  return { velocidade, setVelocidade };
}

// BYOK (Etapa 15) — chave própria do jogador pro Gemini. Igual ao resto
// deste arquivo, vive só no navegador: o back-end nunca a persiste (só
// recebe no header `X-Gemini-Key` de cada pedido), e removê-la aqui é
// suficiente pra voltar a usar a cota compartilhada do servidor.
const CHAVE_GEMINI = 'mestre_ia_chave_gemini';

export function getChaveGemini(): string | null {
  return localStorage.getItem(CHAVE_GEMINI);
}

export function setChaveGemini(chave: string): void {
  localStorage.setItem(CHAVE_GEMINI, chave);
}

export function removerChaveGemini(): void {
  localStorage.removeItem(CHAVE_GEMINI);
}

export function useChaveGemini() {
  const [chave, setEstado] = useState<string | null>(getChaveGemini);

  useEffect(() => {
    const aoMudar = (e: StorageEvent) => {
      if (e.key === CHAVE_GEMINI) setEstado(getChaveGemini());
    };
    window.addEventListener('storage', aoMudar);
    return () => window.removeEventListener('storage', aoMudar);
  }, []);

  const salvar = (v: string) => {
    setChaveGemini(v);
    setEstado(v);
  };
  const remover = () => {
    removerChaveGemini();
    setEstado(null);
  };

  return { chave, salvar, remover };
}
