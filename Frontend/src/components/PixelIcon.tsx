// Etapa 14 (C-1) — ícones 8-bit reais no lugar do lucide-react (traço fino,
// não combina com o resto do visual pixel art da Etapa 11). Fonte de cada
// arquivo documentada em docs/CREDITOS.md. Ponto único de troca: qualquer
// lugar que hoje importa um ícone do lucide-react pode virar
// `<PixelIcon name="..." />`.
const ICON_PATHS = {
  coroa: '/assets/icons/coroa.png',
  coracao: '/assets/icons/coracao.png',
  menos: '/assets/icons/menos.png',
  mais: '/assets/icons/mais.png',
  espada: '/assets/icons/espada.png',
  adaga: '/assets/icons/adaga.png',
  machado: '/assets/icons/machado.png',
  maca: '/assets/icons/maca.png',
  escudo: '/assets/icons/escudo.png',
  'pocao-roxa': '/assets/icons/pocao-roxa.png',
  'pocao-verde': '/assets/icons/pocao-verde.png',
  'pocao-vermelha': '/assets/icons/pocao-vermelha.png',
  'pocao-azul': '/assets/icons/pocao-azul.png',
  bau: '/assets/icons/bau.png',
  pergaminho: '/assets/icons/pergaminho.png',
  mochila: '/assets/icons/mochila.png',
  moeda: '/assets/icons/moeda.png',
  estrela: '/assets/icons/estrela.png',
  fechar: '/assets/icons/fechar.png',
  menu: '/assets/icons/menu.png',
  seta: '/assets/icons/seta.png',
  'som-ligado': '/assets/icons/som-ligado.png',
  'som-mudo': '/assets/icons/som-mudo.png',
  // Revisão da Etapa 14 — os que faltavam pra tirar o lucide-react do
  // GameChat/RollCard/StatusCard. Mesma origem dos outros desenhados à mão
  // (ver docs/CREDITOS.md).
  dado: '/assets/icons/dado.png',
  rosto: '/assets/icons/rosto.png',
  alerta: '/assets/icons/alerta.png',
  'polegar-cima': '/assets/icons/polegar-cima.png',
  'polegar-baixo': '/assets/icons/polegar-baixo.png',
  enviar: '/assets/icons/enviar.png',
  cura: '/assets/icons/cura.png',
  caveira: '/assets/icons/caveira.png',
} as const;

export type PixelIconName = keyof typeof ICON_PATHS;

export default function PixelIcon({
  name,
  size = 16,
  className = '',
  alt = '',
}: {
  name: PixelIconName;
  size?: number;
  className?: string;
  alt?: string;
}) {
  return (
    <img
      src={ICON_PATHS[name]}
      width={size}
      height={size}
      alt={alt}
      draggable={false}
      className={`inline-block shrink-0 ${className}`}
    />
  );
}
