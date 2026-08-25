import { useEffect, useState } from 'react';
import RetratoPixelado from './RetratoPixelado';
import { useVelocidadeTexto } from '../lib/config';

// Etapa 11 (B-7) — o prólogo (narrator.gerar_prologo_missao) sempre existiu
// como texto pronto, mas virava só mais uma bolha de chat igual às outras
// (ou nem isso: ao recarregar, "Conectado ao mundo" tomava o lugar dele).
// Esta tela mostra o prólogo pela primeira vez de verdade — quem é o
// herói (retrato + raça/classe), onde ele está (local/clima) e o que ele
// quer (background/objetivo), como uma abertura de campanha, não um
// system message.
interface PrologoProps {
  nome: string;
  raca: string;
  classe: string;
  local: string;
  clima?: string | null;
  background?: string | null;
  objetivo?: string | null;
  charImage: string;
  texto: string;
  onComecar: () => void;
}

const CARACTERES_POR_TICK = 2;

export default function Prologo({
  nome, raca, classe, local, clima, background, objetivo, charImage, texto, onComecar,
}: PrologoProps) {
  // Velocidade vem das opções; 0 mostra o texto de uma vez.
  const { velocidade } = useVelocidadeTexto();
  const [visivel, setVisivel] = useState('');
  const [concluido, setConcluido] = useState(false);

  useEffect(() => {
    setVisivel('');
    setConcluido(false);
    if (velocidade === 0) {
      setVisivel(texto);
      setConcluido(true);
      return;
    }
    let i = 0;
    const id = setInterval(() => {
      i += CARACTERES_POR_TICK;
      setVisivel(texto.slice(0, i));
      if (i >= texto.length) {
        clearInterval(id);
        setConcluido(true);
      }
    }, velocidade);
    return () => clearInterval(id);
  }, [texto, velocidade]);

  const pular = () => {
    setVisivel(texto);
    setConcluido(true);
  };

  return (
    // Composição centrada, com largura máxima. A versão anterior colava o
    // retrato na borda esquerda ocupando 40% da largura E a altura inteira, o
    // que deixava a imagem gigantesca ao lado de uma coluna de texto espremida
    // — e num monitor largo as linhas passavam de 100 caracteres, longe demais
    // pra vista acompanhar de uma linha pra outra.
    <div className="min-h-[100dvh] w-screen bg-rpg-darker text-gray-100 flex items-center justify-center p-4 md:p-10 animate-fade-in">
      <div className="w-full max-w-5xl flex flex-col md:flex-row gap-6 md:gap-10 items-center">

        {/* Retrato com tamanho próprio, na proporção em que ele é gerado
            (500x750). Antes era `h-full` com `object-cover`, o que esticava a
            moldura e recortava a figura. */}
        <div className="pixel-frame w-40 md:w-72 shrink-0 aspect-[3/4] bg-black overflow-hidden">
          <RetratoPixelado src={charImage} alt={`Retrato de ${nome}`} grade={96} className="w-full h-full object-cover object-top" />
        </div>

        <div className="flex-1 min-w-0 w-full">
          <h1 className="font-pixel-title text-xl md:text-3xl text-rpg-gold mb-3 leading-relaxed break-words">{nome}</h1>
          <p className="text-xs md:text-sm text-gray-300 uppercase tracking-widest mb-5 font-rpg">
            {raca} · {classe} · {local}{clima ? ` · ${clima}` : ''}
          </p>

          {(background || objetivo) && (
            <div className="text-xs text-gray-300 mb-6 space-y-1 border-l-2 border-rpg-gold/50 pl-3 font-rpg">
              {background && <p><span className="text-rpg-gold">Origem:</span> {background}</p>}
              {objetivo && <p><span className="text-rpg-gold">Objetivo:</span> {objetivo}</p>}
            </div>
          )}

          {/* `max-w-[62ch]` porque o limite de leitura confortável é a MEDIDA
              em caracteres, não a largura do monitor. Uma barra de rolagem só:
              antes esta caixa rolava dentro de um pai que também rolava, e as
              duas apareciam lado a lado. */}
          <div
            onClick={pular}
            role="button"
            aria-label="Pular efeito de digitação"
            tabIndex={0}
            className="cursor-pointer text-gray-100 leading-relaxed whitespace-pre-wrap font-hand text-lg md:text-xl max-w-[62ch] max-h-[46vh] overflow-y-auto custom-scrollbar pr-2"
          >
            {visivel}
            {!concluido && <span className="animate-pulse">▋</span>}
          </div>

          <button
            onClick={onComecar}
            className="pixel-frame mt-8 bg-rpg-gold text-black font-pixel-title text-[10px] md:text-xs px-6 py-3 hover:bg-white transition-colors"
          >
            COMEÇAR
          </button>
        </div>
      </div>
    </div>
  );
}
