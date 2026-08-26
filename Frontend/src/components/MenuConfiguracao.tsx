import { useNavigate } from 'react-router-dom';
import { useVelocidadeTexto, VELOCIDADES } from '../lib/config';
import PixelIcon from './PixelIcon';
import PixelButton from './PixelButton';
import FormChaveGemini from './FormChaveGemini';

// Menu de configuração. Nasce com o que já existe pra ajustar (som e
// velocidade do texto) mais a saída pro menu inicial, e é feito pra crescer:
// cada item é um bloco `<Secao>` independente.
//
// Tema claro NÃO entra por decisão consciente, não por esquecimento: a
// identidade inteira do jogo assume fundo escuro — paleta ouro/couro,
// molduras, o cenário da cidade ao entardecer, sprites com contorno preto.
// Um tema claro seria uma segunda identidade visual, não um interruptor.
// Os controles de som chegam por PROP, não de um `useTrilha` próprio: o hook
// cria um elemento de áudio por instância, e como hooks rodam mesmo com o
// modal fechado, chamá-lo aqui faria DOIS players tocando a mesma faixa em
// paralelo, levemente defasados. Quem toca é a tela; o menu só ajusta.
export default function MenuConfiguracao({
  aberto,
  aoFechar,
  trilha,
  mostrarVoltar = true,
}: {
  aberto: boolean;
  aoFechar: () => void;
  /** Na própria tela inicial não faz sentido oferecer "voltar ao menu". */
  mostrarVoltar?: boolean;
  trilha: {
    mudo: boolean;
    alternarMudo: () => void;
    volume: number;
    setVolume: (v: number) => void;
  };
}) {
  const navigate = useNavigate();
  const { mudo, alternarMudo, volume, setVolume } = trilha;
  const { velocidade, setVelocidade } = useVelocidadeTexto();

  if (!aberto) return null;

  return (
    <div
      className="fixed inset-0 z-[70] bg-black/85 flex items-center justify-center p-4 animate-fade-in"
      onClick={aoFechar}
      role="dialog"
      aria-modal="true"
      aria-label="Configurações"
    >
      <div
        className="w-full max-w-sm bg-rpg-dark border-2 border-rpg-gold max-h-[90dvh] overflow-y-auto custom-scrollbar"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between p-3 border-b-2 border-gray-700">
          <h2 className="font-pixel-title text-xs text-rpg-gold flex items-center gap-2">
            <PixelIcon name="config" size={16} /> OPÇÕES
          </h2>
          <button
            onClick={aoFechar}
            aria-label="Fechar configurações"
            className="p-1 border-2 border-gray-700 hover:border-rpg-gold focus-visible:outline-none focus-visible:border-rpg-gold"
          >
            <PixelIcon name="fechar" size={14} />
          </button>
        </div>

        <div className="p-3 space-y-5">
          <Secao titulo="Som">
            <button
              onClick={alternarMudo}
              aria-pressed={!mudo}
              className="w-full flex items-center justify-between gap-2 p-2 border-2 border-gray-700 hover:border-rpg-gold text-gray-200 font-rpg text-sm transition-colors focus-visible:outline-none focus-visible:border-rpg-gold"
            >
              <span className="flex items-center gap-2">
                <PixelIcon name={mudo ? 'som-mudo' : 'som-ligado'} size={14} />
                Música
              </span>
              <span className={mudo ? 'text-gray-400' : 'text-rpg-gold'}>{mudo ? 'Desligada' : 'Ligada'}</span>
            </button>

            <label className="block mt-3">
              <span className="flex items-center justify-between text-xs text-gray-300 font-rpg mb-1">
                Volume <span className="text-rpg-gold">{Math.round(volume * 100)}%</span>
              </span>
              <input
                type="range"
                min={0}
                max={100}
                value={Math.round(volume * 100)}
                onChange={(e) => setVolume(Number(e.target.value) / 100)}
                disabled={mudo}
                className="w-full accent-rpg-gold disabled:opacity-40"
                aria-label="Volume da música"
              />
            </label>
          </Secao>

          <Secao titulo="Velocidade do texto">
            {/* Afeta o efeito de digitação do prólogo. "Instantâneo" existe
                tanto pra quem lê rápido quanto pra quem se incomoda com
                movimento na tela. */}
            <div className="grid grid-cols-2 gap-2">
              {VELOCIDADES.map((v) => (
                <button
                  key={v.valor}
                  onClick={() => setVelocidade(v.valor)}
                  aria-pressed={velocidade === v.valor}
                  className={`p-2 border-2 font-rpg text-sm transition-colors focus-visible:outline-none focus-visible:border-rpg-gold ${
                    velocidade === v.valor
                      ? 'border-rpg-gold bg-rpg-gold/20 text-rpg-gold'
                      : 'border-gray-700 text-gray-300 hover:border-gray-500'
                  }`}
                >
                  {v.rotulo}
                </button>
              ))}
            </div>
          </Secao>

          <Secao titulo="Sua chave de API (Gemini)">
            {/* BYOK (Etapa 15) — joga sem limite compartilhado usando a
                própria chave gratuita do Google AI Studio. Nunca sai deste
                navegador em texto salvo: o servidor só a recebe por pedido,
                nunca a guarda (ver docs/BACKLOG_TECNICO.md). */}
            <p className="text-[11px] text-gray-400 leading-relaxed mb-2">
              Quer jogar sem depender da cota compartilhada do servidor? Gere uma chave
              gratuita no{' '}
              <a
                href="https://aistudio.google.com/apikey"
                target="_blank"
                rel="noreferrer"
                className="text-rpg-gold underline hover:text-white"
              >
                Google AI Studio
              </a>{' '}
              e cole aqui — leva menos de um minuto.
            </p>
            <FormChaveGemini />
          </Secao>

          {mostrarVoltar && (
            <>
              <PixelButton
                variant="vermelho"
                onClick={() => navigate('/')}
                className="w-full py-4 text-[10px] flex items-center justify-center gap-2"
              >
                <PixelIcon name="seta" size={14} className="rotate-180" />
                MENU PRINCIPAL
              </PixelButton>
              <p className="text-[10px] text-gray-400 font-rpg text-center -mt-3">
                Seu progresso é salvo a cada turno.
              </p>
            </>
          )}
        </div>
      </div>
    </div>
  );
}

function Secao({ titulo, children }: { titulo: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="text-[10px] text-rpg-gold uppercase tracking-widest font-rpg mb-2">{titulo}</h3>
      {children}
    </section>
  );
}
