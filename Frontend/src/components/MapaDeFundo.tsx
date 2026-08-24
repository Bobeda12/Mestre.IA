// Fundo da tela inicial e do login: uma cidade sombria ao entardecer, em
// parallax de duas camadas.
//
// Histórico, porque explica por que NÃO é mais um mapa gerado: a versão
// anterior compunha um overworld tile a tile por script, e passou por quatro
// tentativas (sorteio por tile, suavização celular, Voronoi, marcos esparsos)
// sem nunca deixar de parecer manchado. A lição foi a mesma dos retratos de
// raça/classe: arte pronta feita à mão ganha de arte composta por algoritmo.
// Esta é do pacote GothicVania Town (ansimuz, CC0, ver docs/CREDITOS.md).
//
// Parallax de verdade: a camada de trás (céu e cidade distante) desliza mais
// devagar que a da frente (telhados escuros). A diferença de velocidade é o
// que dá sensação de profundidade — as duas na mesma velocidade seriam só uma
// imagem se movendo.
//
// As duas ladrilham sem emenda, por caminhos diferentes: a de trás já vinha
// assim do pacote; a da frente NÃO (bordas com diferença média de 52), então
// ela é a original seguida da própria imagem espelhada — a borda direita vira
// cópia da esquerda e a costura fecha por construção.
//
// `aria-hidden` porque é puramente decorativo: o leitor de tela não ganha
// nada anunciando um cenário de fundo.
const FUNDO_LARGURA = 384;
const FRENTE_LARGURA = 768;
const ALTURA_ARTE = 288;   // as duas camadas do pacote têm essa altura
// Escala inteira: 288 * 3 = 864px, cobre a altura de tela usual sem esticar.
// Fracionária borraria a grade de pixel.
const ESCALA = 3;

export default function MapaDeFundo({
  opacidade = 0.85,
  duracaoSegundos = 140,
}: {
  opacidade?: number;
  duracaoSegundos?: number;
}) {
  return (
    <div aria-hidden className="absolute inset-0 z-0 overflow-hidden pointer-events-none">
      {/* Camada de trás: céu e cidade distante. */}
      <Camada
        imagem="/assets/backgrounds/cidade-fundo.png"
        larguraTile={FUNDO_LARGURA}
        duracao={duracaoSegundos}
        opacidade={opacidade}
        alturaPercentual={100}
        alinhamento="bottom"
      />
      {/* Camada da frente: telhados escuros, ancorados na base. Mais rápida
          que a de trás, e é ela que escurece o rodapé da tela. */}
      <Camada
        imagem="/assets/backgrounds/cidade-frente.png"
        larguraTile={FRENTE_LARGURA}
        duracao={Math.round(duracaoSegundos * 0.55)}
        opacidade={opacidade}
        alturaPercentual={60}
        alinhamento="bottom"
      />
      {/* Véu de opacidade CONSTANTE, não gradiente: em gradiente aparecia uma
          faixa perceptível na altura em que ele terminava, e num fundo isso
          lê como defeito de renderização. */}
      <div className="absolute inset-0 bg-rpg-darker/55" />
    </div>
  );
}

function Camada({
  imagem,
  larguraTile,
  duracao,
  opacidade,
  alturaPercentual,
  alinhamento,
}: {
  imagem: string;
  larguraTile: number;
  duracao: number;
  opacidade: number;
  alturaPercentual: number;
  alinhamento: 'bottom' | 'top';
}) {
  return (
    <div
      className="animate-mapa absolute left-0"
      style={{
        // Bem mais larga que qualquer viewport: assim a borda de trás nunca
        // entra em cena durante o deslocamento de um tile.
        width: '400vw',
        height: `${alturaPercentual}%`,
        [alinhamento]: 0,
        backgroundImage: `url('${imagem}')`,
        backgroundRepeat: 'repeat-x',
        // Tamanho em PIXELS por escala inteira, não `auto 100%`. Com altura em
        // `100%` a largura do tile passaria a depender da altura da janela e
        // deixaria de bater com `--tile-w` — o deslocamento não cairia mais
        // sobre um tile exato e a emenda voltaria. Escala inteira também é o
        // que mantém o pixel quadrado.
        backgroundSize: `${larguraTile * ESCALA}px ${ALTURA_ARTE * ESCALA}px`,
        backgroundPosition: `left ${alinhamento}`,
        imageRendering: 'pixelated',
        opacity: opacidade,
        ['--tile-w' as string]: `${larguraTile * ESCALA}px`,
        ['--tile-dur' as string]: `${duracao}s`,
        // Um passo por pixel do tile mantém o movimento na grade: nunca cai em
        // meio pixel, que é o que borraria a arte.
        ['--tile-passos' as string]: String(larguraTile),
      }}
    />
  );
}
