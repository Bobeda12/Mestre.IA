import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { api } from '../lib/api';
import { useAuth, useInvalidarAuth } from '../lib/auth';
import { useChaveGemini } from '../lib/config';
import { getLocalImage } from '../lib/utils';
import PixelIcon from './PixelIcon';
import PixelButton from './PixelButton';
import MapaDeFundo from './MapaDeFundo';
import Carregando from './Carregando';
import BotaoConfig from './BotaoConfig';
import BannerChaveGemini from './BannerChaveGemini';

interface Personagem {
  session_id: string;
  nome: string;
  raca: string;
  classe: string;
  hp_max: number;
  defesa: number;
  nivel: number;
  criado_em: string;
}

export default function Home() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const invalidarAuth = useInvalidarAuth();
  const { usuario, logado, carregando: carregandoAuth } = useAuth();
  const { chave: chaveGemini } = useChaveGemini();

  // Etapa 8, ADR-0014: a lista de heróis vem do servidor — `localStorage`
  // morreu como fonte de saves. Só roda a query depois de saber que está
  // logado (`enabled`), senão a primeira renderização dispara um 401 à toa.
  const personagens = useQuery({
    queryKey: ['personagens'],
    queryFn: async () => (await api.get<Personagem[]>('/personagens')).data,
    enabled: logado,
  });

  const loadGame = useMutation({
    mutationFn: async (sessionId: string) => {
      // Confere que a sessão ainda existe (e é sua) antes de navegar. O
      // resto dos dados (HP, defesa, atributos...) o próprio GameChat busca
      // de novo ao montar, a partir da URL — o backend é a fonte da verdade.
      await api.post('/load_game', { session_id: sessionId });
    },
    onSuccess: (_data, sessionId) => navigate(`/jogar/${sessionId}`),
    onError: () => alert('Erro: esse herói não existe mais, ou não é seu.'),
  });

  const excluir = useMutation({
    mutationFn: async (sessionId: string) => {
      await api.delete(`/personagens/${sessionId}`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['personagens'] }),
    onError: () => alert('Erro: não foi possível excluir esse herói. Tenta de novo.'),
  });

  const sair = useMutation({
    mutationFn: async () => api.post('/auth/sair'),
    onSuccess: () => {
      invalidarAuth();
      queryClient.removeQueries({ queryKey: ['personagens'] });
    },
  });

  return (
    <div className="min-h-[100dvh] w-full bg-rpg-darker flex flex-col items-center relative overflow-x-hidden">

      {/* Etapa 14 (revisão) — o fundo era um tile de masmorra repetido, e leu
          como defeito. Agora é um mapa de overworld deslizando devagar, que é
          o vocabulário de tela de título de console. Ver MapaDeFundo.tsx. */}
      <MapaDeFundo />

      {/* Trilha na tela inicial (revisão da Etapa 14): antes só o jogo tinha
          música. Fica fora do bloco de auth abaixo pra aparecer mesmo enquanto
          a sessão ainda está carregando. */}
      <div className="absolute top-4 left-4 z-30">
        <BotaoConfig tema="aventura" mostrarVoltar={false} />
      </div>

      {!carregandoAuth && (
        <div className="absolute top-4 right-4 z-30 flex items-center gap-3 text-sm font-rpg">
          {logado ? (
            <>
              {chaveGemini && (
                <span title="Chave própria ativa (VIP)">
                  <PixelIcon name="estrela" size={12} alt="Chave própria ativa (VIP)" />
                </span>
              )}
              <span className="text-gray-400 hidden sm:inline">{usuario?.email}</span>
              <button onClick={() => sair.mutate()} className="text-gray-400 hover:text-rpg-gold">
                Sair
              </button>
            </>
          ) : (
            <button onClick={() => navigate('/entrar')} className="text-rpg-gold hover:text-white flex items-center gap-1">
              Entrar <PixelIcon name="seta" size={14} />
            </button>
          )}
        </div>
      )}

      {/* Tela de título: tudo numa coluna central. A versão anterior punha o
          botão numa coluna e a lista de heróis noutra, e as duas metades não
          se equilibravam (um botão de um lado, uma lista quase sempre vazia do
          outro). Menu empilhado no centro é como console de verdade abre. */}
      <div className="z-20 w-full max-w-2xl px-6 flex flex-col items-center justify-center flex-1 py-16">

        <div className="text-center mb-10 animate-fade-in">
          <PixelIcon name="coroa" size={96} className="mx-auto mb-6 animate-pulse-slow" />
          {/* Press Start 2P é bem mais larga por letra que uma fonte comum:
              tamanho contido pra não estourar em tela estreita (Etapa 11). */}
          <h1 className="text-2xl md:text-5xl font-pixel-title text-white tracking-wider mb-4 leading-relaxed drop-shadow-[0_4px_0_rgba(0,0,0,0.8)]">
            MESTRE<span className="text-red-600">.IA</span>
          </h1>
          <p className="text-gray-300 font-hand text-xl">Aventure-se no desconhecido.</p>
        </div>

        <PixelButton
          variant="vermelho"
          onClick={() => navigate(logado ? '/criar' : '/entrar')}
          className="w-full max-w-sm py-5 text-xs md:text-sm flex items-center justify-center gap-3"
        >
          <PixelIcon name="espada" size={22} />
          NOVO JOGO
        </PixelButton>

        {!logado && !carregandoAuth && (
          <p className="text-xs text-gray-400 text-center mt-3 font-rpg max-w-sm">
            Entre com seu e-mail para criar e guardar seus heróis.
          </p>
        )}

        {logado && <BannerChaveGemini />}

        {/* A lista de heróis só ocupa espaço quando existe. Antes o título
            "MEUS HERÓIS" aparecia sempre, inclusive vazio ao lado do menu. */}
        {logado && (
          <div className="w-full max-w-sm mt-10">
            <h2 className="text-rpg-gold font-rpg text-sm mb-3 flex items-center gap-2 uppercase tracking-widest">
              <PixelIcon name="pergaminho" size={16} /> Continuar
            </h2>

            <div className="max-h-72 overflow-y-auto custom-scrollbar pr-1 space-y-2">
              {personagens.isLoading ? (
                <div className="flex justify-center py-6 text-gray-400"><Carregando rotulo="Carregando heróis" /></div>
              ) : !personagens.data || personagens.data.length === 0 ? (
                <p className="text-gray-400 text-sm text-center py-6 font-rpg">
                  Nenhum herói ainda. Crie sua lenda.
                </p>
              ) : (
                personagens.data.map((p, i) => (
                  <div
                    key={p.session_id}
                    onClick={() => loadGame.mutate(p.session_id)}
                    role="button"
                    tabIndex={0}
                    onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadGame.mutate(p.session_id); } }}
                    aria-label={`Continuar como ${p.nome}, ${p.raca} ${p.classe}`}
                    style={{ animationDelay: `${i * 60}ms` }}
                    className="group flex items-center gap-3 p-2 bg-black/70 border-2 border-gray-700 hover:border-rpg-gold hover:-translate-y-0.5 hover:scale-[1.01] active:translate-y-0 active:scale-[0.99] cursor-pointer transition-all duration-150 relative focus-visible:outline-none focus-visible:border-rpg-gold animate-fade-in"
                  >
                    <div className="pixel-frame w-12 h-12 shrink-0 bg-black overflow-hidden">
                      <img src={getLocalImage('classes', p.classe)} alt="" className="w-full h-full" />
                    </div>

                    <div className="flex-1 min-w-0">
                      <h3 className="font-rpg text-gray-100 group-hover:text-white truncate">{p.nome}</h3>
                      <p className="text-[11px] text-gray-400 uppercase tracking-wide font-rpg">
                        {p.raca} {p.classe} · Nível {p.nivel}
                      </p>
                    </div>

                    <span className="text-gray-500 group-hover:text-rpg-gold transition-colors pr-1">
                      {loadGame.isPending ? <Carregando tamanho={5} rotulo="Abrindo" /> : <PixelIcon name="seta" size={18} />}
                    </span>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        if (window.confirm('Deseja mesmo excluir este herói?')) {
                          excluir.mutate(p.session_id);
                        }
                      }}
                      className="absolute top-1 right-1 p-1 opacity-40 hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none transition-opacity"
                      title="Excluir herói"
                      aria-label={`Excluir ${p.nome}`}
                    >
                      <PixelIcon name="fechar" size={14} />
                    </button>
                  </div>
                ))
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
