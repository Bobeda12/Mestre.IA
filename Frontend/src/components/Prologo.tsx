import { useEffect, useState } from 'react';

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

const VELOCIDADE_MS = 12;
const CARACTERES_POR_TICK = 2;

export default function Prologo({
  nome, raca, classe, local, clima, background, objetivo, charImage, texto, onComecar,
}: PrologoProps) {
  const [visivel, setVisivel] = useState('');
  const [concluido, setConcluido] = useState(false);

  useEffect(() => {
    setVisivel('');
    setConcluido(false);
    let i = 0;
    const id = setInterval(() => {
      i += CARACTERES_POR_TICK;
      setVisivel(texto.slice(0, i));
      if (i >= texto.length) {
        clearInterval(id);
        setConcluido(true);
      }
    }, VELOCIDADE_MS);
    return () => clearInterval(id);
  }, [texto]);

  const pular = () => {
    setVisivel(texto);
    setConcluido(true);
  };

  return (
    <div className="h-screen w-screen bg-black text-gray-100 flex flex-col md:flex-row overflow-hidden animate-fade-in">
      <div className="pixel-frame w-full md:w-2/5 h-56 md:h-full shrink-0 bg-black relative m-4 md:m-8 md:mr-0">
        <img src={charImage} alt={nome} className="w-full h-full object-cover" onError={(e) => (e.currentTarget.style.display = 'none')} />
      </div>

      <div className="flex-1 min-h-0 p-6 md:p-12 flex flex-col justify-center overflow-y-auto custom-scrollbar">
        <h1 className="font-pixel-title text-lg md:text-2xl text-rpg-gold mb-2 leading-relaxed">{nome}</h1>
        <p className="text-xs md:text-sm text-gray-400 uppercase tracking-widest mb-4">
          {raca} · {classe} · {local}{clima ? ` · ${clima}` : ''}
        </p>

        {(background || objetivo) && (
          <div className="text-xs text-gray-500 mb-6 space-y-1 border-l-2 border-rpg-gold/40 pl-3">
            {background && <p><span className="text-rpg-gold">Origem:</span> {background}</p>}
            {objetivo && <p><span className="text-rpg-gold">Objetivo:</span> {objetivo}</p>}
          </div>
        )}

        <div
          onClick={pular}
          role="button"
          aria-label="Pular efeito de digitação"
          tabIndex={0}
          className="cursor-pointer text-gray-200 leading-relaxed whitespace-pre-wrap font-hand text-lg md:text-xl max-h-[45vh] overflow-y-auto custom-scrollbar pr-2"
        >
          {visivel}
          {!concluido && <span className="animate-pulse">▋</span>}
        </div>

        <button
          onClick={onComecar}
          className="pixel-frame mt-8 self-start bg-rpg-gold text-black font-pixel-title text-[10px] md:text-xs px-6 py-3 hover:bg-white transition-colors"
        >
          COMEÇAR
        </button>
      </div>
    </div>
  );
}
