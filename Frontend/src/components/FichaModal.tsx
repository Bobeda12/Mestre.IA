import PixelIcon from './PixelIcon';
import PanelFrame from './PanelFrame';
import RetratoPixelado from './RetratoPixelado';

// Fase 3 do remaster UX (PLANO_REMASTER_UX.md) — "Ficha de Personagem":
// clicar no retrato da sidebar abria só a imagem ampliada; agora abre uma
// ficha de D&D de papel de verdade, tela cheia. Substitui aquele modal
// (mesmo conteúdo do retrato — nome, raça, classe — só que dentro de algo
// maior, não ao lado dele), então não sobra um segundo "clique pra ver
// grande" fazendo quase a mesma coisa.
const ATRIBUTOS_FICHA = [
  ['forca', 'Força'], ['destreza', 'Destreza'], ['constituicao', 'Constituição'],
  ['inteligencia', 'Inteligência'], ['sabedoria', 'Sabedoria'], ['carisma', 'Carisma'],
] as const;

export default function FichaModal({
  aberto,
  onFechar,
  nome,
  raca,
  classe,
  charImage,
  atributos,
  hpAtual,
  hpMax,
  defesa,
  origem,
  objetivo,
  historia,
}: {
  aberto: boolean;
  onFechar: () => void;
  nome: string;
  raca: string;
  classe: string;
  charImage: string;
  atributos: Record<string, number>;
  hpAtual: number;
  hpMax: number;
  defesa: number | null;
  origem?: string | null;
  objetivo?: string | null;
  historia?: string | null;
}) {
  if (!aberto) return null;

  return (
    <div
      className="fixed inset-0 z-[65] bg-black/90 flex items-start md:items-center justify-center p-3 md:p-8 overflow-y-auto animate-fade-in"
      onClick={onFechar}
      role="dialog"
      aria-modal="true"
      aria-label={`Ficha de ${nome}`}
    >
      <PanelFrame
        borderWidth={14}
        preencher
        className="max-w-3xl w-full my-auto p-5 md:p-8 relative"
        onClick={(e) => e.stopPropagation()}
      >
        <button
          onClick={onFechar}
          aria-label="Fechar ficha"
          className="absolute top-3 right-3 p-1 bg-black/40 border-2 border-gray-700 hover:border-rpg-gold text-gray-700 hover:text-rpg-gold focus-visible:outline-none focus-visible:border-rpg-gold"
        ><PixelIcon name="fechar" size={16} /></button>

        <h2 className="font-pixel-title text-[11px] text-rpg-dark/70 mb-6 flex items-center gap-2">
          <PixelIcon name="pergaminho" size={16} /> FICHA DE PERSONAGEM
        </h2>

        <div className="grid md:grid-cols-[180px_1fr] gap-6">
          <div className="shrink-0">
            <div className="pixel-frame w-full aspect-[3/4] bg-black overflow-hidden mb-2">
              <RetratoPixelado src={charImage} alt={`Retrato de ${nome}`} grade={90} className="w-full h-full object-cover object-top" />
            </div>
            <p className="text-rpg-dark font-rpg text-2xl leading-tight">{nome}</p>
            <p className="text-xs text-rpg-dark/70 uppercase tracking-wide font-rpg">{raca} · {classe}</p>
          </div>

          <div className="space-y-4 min-w-0">
            <div className="flex flex-wrap gap-4 font-rpg text-rpg-dark">
              <span className="flex items-center gap-1.5"><PixelIcon name="coracao" size={14} /> {hpAtual}/{hpMax}</span>
              <span className="flex items-center gap-1.5"><PixelIcon name="escudo" size={14} /> {defesa ?? '?'}</span>
            </div>

            <div className="grid grid-cols-3 gap-2">
              {ATRIBUTOS_FICHA.map(([chave, rotulo]) => (
                <div key={chave} className="bg-black/10 border-2 border-rpg-dark/30 p-2 text-center">
                  <span className="text-[9px] text-rpg-dark/60 block font-rpg uppercase tracking-widest">{rotulo}</span>
                  <span className="font-rpg text-xl text-rpg-dark">{atributos?.[chave] ?? '-'}</span>
                </div>
              ))}
            </div>

            {origem && (
              <p className="text-sm text-rpg-dark leading-relaxed"><span className="font-bold">Origem:</span> {origem}</p>
            )}
            {objetivo && (
              <p className="text-sm text-rpg-dark leading-relaxed"><span className="font-bold">Objetivo:</span> {objetivo}</p>
            )}
            {historia && (
              <div className="border-t-2 border-rpg-dark/20 pt-3">
                <h3 className="text-[10px] uppercase tracking-widest text-rpg-dark/60 font-rpg mb-1">História</h3>
                <p className="text-sm text-rpg-dark/80 italic leading-relaxed">{historia}</p>
              </div>
            )}
          </div>
        </div>
      </PanelFrame>
    </div>
  );
}
