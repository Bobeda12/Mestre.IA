import { useNavigate } from 'react-router-dom';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Loader2, Archive, Play, LogOut, LogIn } from 'lucide-react';
import { api } from '../lib/api';
import { useAuth, useInvalidarAuth } from '../lib/auth';
import { getLocalImage } from '../lib/utils';
import PixelIcon from './PixelIcon';
import PixelButton from './PixelButton';
import PanelFrame from './PanelFrame';

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

  const arquivar = useMutation({
    mutationFn: async (sessionId: string) => {
      await api.patch(`/personagens/${sessionId}/arquivar`);
    },
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['personagens'] }),
  });

  const sair = useMutation({
    mutationFn: async () => api.post('/auth/sair'),
    onSuccess: () => {
      invalidarAuth();
      queryClient.removeQueries({ queryKey: ['personagens'] });
    },
  });

  return (
    <div className="h-screen w-screen bg-black flex flex-col items-center justify-center relative overflow-hidden font-sans">

      {/* Background — Etapa 14 (C-2): cena pixel art composta a partir de
          tiles do Tiny Dungeon (parede + chão + móveis), no lugar da foto
          gerada por IA. Mesma regra do ADR-0017: sem geração por IA. */}
      <div className="absolute inset-0 z-0">
        <div className="absolute inset-0 bg-gradient-to-t from-black via-black/80 to-black/40 z-10" />
        <img src="/assets/backgrounds/home.png" className="w-full h-full object-cover opacity-50"/>
      </div>

      {!carregandoAuth && (
        <div className="absolute top-4 right-4 z-30 flex items-center gap-3 text-sm">
          {logado ? (
            <>
              <span className="text-gray-500">{usuario?.email}</span>
              <button onClick={() => sair.mutate()} className="text-gray-500 hover:text-white flex items-center gap-1">
                <LogOut size={16} /> Sair
              </button>
            </>
          ) : (
            <button onClick={() => navigate('/entrar')} className="text-rpg-gold hover:text-white flex items-center gap-1 font-bold">
              <LogIn size={16} /> Entrar
            </button>
          )}
        </div>
      )}

      <div className="z-20 w-full max-w-6xl px-8 flex flex-col h-full justify-center">

        {/* Header */}
        <div className="text-center mb-12 animate-fade-in">
            <div className="mb-4 flex justify-center">
                <PixelIcon name="coroa" size={60} className="animate-pulse-slow drop-shadow-[0_0_15px_rgba(197,160,89,0.5)]" />
            </div>
            {/* Etapa 11 (B-1) — Press Start 2P é bem mais larga por letra que
                a Cinzel antiga; texto menor que o tamanho original pra não
                estourar a tela em telas estreitas. */}
            <h1 className="text-3xl md:text-6xl font-pixel-title text-white drop-shadow-lg tracking-wider mb-4 leading-relaxed">
            MESTRE<span className="text-red-600">.IA</span>
            </h1>
            <p className="text-gray-400 font-hand text-xl">Aventure-se no desconhecido.</p>
        </div>

        <div className="flex flex-col md:flex-row gap-12 items-start justify-center h-[400px]">

            {/* COLUNA 1: MENU PRINCIPAL */}
            <div className="flex-1 flex flex-col gap-6 items-center md:items-end w-full">
                <PixelButton
                    variant="vermelho"
                    onClick={() => navigate(logado ? '/criar' : '/entrar')}
                    className="w-full md:w-80 px-8 py-6 text-lg flex items-center justify-center gap-4 hover:scale-105"
                >
                    <PixelIcon name="espada" size={28} />
                    NOVO JOGO
                </PixelButton>
                {!logado && !carregandoAuth && (
                    <p className="text-xs text-gray-600 text-center md:text-right w-full md:w-80">
                        Entre com seu e-mail para criar e guardar seus heróis.
                    </p>
                )}
            </div>

            {/* COLUNA 2: MEUS HERÓIS */}
            <div className="flex-1 w-full md:w-auto h-full flex flex-col">
                <h3 className="text-rpg-gold font-rpg text-xl mb-4 flex items-center gap-2 border-b border-gray-800 pb-2">
                    <PixelIcon name="pergaminho" size={20}/> MEUS HERÓIS
                </h3>

                <div className="flex-1 overflow-y-auto custom-scrollbar pr-2 space-y-3">
                    {!logado ? (
                        <div className="text-gray-600 italic text-center mt-10">
                            Entre para ver seus heróis...
                        </div>
                    ) : personagens.isLoading ? (
                        <div className="flex justify-center mt-10"><Loader2 className="animate-spin text-gray-600" /></div>
                    ) : !personagens.data || personagens.data.length === 0 ? (
                        <div className="text-gray-600 italic text-center mt-10">Nenhum herói encontrado...<br/>Crie sua lenda.</div>
                    ) : (
                        personagens.data.map((p) => (
                            <div
                                key={p.session_id}
                                onClick={() => loadGame.mutate(p.session_id)}
                                role="button"
                                tabIndex={0}
                                onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); loadGame.mutate(p.session_id); } }}
                                aria-label={`Continuar como ${p.nome}, ${p.raca} ${p.classe}`}
                                className="group flex items-center gap-4 p-3 bg-gray-900/60 hover:bg-gray-800 border border-gray-800 hover:border-rpg-gold/50 cursor-pointer transition-all relative focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-rpg-gold"
                            >
                                <PanelFrame borderWidth={6} className="w-16 h-16 shrink-0 overflow-hidden flex items-center justify-center">
                                    <img src={getLocalImage('classes', p.classe)} alt="" className="w-full h-full" />
                                </PanelFrame>

                                <div className="flex-1 min-w-0">
                                    <h4 className="text-lg font-rpg text-gray-200 group-hover:text-white truncate">{p.nome}</h4>
                                    <p className="text-xs text-gray-500 uppercase tracking-wide">{p.raca} {p.classe} • Nível {p.nivel}</p>
                                    <p className="text-[10px] text-gray-600 mt-1 flex items-center gap-2">
                                        <span>📅 {new Date(p.criado_em).toLocaleDateString()}</span>
                                    </p>
                                </div>

                                <div className="w-10 h-10 rounded-full bg-black/50 group-hover:bg-rpg-gold text-gray-500 group-hover:text-black flex items-center justify-center transition-colors">
                                    {loadGame.isPending ? <Loader2 size={20} className="animate-spin"/> : <Play size={20} className="ml-1"/>}
                                </div>

                                <button
                                    onClick={(e) => { e.stopPropagation(); arquivar.mutate(p.session_id); }}
                                    className="absolute top-2 right-2 p-1 text-gray-700 hover:text-red-500 opacity-0 group-hover:opacity-100 focus-visible:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-red-500 transition-opacity"
                                    title="Arquivar herói"
                                    aria-label={`Arquivar ${p.nome}`}
                                >
                                    <Archive size={14}/>
                                </button>
                            </div>
                        ))
                    )}
                </div>
            </div>

        </div>
      </div>

      <footer className="absolute bottom-4 text-gray-700 text-xs font-rpg">v2.2 • Contas e biblioteca de heróis</footer>
    </div>
  );
}
