import { useState } from 'react';
import { useChaveGemini } from '../lib/config';
import PixelIcon from './PixelIcon';
import FormChaveGemini from './FormChaveGemini';

// Recomendação de BYOK (chave própria do Gemini) na tela inicial — antes só
// vivia escondida dentro do menu de Opções, e quase ninguém a descobria. Só
// aparece pra quem está logado e ainda não tem chave; some sozinho assim que
// `useChaveGemini` reportar uma chave salva (FormChaveGemini cuida disso).
export default function BannerChaveGemini() {
  const { chave: chaveGemini } = useChaveGemini();
  const [expandido, setExpandido] = useState(false);

  if (chaveGemini) return null;

  return (
    <div className="w-full max-w-sm mt-8 border-2 border-rpg-gold bg-black/70 p-3 animate-fade-in">
      <div className="flex items-start gap-2">
        <PixelIcon name="estrela" size={20} className="mt-0.5 shrink-0" />
        <div className="flex-1 min-w-0">
          <h3 className="font-pixel-title text-[10px] text-rpg-gold mb-1.5 leading-relaxed">
            ACESSO VIP GRÁTIS
          </h3>
          <p className="text-[11px] text-gray-300 leading-relaxed font-rpg">
            Use sua própria chave gratuita do Gemini — leva menos de um minuto pra criar no{' '}
            <a
              href="https://aistudio.google.com/apikey"
              target="_blank"
              rel="noreferrer"
              className="text-rpg-gold underline hover:text-white"
            >
              Google AI Studio
            </a>
            — e jogue sem entrar na fila da cota compartilhada do servidor.
          </p>
          {!expandido && (
            <button
              onClick={() => setExpandido(true)}
              className="mt-2 text-xs font-bold text-black bg-rpg-gold hover:bg-white px-3 py-1.5"
            >
              Configurar agora
            </button>
          )}
        </div>
      </div>

      {expandido && (
        <div className="mt-3 pt-3 border-t border-gray-700">
          <FormChaveGemini />
        </div>
      )}
    </div>
  );
}
