import PixelIcon from './PixelIcon';
import PanelFrame from './PanelFrame';

// Item 11 da rodada de polish pós-remaster — onboarding conceitual pra
// quem nunca jogou RPG de mesa. Complementar ao "Manual do Jogo"
// (PainelRegrasModal.tsx), não redundante: aquele é 100% mecânico (XP, CD,
// ações de combate — ver regras.py:8-11, decisão registrada explicitamente
// como "isto NÃO é a bíblia do mestre"); este é conceito/emoção. Visual
// também diferente de propósito: pergaminho envelhecido (`PanelFrame
// preencher`, mesma técnica de FichaModal/DetalheMonstroModal) em vez do
// chrome escuro do manual — reforça que são coisas distintas.
export default function GuiaAventureiro({
  aberto,
  aoFechar,
}: {
  aberto: boolean;
  aoFechar: () => void;
}) {
  if (!aberto) return null;

  return (
    <div
      className="fixed inset-0 z-[68] bg-black/85 flex items-center justify-center p-4 animate-fade-in"
      onClick={aoFechar}
      role="dialog"
      aria-modal="true"
      aria-label="Guia do aventureiro"
    >
      <PanelFrame
        borderWidth={14}
        preencher
        className="max-w-lg w-full max-h-[90dvh] overflow-y-auto custom-scrollbar p-6 md:p-8 relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={aoFechar}
          aria-label="Fechar guia do aventureiro"
          className="absolute top-3 right-3 p-1 bg-black/40 border-2 border-gray-700 hover:border-rpg-gold text-gray-700 hover:text-rpg-gold focus-visible:outline-none focus-visible:border-rpg-gold"
        ><PixelIcon name="fechar" size={16} /></button>

        <h2 className="font-pixel-title text-sm text-rpg-dark mb-6 flex items-center gap-2">
          <PixelIcon name="pergaminho" size={18} /> GUIA DO AVENTUREIRO
        </h2>

        <div className="space-y-6 text-rpg-dark">
          <section>
            <h3 className="font-rpg text-xl mb-1 flex items-center gap-2">
              <PixelIcon name="rosto" size={16} /> O que é um RPG?
            </h3>
            <p className="text-sm leading-relaxed text-rpg-dark/85">
              É uma história que ninguém escreveu sozinho. Aqui, o Mestre — a
              inteligência artificial que narra o mundo — não segue um roteiro
              fixo: ele reage ao que você faz de verdade. Não existe "resposta
              certa" escondida em algum lugar, só as consequências do que seu
              herói escolhe.
            </p>
          </section>

          <section>
            <h3 className="font-rpg text-xl mb-1 flex items-center gap-2">
              <PixelIcon name="dado" size={16} /> Como jogar?
            </h3>
            <p className="text-sm leading-relaxed text-rpg-dark/85">
              Escreva o que seu herói faz, em texto livre — "eu ataco o goblin",
              "eu tento convencer o guarda", "eu procuro uma saída". O Mestre
              narra o que acontece. Quando o resultado é incerto, os dados
              decidem: você vê a rolagem de verdade na tela, sem fachada — se o
              d20 disser que falhou, a história segue a partir da falha, não
              do que seria conveniente.
            </p>
          </section>

          <section>
            <h3 className="font-rpg text-xl mb-1 flex items-center gap-2">
              <PixelIcon name="estrela" size={16} /> Por que jogar?
            </h3>
            <p className="text-sm leading-relaxed text-rpg-dark/85">
              Porque o mundo continua vivo mesmo quando você não está olhando
              pra ele, e nenhuma outra pessoa vai jogar exatamente a sua
              história. Não tem final gravado — tem o que você e o Mestre
              constroem juntos, turno a turno, com risco de verdade.
            </p>
          </section>
        </div>
      </PanelFrame>
    </div>
  );
}
