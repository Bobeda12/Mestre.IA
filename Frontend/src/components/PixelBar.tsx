// Etapa 11 (B-1) — barra de vida/XP em blocos discretos, no lugar do
// preenchimento suave e animado do <Progress> (shadcn/Radix) — telas de
// RPG 8-bit mostram a barra como uma fileira de segmentos cheios/vazios,
// nunca um gradiente contínuo.
export default function PixelBar({
  value,
  max = 100,
  segments = 12,
  colorClass = 'bg-red-600',
  trackClass = 'bg-gray-900',
}: {
  value: number;
  max?: number;
  segments?: number;
  colorClass?: string;
  trackClass?: string;
}) {
  const pct = max > 0 ? Math.max(0, Math.min(1, value / max)) : 0;
  const preenchidos = Math.round(pct * segments);
  return (
    <div
      className="flex gap-[2px]"
      role="progressbar"
      aria-valuenow={Math.round(pct * 100)}
      aria-valuemin={0}
      aria-valuemax={100}
    >
      {Array.from({ length: segments }).map((_, i) => (
        <div key={i} className={`h-2 flex-1 ${i < preenchidos ? colorClass : trackClass}`} />
      ))}
    </div>
  );
}
