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
  config: '/assets/icons/config.png',
} as const;

export type PixelIconName = keyof typeof ICON_PATHS;

// Item D da rodada de melhorias pós-Fase-6 — os PNGs são desenhados à mão,
// cada um com sua própria folga dentro do quadro de 16×16 (medido de
// verdade: `im.getbbox()` sobre cada arquivo, ver commit). O mesmo `size=`
// produzia ícones visivelmente maiores ou menores lado a lado (ex.:
// "pergaminho" preenche só 69% do quadro; "config" preenche 100%) — o que
// o usuário via como "ícones desalinhados". Este fator escala CADA ícone
// pra todos convergirem pro mesmo preenchimento visual (~85% do quadro),
// mantendo `size` como o tamanho nominal esperado pelo call site.
const CORRECAO_VISUAL: Partial<Record<PixelIconName, number>> = {
  adaga: 1.05,
  alerta: 0.91,
  bau: 0.85,
  caveira: 1.13,
  config: 0.85,
  coroa: 1.13,
  cura: 1.13,
  dado: 0.91,
  enviar: 0.91,
  escudo: 1.25,
  espada: 0.94,
  fechar: 1.05,
  maca: 0.85,
  machado: 0.85,
  mais: 1.13,
  menos: 1.13,
  menu: 1.13,
  mochila: 0.91,
  moeda: 1.24,
  pergaminho: 1.24,
  'pocao-azul': 1.05,
  'pocao-roxa': 1.05,
  'pocao-verde': 1.05,
  'pocao-vermelha': 1.05,
  seta: 1.13,
  'som-ligado': 0.85,
  'som-mudo': 0.85,
};

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
  const tamanho = Math.round(size * (CORRECAO_VISUAL[name] ?? 1));
  return (
    <img
      src={ICON_PATHS[name]}
      width={tamanho}
      height={tamanho}
      alt={alt}
      draggable={false}
      className={`inline-block shrink-0 ${className}`}
    />
  );
}
