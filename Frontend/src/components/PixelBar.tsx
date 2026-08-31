// Etapa 11 (B-1) — barra de vida/XP em blocos discretos, no lugar do
// preenchimento suave e animado do <Progress> (shadcn/Radix) — telas de
// RPG 8-bit mostram a barra como uma fileira de segmentos cheios/vazios,
// nunca um gradiente contínuo.
//
// Fase 2 do remaster UX (PLANO_REMASTER_UX.md) — `flash`/`glow` dão o
// "juice" da barra reagir a evento (dano, level up) sem sair do vocabulário
// 8-bit: `flash` é um brilho em pico + tremor (`.animate-shake`, já usado
// pra tela inteira no dano), `glow` é a respiração dourada (`pulse-glow`)
// só que aplicada à barra, não à tela toda. Quem controla a duração é
// quem chama (GameChat liga/desliga a prop), a barra só reage.
export default function PixelBar({
  value,
  max = 100,
  segments = 12,
  colorClass = 'bg-red-600',
  trackClass = 'bg-gray-900',
  flash = false,
  glow = false,
}: {
  value: number;
  max?: number;
  segments?: number;
  colorClass?: string;
  trackClass?: string;
  flash?: boolean;
  glow?: boolean;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const preenchidos = Math.round(pct * segments);
  return (
    <div
      className={`flex gap-[2px] ${flash ? 'animate-bar-flash animate-shake' : ''} ${glow ? 'animate-bar-glow' : ''}`}
      role="progressbar"
      aria-valuenow={Math.round(pct * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: segments }).map((_, i) => (
        <div key={i} className={`h-2 flex-1 transition-colors duration-150 ${i < preenchidos ? colorClass : trackClass}`} />
      ))}
    </div>
  );
}
