import PixelIcon from './PixelIcon';
import PixelBar from './PixelBar';
import RetratoPixelado from './RetratoPixelado';
import StatusEffectIcons, { statusEfeitosAtivos } from './StatusEffectIcons';
import FloatingCombatText, { type FlutuanteHeroi } from './FloatingCombatText';
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from './ui/tooltip';

// Item 1+2+9 da rodada de polish pós-remaster — "a barra lateral deve
// concentrar tudo do herói". Extraído de GameChat.tsx (que já tinha ~1875
// linhas) seguindo o padrão de componentização das fases anteriores do
// remaster (PixelActionCard.tsx, SistemaFeedbackToast.tsx,
// StatusEffectIcons.tsx). Retrato + nome + HP/XP/Ouro (com barras) no lugar
// do card de retrato antigo da sidebar — Local/Clima saiu daqui pro topo
// central (CabecalhoRegiao.tsx), e uma pílula compacta só de HP continua
// visível fora da ficha (inline em GameChat.tsx), pro combate no mobile não
// perder a vida de vista quando a ficha fecha (decisão de HUD híbrido,
// aprovada com o usuário — ver o comentário em GameChat.tsx:1347 que
// motivou a pílula).
const ARQUIVO_FERIMENTO = {
  leve: '/assets/effects/ferimento-leve.png',
  medio: '/assets/effects/ferimento-medio.png',
  grave: '/assets/effects/ferimento-grave.png',
} as const;

function tierFerimento(pct: number): { arquivo: string; opacidade: number; pulsa: boolean } | null {
  if (pct > 0.5) return null;
  if (pct > 0.25) return { arquivo: ARQUIVO_FERIMENTO.leve, opacidade: 0.55, pulsa: false };
  if (pct > 0.10) return { arquivo: ARQUIVO_FERIMENTO.medio, opacidade: 0.7, pulsa: true };
  return { arquivo: ARQUIVO_FERIMENTO.grave, opacidade: 0.85, pulsa: true };
}

export default function HudPersonagem({
  charName,
  charRace,
  charClass,
  charImage,
  hpAtual,
  hpMax,
  xp,
  nivel,
  xpProximoNivel,
  ouro,
  defesa,
  wasDamaged,
  levelUpGlow,
  flutuantesHeroi,
  heroiEscondido,
  heroiBonusCa,
  heroiVantagemInimiga,
  onAbrirFicha,
}: {
  charName: string;
  charRace: string;
  charClass: string;
  charImage: string;
  hpAtual: number;
  hpMax: number;
  xp: number;
  nivel: number;
  xpProximoNivel: number | null;
  ouro: number;
  defesa: number | null;
  wasDamaged: boolean;
  levelUpGlow: boolean;
  flutuantesHeroi: (FlutuanteHeroi & { alvo: 'hp' | 'xp' })[];
  heroiEscondido: boolean;
  heroiBonusCa: number;
  heroiVantagemInimiga: boolean | null;
  onAbrirFicha: () => void;
}) {
  const pctHp = hpMax > 0 ? hpAtual / hpMax : 1;
  const ferimento = tierFerimento(pctHp);

  return (
    <div className="shrink-0 m-3 mb-0 p-3 border-2 border-gray-700 bg-black/50 flex flex-col gap-3">
      <button
        onClick={onAbrirFicha}
        className="flex items-center gap-3 text-left focus-visible:outline-none group"
        aria-label={`Abrir ficha completa de ${charName}`}
      >
        <div className="relative pixel-frame w-16 h-16 shrink-0 bg-black overflow-hidden group-focus-visible:ring-2 group-focus-visible:ring-rpg-gold">
          <RetratoPixelado src={charImage} alt="" className="w-full h-full object-cover object-top" />
          {/* Item 9 — marcas de ferimento por percentual de vida, camada
              CSS por cima do canvas (RetratoPixelado.tsx já embrulha o
              canvas num `<div className="relative">`, então isto encaixa
              sem tocar naquele componente). `mask-image` tinge o splat
              (arte original em preto/cinza) de vermelho de verdade, em vez
              de tentar acertar a cor via `filter`. */}
          {ferimento && (
            <div
              className={`absolute inset-0 pointer-events-none ${ferimento.pulsa ? 'animate-ferimento-pulso' : ''}`}
              style={{
                opacity: ferimento.pulsa ? undefined : ferimento.opacidade,
                backgroundColor: 'var(--color-rpg-crimson)',
                WebkitMaskImage: `url(${ferimento.arquivo})`,
                maskImage: `url(${ferimento.arquivo})`,
                WebkitMaskSize: 'cover',
                maskSize: 'cover',
                WebkitMaskPosition: 'center',
                maskPosition: 'center',
                WebkitMaskRepeat: 'no-repeat',
                maskRepeat: 'no-repeat',
              }}
            />
          )}
        </div>
        <div className="min-w-0">
          <p className="text-white font-rpg text-lg leading-tight truncate">{charName}</p>
          <p className="text-[10px] text-gray-300 uppercase tracking-wide font-rpg truncate">{charRace} {charClass}</p>
          <StatusEffectIcons efeitos={statusEfeitosAtivos({ escondido: heroiEscondido, bonusCa: heroiBonusCa, vantagemInimiga: heroiVantagemInimiga })} />
        </div>
      </button>

      <TooltipProvider delayDuration={150}>
        <div className="flex flex-col gap-1.5">
          <Tooltip>
            <TooltipTrigger asChild>
              <div tabIndex={0} className="relative flex items-center gap-2 cursor-help px-1 py-0.5 border-2 border-transparent hover:border-gray-700 focus-visible:outline-none focus-visible:border-rpg-gold transition-colors">
                <PixelIcon name="coracao" size={14} />
                <span className="text-[11px] font-rpg text-gray-200 w-14 shrink-0">{hpAtual}/{hpMax}</span>
                <div className="flex-1 min-w-0"><PixelBar value={hpAtual} max={hpMax} colorClass="bg-red-600" flash={wasDamaged} /></div>
                <FloatingCombatText itens={flutuantesHeroi.filter(f => f.alvo === 'hp')} />
              </div>
            </TooltipTrigger>
            <TooltipContent>
              Vida: {hpAtual} de {hpMax}
              {hpMax > 0 && ` (${Math.round((hpAtual / hpMax) * 100)}%)`}
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <div tabIndex={0} className="relative flex items-center gap-2 cursor-help px-1 py-0.5 border-2 border-transparent hover:border-gray-700 focus-visible:outline-none focus-visible:border-rpg-gold transition-colors">
                <PixelIcon name="estrela" size={14} />
                <span className="text-[11px] font-rpg text-gray-200 w-14 shrink-0">Nv {nivel}</span>
                <div className="flex-1 min-w-0">
                  <PixelBar
                    value={xpProximoNivel != null ? xp : 1}
                    max={xpProximoNivel != null ? xpProximoNivel : 1}
                    colorClass="bg-rpg-gold"
                    glow={levelUpGlow}
                  />
                </div>
                <FloatingCombatText itens={flutuantesHeroi.filter(f => f.alvo === 'xp')} />
              </div>
            </TooltipTrigger>
            <TooltipContent>
              {xpProximoNivel != null
                ? `Experiência: ${xp} de ${xpProximoNivel} para o nível ${nivel + 1}`
                : `Nível ${nivel} — experiência no máximo`}
            </TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <div tabIndex={0} className="flex items-center gap-2 cursor-help px-1 py-0.5 border-2 border-transparent hover:border-gray-700 focus-visible:outline-none focus-visible:border-rpg-gold transition-colors">
                <PixelIcon name="moeda" size={14} />
                <span className="text-[11px] font-rpg text-rpg-gold">{ouro}</span>
                <span className="text-[9px] text-gray-500 uppercase tracking-widest ml-auto">Ouro</span>
              </div>
            </TooltipTrigger>
            <TooltipContent>{ouro} de ouro no bolso.</TooltipContent>
          </Tooltip>

          <Tooltip>
            <TooltipTrigger asChild>
              <div tabIndex={0} className="flex items-center gap-2 cursor-help px-1 py-0.5 border-2 border-transparent hover:border-gray-700 focus-visible:outline-none focus-visible:border-rpg-gold transition-colors">
                <PixelIcon name="escudo" size={14} />
                <span className="text-[11px] font-rpg text-blue-200">{defesa ?? '?'}</span>
                <span className="text-[9px] text-gray-500 uppercase tracking-widest ml-auto">Defesa</span>
              </div>
            </TooltipTrigger>
            <TooltipContent>
              Defesa {defesa ?? '?'} — o número que um ataque precisa alcançar para acertar você.
            </TooltipContent>
          </Tooltip>
        </div>
      </TooltipProvider>
    </div>
  );
}
