import PixelIcon from './PixelIcon';
import PainelRegras from './PainelRegras';

// Correção de UX pós Fase 1 do remaster — a aba "Regras" ficava dentro da
// ficha, competindo por espaço com status/itens/missão/relações/bestiário
// numa faixa de abas já cheia. Vira um modal disparado por um botão dedicado
// ("Manual do Jogo") no header, no mesmo padrão de MenuConfiguracao.tsx (tema
// escuro, caixa simples, sem PanelFrame/`preencher`) — não o de FichaModal
// (pergaminho claro), porque PainelRegras.tsx já foi escrito para fundo
// escuro (`text-gray-300`, `bg-black/50`); usar o pergaminho aqui pediria
// reescrever as cores dele à toa. PainelRegras continua um componente de
// conteúdo puro (fetch de /regras) — este arquivo só desenha o chrome do
// modal por fora.
export default function PainelRegrasModal({
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
      aria-label="Manual do jogo"
    >
      <div
        className="w-full max-w-lg bg-rpg-dark border-2 border-rpg-gold max-h-[90dvh] overflow-y-auto custom-scrollbar"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-3 border-b-2 border-gray-700">
          <h2 className="font-pixel-title text-xs text-rpg-gold flex items-center gap-2">
            <PixelIcon name="dado" size={16} /> MANUAL DO JOGO
          </h2>
          <button
            onClick={aoFechar}
            aria-label="Fechar manual do jogo"
            className="p-1 border-2 border-gray-700 hover:border-rpg-gold focus-visible:outline-none focus-visible:border-rpg-gold"
          >
            <PixelIcon name="fechar" size={14} />
          </button>
        </div>

        <div className="p-3">
          <PainelRegras />
        </div>
      </div>
    </div>
  );
}
