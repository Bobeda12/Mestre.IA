// Etapa 14 (revisão) — o fundo anterior da tela inicial era um único tile de
// masmorra repetido em `bg-repeat`, e lido como defeito ("parece algo
// bugado"): a repetição de um tile de 16px numa tela inteira vira um padrão
// mecânico, não uma cena. Aqui é um mapa de overworld montado como uma faixa
// larga, deslizando devagar na horizontal em loop — a câmera sobrevoando o
// mundo, que é o que consoles 8-bit faziam em tela de título.
//
// Por que uma faixa larguíssima em vez de um `bg-repeat` no próprio contêiner:
// a animação precisa ser em `transform` (a única propriedade, junto de
// `opacity`, que não força repaint a cada quadro). Deslocar exatamente a
// largura de um tile faz o padrão coincidir consigo mesmo, então o loop não
// tem emenda em nenhuma largura de tela — ver `@keyframes mapaDeslizando` em
// index.css.
//
// `aria-hidden` porque é puramente decorativo: o leitor de tela não ganha
// nada anunciando um mapa de fundo, e a tela já tem título e rótulos.
// Precisa bater EXATAMENTE com o lado de `mapa-mundo.png` (ver gerar_mapa.py,
// N * TILE). Se divergir, dois problemas de uma vez: o `background-size`
// reescala a arte e destrói a grade de pixel, e o deslocamento da animação
// deixa de coincidir com um tile inteiro, fazendo a emenda aparecer.
const TILE_LARGURA = 768;

export default function MapaDeFundo({
  opacidade = 0.75,
  duracaoSegundos = 90,
}: {
  opacidade?: number;
  duracaoSegundos?: number;
}) {
  return (
    <div aria-hidden className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
      <div
        className="animate-mapa absolute inset-y-0 left-0"
        style={{
          // Bem mais larga que qualquer viewport: assim a borda de trás nunca
          // entra em cena durante o deslocamento de um tile.
          width: '400vw',
          backgroundImage: "url('/assets/backgrounds/mapa-mundo.png')",
          // Repete nos DOIS eixos, com tamanho fixo em px. É um mapa visto de
          // cima, então ladrilhar na vertical é natural — e tamanho fixo
          // mantém o pixel quadrado. Esticar pra `100%` de altura deformaria
          // a arte (pixel retangular), que é justamente o que faz pixel art
          // parecer amadora.
          backgroundRepeat: 'repeat',
          backgroundSize: `${TILE_LARGURA}px ${TILE_LARGURA}px`,
          imageRendering: 'pixelated',
          opacity: opacidade,
          ['--tile-w' as string]: `${TILE_LARGURA}px`,
          ['--tile-dur' as string]: `${duracaoSegundos}s`,
          // Um passo por pixel do tile mantém o movimento na grade: nunca cai
          // em meio pixel, que é o que borraria a arte.
          ['--tile-passos' as string]: String(TILE_LARGURA),
        }}
      />
      {/* Escurece o mapa por baixo do conteúdo. Sem isto o texto disputa com a
          arte e nenhum dos dois se lê.
          Véu de opacidade CONSTANTE, não gradiente: a versão em gradiente
          criava uma faixa perceptível na altura em que ele terminava, e numa
          tela de fundo isso lê como defeito de renderização. */}
      <div className="absolute inset-0 bg-rpg-darker/70" />
    </div>
  );
}
